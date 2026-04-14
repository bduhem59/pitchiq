#!/usr/bin/env python3
"""
api.py — PitchIQ FastAPI backend

Endpoints :
  GET /players/list                               → all players across all leagues
  GET /player/{name}?league=Ligue_1&season=2025   → full player card
  GET /league/averages?league=Ligue_1             → positional averages for radar
  GET /health                                     → sanity check

Run :
    uvicorn api:app --reload --port 8000
"""

from __future__ import annotations

import html as _html
import json
import logging
import math
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from player_data import fetch_understat_data, fetch_transfermarkt_data, get_tm_cache_entry, normalize_name

# ─────────────────────────────────────────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("pitchiq")

app = FastAPI(
    title="PitchIQ API",
    description="Football Intelligence Platform — multi-league analytics",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent

# All supported leagues and their percentile files
LEAGUE_FILES: dict[str, Path] = {
    "Ligue_1":    BASE_DIR / "percentiles.json",
    "EPL":        BASE_DIR / "percentiles_epl.json",
    "La_Liga":    BASE_DIR / "percentiles_laliga.json",
    "Bundesliga": BASE_DIR / "percentiles_bundesliga.json",
    "Serie_A":    BASE_DIR / "percentiles_seriea.json",
}

TM_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.transfermarkt.com/",
}

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _decode_names(records: list[dict]) -> list[dict]:
    """Decode HTML entities in player_name fields (e.g. &#039; → ')."""
    for r in records:
        if "player_name" in r:
            r["player_name"] = _html.unescape(r["player_name"])
    return records


def _load_percentiles(league: str = "Ligue_1") -> list[dict]:
    """Load percentile records for a single league."""
    path = LEAGUE_FILES.get(league)
    if not path or not path.exists():
        return []
    return _decode_names(json.loads(path.read_text(encoding="utf-8")))


def _load_all_percentiles() -> list[dict]:
    """Load percentile records for all leagues, tagging each record with its league."""
    all_records: list[dict] = []
    for league_code, path in LEAGUE_FILES.items():
        if not path.exists():
            log.warning("Percentile file missing: %s", path)
            continue
        records = _decode_names(json.loads(path.read_text(encoding="utf-8")))
        for r in records:
            r["league"] = league_code
        all_records.extend(records)
    return all_records


def _find_percentile_record(name: str, records: list[dict]) -> dict | None:
    needle = name.lower().strip()
    # 1. Exact match (covers the vast majority of calls — name comes from the same records)
    for r in records:
        if r["player_name"].lower().strip() == needle:
            return r
    # 2. Substring fallback (legacy / search-bar partial queries)
    for r in records:
        if needle in r["player_name"].lower():
            return r
    return None


def _build_percentile_context(record: dict, records: list[dict]) -> dict | None:
    """Return rank context (total players, per-metric rank) for the player's pos group."""
    pos_group = record.get("position_group", "")
    same_pos = [r for r in records if r.get("position_group") == pos_group]
    total = len(same_pos)

    ranks: dict[str, int] = {}
    for key in ["xG_90", "npxG_90", "xA_90", "xGChain_90", "xGBuildup_90"]:
        val = record.get(key, 0.0)
        sorted_pop = sorted([r.get(key, 0.0) for r in same_pos], reverse=True)
        ranks[key] = next(
            (i + 1 for i, v in enumerate(sorted_pop) if abs(v - val) < 1e-9),
            sum(1 for v in sorted_pop if v > val) + 1,
        )

    return {"total": total, "pos_group": pos_group, "ranks": ranks}



def _avg_percentile(record: dict | None) -> float | None:
    if record is None:
        return None
    pcts = (record.get("percentiles") or {})
    vals = [v for v in pcts.values() if v is not None]
    return sum(vals) / len(vals) if vals else None


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────────────────

LEAGUE_LOGO_URLS: dict[str, str] = {
    "Ligue_1":    "https://tmssl.akamaized.net/images/logo/normal/fr1.png",
    "EPL":        "https://tmssl.akamaized.net/images/logo/normal/gb1.png",
    "La_Liga":    "https://tmssl.akamaized.net/images/logo/normal/es1.png",
    "Bundesliga": "https://tmssl.akamaized.net/images/logo/normal/l1.png",
    "Serie_A":    "https://tmssl.akamaized.net/images/logo/normal/it1.png",
}

