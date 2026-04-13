#!/usr/bin/env python3
"""
api.py — xScout FastAPI backend

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
from pathlib import Path
from typing import Any

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from player_data import fetch_understat_data, fetch_transfermarkt_data, get_tm_cache_entry

# ─────────────────────────────────────────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("xscout")

app = FastAPI(
    title="xScout API",
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
        records = json.loads(path.read_text(encoding="utf-8"))
        for r in records:
            r["league"] = league_code
        all_records.extend(records)
    return all_records


def _find_percentile_record(name: str, records: list[dict]) -> dict | None:
    needle = name.lower()
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


def _fetch_photo_bytes_b64(url: str) -> str | None:
    import base64
    try:
        r = requests.get(url, headers=TM_HEADERS, timeout=8)
        r.raise_for_status()
        mime = "image/png" if r.content[:4] == b"\x89PNG" else "image/jpeg"
        b64 = base64.b64encode(r.content).decode()
        return f"data:{mime};base64,{b64}"
    except Exception as exc:
        log.warning("Photo download failed (%s): %s", url, exc)
        return None


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


@app.get("/player/{name}")
def player_detail(
    name: str,
    league: str = Query(default="Ligue_1"),
    season: str = Query(default="2025"),
    include_shots: bool = Query(default=True),
) -> dict[str, Any]:
    """Full player card data."""
    records = _load_percentiles(league)

    # ── Understat ────────────────────────────────────────────────────────────
    try:
        us = fetch_understat_data(name, league=league, season=season)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        log.exception("Understat error for '%s'", name)
        raise HTTPException(status_code=502, detail=f"Understat error: {exc}")

    if not include_shots:
        us = {k: v for k, v in us.items() if k != "shot_coords"}

    # ── Transfermarkt ────────────────────────────────────────────────────────
    tm: dict | None = None
    photo_data_uri: str | None = None
    club_logo_data_uri: str | None = None
    try:
        tm = fetch_transfermarkt_data(name)
        photo_url = (tm or {}).get("photo_url", "")
        if photo_url and photo_url != "N/A":
            photo_data_uri = _fetch_photo_bytes_b64(photo_url)
        logo_url = (tm or {}).get("club_logo_url", "")
        if logo_url and logo_url != "N/A":
            club_logo_data_uri = _fetch_photo_bytes_b64(logo_url)
    except Exception as exc:
        log.warning("Transfermarkt unavailable for '%s': %s", name, exc)

    # ── Percentiles ──────────────────────────────────────────────────────────
    pct_record  = _find_percentile_record(name, records)
    pct_context = _build_percentile_context(pct_record, records) if pct_record else None
    avg_pct     = _avg_percentile(pct_record)

    return {
        "understat":            us,
        "transfermarkt":        tm,
        "percentile_record":    pct_record,
        "percentile_context":   pct_context,
        "avg_percentile":       round(avg_pct, 2) if avg_pct is not None else None,
        "photo_data_uri":       photo_data_uri,
        "club_logo_data_uri":   club_logo_data_uri,
    }