@app.get("/league/logo/{code}")
def league_logo(code: str) -> Response:
    """Proxy a league logo from Transfermarkt CDN (bypasses hotlink protection)."""
    url = LEAGUE_LOGO_URLS.get(code)
    if not url:
        raise HTTPException(status_code=404, detail=f"Unknown league: {code}")
    try:
        r = requests.get(url, headers=TM_HEADERS, timeout=8)
        r.raise_for_status()
        return Response(content=r.content, media_type="image/png",
                        headers={"Cache-Control": "public, max-age=86400"})
    except Exception as exc:
        log.warning("League logo fetch failed (%s): %s", code, exc)
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "2.0.0"}


@app.get("/admin/cache-status")
def cache_status() -> dict[str, Any]:
    """Returns TM cache statistics."""
    import unicodedata
    def _norm(name: str) -> str:
        nfkd = unicodedata.normalize("NFKD", name)
        return nfkd.encode("ASCII", "ignore").decode("ASCII").lower().strip()

    cache_path = BASE_DIR / "tm_cache.json"
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        cache = {}

    all_records = _load_all_percentiles()
    all_names   = list({r["player_name"] for r in all_records})
    cached    = [n for n in all_names
                 if _norm(n) in cache
                 and cache[_norm(n)].get("_status") != "not_found"]
    not_found = [n for n in all_names
                 if cache.get(_norm(n), {}).get("_status") == "not_found"]

    return {
        "total_players":  len(all_names),
        "cached_players": len(cached),
        "not_found":      len(not_found),
        "pending":        len(all_names) - len(cached) - len(not_found),
        "coverage_pct":   round(100 * len(cached) / max(len(all_names), 1), 1),
    }


@app.get("/players/list")
def players_list(
    league: str | None = Query(default=None, description="Filter by league code (optional)")
) -> list[dict[str, Any]]:
    """
    Returns players from all leagues (or a single league if ?league= is provided).
    Each record includes a 'league' field.

    Response shape per item:
        {
          "player_name": "...", "team": "...", "position_group": "...",
          "league": "EPL",
          "avg_percentile": 63.2,
          "minutes": 2202, "goals": 16, "assists": 1,
          "xG_90": 0.60, ...
        }
    """
    if league:
        records = _load_percentiles(league)
        for r in records:
            r["league"] = league
    else:
        records = _load_all_percentiles()

    kpi_keys = ["xG_90", "npxG_90", "xA_90", "xGChain_90", "xGBuildup_90"]
    result: list[dict] = []
    for r in records:
        avg = _avg_percentile(r)
        row: dict[str, Any] = {
            "player_name":    r["player_name"],
            "team":           r.get("team", ""),
            "position_group": r.get("position_group", ""),
            "league":         r.get("league", "Ligue_1"),
            "avg_percentile": round(avg, 1) if avg is not None else None,
            "minutes":        r.get("minutes", 0),
            "goals":          r.get("goals", 0),
            "assists":        r.get("assists", 0),
        }
        for k in kpi_keys:
            row[k] = round(r.get(k, 0.0), 2)
        result.append(row)

    result.sort(key=lambda x: x["player_name"])
    return result


@app.get("/league/averages")
def league_averages(
    league: str = Query(default="Ligue_1", description="League code")
) -> dict[str, Any]:
    """
    Per-position average values (/90) for a given league.
    Used to draw the reference polygon on the radar chart.
    """
    records   = _load_percentiles(league)
    pos_groups = ["attaquants", "milieux", "défenseurs"]
    kpi_keys  = ["xG_90", "npxG_90", "xA_90", "xGChain_90", "xGBuildup_90"]

    result: dict[str, Any] = {}
    for pos in pos_groups:
        same = [r for r in records if r.get("position_group") == pos]
        if not same:
            continue
        avgs: dict[str, float] = {}
        for k in kpi_keys:
            vals = [r[k] for r in same if r.get(k) is not None]
            avgs[k] = round(sum(vals) / len(vals), 4) if vals else 0.0
        result[pos] = avgs
    return result


# ─────────────────────────────────────────────────────────────────────────────
# SIMILAR-PLAYERS HELPER
# ─────────────────────────────────────────────────────────────────────────────

_SIMILAR_KEYS = ["xG_90", "npxG_90", "xA_90", "xGChain_90", "xGBuildup_90"]
_SIMILAR_LABELS = {
    "xG_90": "xG/90", "npxG_90": "npxG/90", "xA_90": "xA/90",
    "xGChain_90": "xGChain/90", "xGBuildup_90": "xGBuildup/90",
}


def _euclidean_similar(target: dict, all_records: list[dict], target_name: str, n: int = 3) -> list[dict]:
    pos_group = target.get("position_group", "")
    # Use the name from the target record (already decoded) for reliable exclusion
    target_name_norm = target.get("player_name", target_name).lower()

    # Refine position matching using position_raw codes (D / F / M).
    # A player whose position_raw starts with D but also contains F (e.g. "D F M S")
    # is a completely different profile from a pure defender ("D S", "D M S", etc.).
    # Require candidates to share the same F-presence as the target.
    target_raw_codes = set(target.get("position_raw", "").split())
    target_has_f = "F" in target_raw_codes

    pool = [r for r in all_records if r.get("position_group") == pos_group]
    candidates = [
        r for r in pool
        if r.get("player_name", "").lower() != target_name_norm
        and ("F" in r.get("position_raw", "").split()) == target_has_f
    ]

    if not candidates:
        return []

    # Min-max normalise over entire pos-group pool (candidates + target)
    full_pool = candidates + [target]
    mins = {k: min(r.get(k, 0.0) for r in full_pool) for k in _SIMILAR_KEYS}
    maxs = {k: max(r.get(k, 0.0) for r in full_pool) for k in _SIMILAR_KEYS}

    def vec(r: dict) -> list[float]:
        return [(r.get(k, 0.0) - mins[k]) / max(maxs[k] - mins[k], 1e-9) for k in _SIMILAR_KEYS]

    tv = vec(target)
    max_d = math.sqrt(len(_SIMILAR_KEYS))

    scored: list[tuple[float, dict]] = []
    for r in candidates:
        rv = vec(r)
        d = math.sqrt(sum((a - b) ** 2 for a, b in zip(tv, rv)))
        similarity = round(max(0.0, (1.0 - d / max_d) * 100))
        scored.append((d, similarity, r))

    scored.sort(key=lambda x: x[0])

    # Load TM cache once for photo lookup
    tm_cache_path = BASE_DIR / "tm_cache.json"
    try:
        tm_cache: dict = json.loads(tm_cache_path.read_text(encoding="utf-8"))
    except Exception:
        tm_cache = {}

    result: list[dict] = []
    for d, similarity, r in scored[:n]:
        # 3 closest-value metrics
        diffs = sorted(
            [(k, abs(target.get(k, 0.0) - r.get(k, 0.0))) for k in _SIMILAR_KEYS],
            key=lambda x: x[1],
        )
        closest = [
            {"key": k, "label": _SIMILAR_LABELS[k], "value": round(r.get(k, 0.0), 2)}
            for k, _ in diffs[:3]
        ]

        avg = _avg_percentile(r)

        # Photo URL from TM cache
        pname = r["player_name"]
        norm_key = unicodedata.normalize("NFKD", pname.lower().strip()).encode("ASCII", "ignore").decode("ASCII")
        cached_tm = tm_cache.get(norm_key, {})
        photo_url = cached_tm.get("photo_url") if cached_tm.get("_status") != "not_found" else None
        if photo_url == "N/A":
            photo_url = None

        result.append({
            "player_name":     pname,
            "team":            r.get("team", ""),
            "league":          r.get("league", ""),
            "position_group":  r.get("position_group", ""),
            "similarity":      similarity,
            "avg_percentile":  round(avg, 1) if avg is not None else None,
            "closest_metrics": closest,
            "photo_url":       photo_url,
        })

    return result


@app.get("/player/{name}")
def player_detail(
    name: str,
    league: str = Query(default="Ligue_1"),
    season: str = Query(default="2025"),
    include_shots: bool = Query(default=True),
) -> dict[str, Any]:
    """Full player card data."""
    records = _load_percentiles(league)

    # ── Fetch Understat + Transfermarkt in parallel ───────────────────────────
    us: dict | None = None
    tm: dict | None = None
    us_exc: Exception | None = None
    tm_exc: Exception | None = None

    with ThreadPoolExecutor(max_workers=2) as pool:
        us_future = pool.submit(fetch_understat_data, name, league=league, season=season)
        tm_future = pool.submit(fetch_transfermarkt_data, name)

        try:
            us = us_future.result()
        except Exception as exc:
            us_exc = exc

        try:
            tm = tm_future.result()
        except Exception as exc:
            tm_exc = exc
            log.warning("Transfermarkt unavailable for '%s': %s", name, exc)

    if us_exc is not None:
        if isinstance(us_exc, ValueError):
            raise HTTPException(status_code=404, detail=str(us_exc))
        log.exception("Understat error for '%s'", name)
        raise HTTPException(status_code=502, detail=f"Understat error: {us_exc}")

    if not include_shots:
        us = {k: v for k, v in us.items() if k != "shot_coords"}

    # ── Percentiles ──────────────────────────────────────────────────────────
    pct_record  = _find_percentile_record(name, records)
    pct_context = _build_percentile_context(pct_record, records) if pct_record else None
    avg_pct     = _avg_percentile(pct_record)

    return {
        "understat":          us,
        "transfermarkt":      tm,
        "percentile_record":  pct_record,
        "percentile_context": pct_context,
        "avg_percentile":     round(avg_pct, 2) if avg_pct is not None else None,
    }


@app.get("/player/{name}/club-logo")
def player_club_logo(name: str) -> Response:
    """Proxy the club logo for a player from TM cache."""
    tm = get_tm_cache_entry(name)
    logo_url = (tm or {}).get("club_logo_url", "")
    if not logo_url or logo_url == "N/A":
        raise HTTPException(status_code=404, detail="No club logo available")
    try:
        r = requests.get(logo_url, headers=TM_HEADERS, timeout=8)
        r.raise_for_status()
        mime = "image/png" if r.content[:4] == b"\x89PNG" else "image/jpeg"
        return Response(
            content=r.content, media_type=mime,
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except Exception as exc:
        log.warning("Club logo proxy failed (%s): %s", name, exc)
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/player/{name}/photo")
def player_photo(name: str) -> Response:
    """Proxy a player photo from TM cache (avoids CORS / hotlink issues)."""
    tm = get_tm_cache_entry(name)
    photo_url = (tm or {}).get("photo_url", "")
    if not photo_url or photo_url == "N/A":
        raise HTTPException(status_code=404, detail="No photo available")
    try:
        r = requests.get(photo_url, headers=TM_HEADERS, timeout=8)
        r.raise_for_status()
        mime = "image/png" if r.content[:4] == b"\x89PNG" else "image/jpeg"
        return Response(
            content=r.content, media_type=mime,
            headers={"Cache-Control": "public, max-age=3600"},
        )
    except Exception as exc:
        log.warning("Player photo proxy failed (%s): %s", name, exc)
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/player/{name}/similar")
def player_similar(
    name: str,
    league: str = Query(default="Ligue_1"),
) -> list[dict[str, Any]]:
    """Return the 3 most statistically similar players (same position, all leagues)."""
    # Load target's percentile record
    records = _load_percentiles(league)
    target  = _find_percentile_record(name, records)
    if not target:
        # Fall back: search across all leagues
        all_r  = _load_all_percentiles()
        target = _find_percentile_record(name, all_r)
        if not target:
            raise HTTPException(status_code=404, detail=f"'{name}' not found in percentile data")
        return _euclidean_similar(target, all_r, name, n=3)

    all_records = _load_all_percentiles()
    return _euclidean_similar(target, all_records, name, n=3)
