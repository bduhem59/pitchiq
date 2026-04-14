#!/usr/bin/env python3
"""
build_tm_cache.py — Populate the Transfermarkt cache using a real Chrome browser.

Uses nodriver (undetected Chrome via CDP) in VISIBLE mode to bypass AWS WAF.
Scraped data is saved to tm_cache.json for use by the PitchIQ API.

Usage:
    python3 build_tm_cache.py                          # cache all players from percentile files
    python3 build_tm_cache.py "Kylian Mbappé"          # cache a single player
    python3 build_tm_cache.py --league EPL              # cache all EPL players
    python3 build_tm_cache.py --limit 20               # cache first 20 uncached players
    python3 build_tm_cache.py --status                 # show cache coverage stats
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR   = Path(__file__).parent
CACHE_PATH = BASE_DIR / "tm_cache.json"
TM_BASE    = "https://www.transfermarkt.com"

ALIASES_PATH     = BASE_DIR / "tm_aliases.json"
DIRECT_URLS_PATH = BASE_DIR / "tm_direct_urls.json"


def _load_aliases() -> dict[str, str]:
    """Load normalized name → TM search name mapping."""
    try:
        raw = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
        return {k: v for k, v in raw.items() if not k.startswith("_")}
    except Exception:
        return {}


def _load_direct_urls() -> dict[str, str]:
    """Load normalized name → direct TM profile URL mapping."""
    try:
        raw = json.loads(DIRECT_URLS_PATH.read_text(encoding="utf-8"))
        return {k: v for k, v in raw.items() if not k.startswith("_")}
    except Exception:
        return {}


LEAGUE_FILES: dict[str, Path] = {
    "Ligue_1":    BASE_DIR / "percentiles.json",
    "EPL":        BASE_DIR / "percentiles_epl.json",
    "La_Liga":    BASE_DIR / "percentiles_laliga.json",
    "Bundesliga": BASE_DIR / "percentiles_bundesliga.json",
    "Serie_A":    BASE_DIR / "percentiles_seriea.json",
}


# ─────────────────────────────────────────────────────────────────────────────
# CACHE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def normalize_name(name: str) -> str:
    import html as _html
    name = _html.unescape(name)
    _TRANSLIT = str.maketrans({
        "ø": "o",  "Ø": "O",
        "æ": "ae", "Æ": "AE",
        "ð": "d",  "Ð": "D",
        "þ": "th", "Þ": "TH",
        "ß": "ss",
        "œ": "oe", "Œ": "OE",
        "ł": "l",  "Ł": "L",
    })
    name = name.translate(_TRANSLIT)
    nfkd = unicodedata.normalize("NFKD", name)
    return nfkd.encode("ASCII", "ignore").decode("ASCII").lower().strip()


def load_cache() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def all_players_from_files(league: str | None = None) -> list[str]:
    """Return all unique player names from percentile JSON files."""
    files = (
        {league: LEAGUE_FILES[league]} if league and league in LEAGUE_FILES
        else LEAGUE_FILES
    )
    names: list[str] = []
    seen: set[str] = set()
    for path in files.values():
        if not path.exists():
            continue
        records = json.loads(path.read_text(encoding="utf-8"))
        for r in records:
            n = r.get("player_name", "")
            if n and n not in seen:
                seen.add(n)
                names.append(n)
    return names


# ─────────────────────────────────────────────────────────────────────────────
# BROWSER SCRAPING (nodriver — visible Chrome)
# ─────────────────────────────────────────────────────────────────────────────

async def _is_blocked(page) -> bool:
    """Return True if the current page is a WAF challenge page.
    Checks the full page source (including <script> tags) for WAF markers.
    """
    try:
        # Use full HTML source — awsWaf is in <script> tags, invisible to innerText
        src = await page.evaluate("document.documentElement.outerHTML") or ""
        title = await page.evaluate("document.title") or ""
        return (
            "Human Verification" in title
            or "captcha" in title.lower()
            or "awsWaf" in src
            or "awswaf" in src.lower()
            or "gokuProps" in src          # AWS WAF challenge JS object
            or "window.awsWaf" in src
        )
    except Exception:
        return False


async def _get_page_html(browser, url: str, wait: float = 0.8) -> str:
    """Navigate to url and return the page HTML after waiting for JS."""
    page = await browser.get(url)
    await asyncio.sleep(wait)

    # AWS WAF PoW auto-solves in the browser; wait up to 30s in 5s increments
    for attempt in range(6):
        if not await _is_blocked(page):
            break
        if attempt == 0:
            print(f"\n  ⚠  WAF challenge on {url} — waiting for auto-solve (up to 30s)...")
        await asyncio.sleep(5)

    # Still blocked → ask user to interact with the browser
    if await _is_blocked(page):
        print("  Challenge still active. Please interact with the browser to solve it.")
        print("  Press ENTER in this terminal when the TM page has fully loaded.")
        try:
            input("  [Press ENTER when done] ")
        except EOFError:
            await asyncio.sleep(15)
        await asyncio.sleep(2)

    return await page.evaluate("document.documentElement.outerHTML")


def _parse_profile(html: str, profile_url: str) -> dict:
    """Parse a TM player profile page and extract key data."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")

    # Full name
    name_el = soup.select_one("h1.data-header__headline-wrapper")
    if name_el:
        for badge in name_el.select("[class]"):
            badge.decompose()
        full_name = re.sub(r"\s+", " ", name_el.get_text(" ", strip=True)).strip()
    else:
        full_name = "N/A"

    # Info table
    info: dict[str, str] = {}
    info_div = soup.select_one("div.info-table")
    if info_div:
        spans = info_div.select("span.info-table__content")
        for i in range(0, len(spans) - 1, 2):
            label = spans[i].get_text(strip=True).rstrip(":")
            value = re.sub(r"\s+", " ", spans[i + 1].get_text(" ", strip=True)).strip()
            info[label] = value

    # Market value
    market_value = "N/A"
    mv_el = soup.select_one("a.data-header__market-value-wrapper")
    if mv_el:
        raw = mv_el.get_text(" ", strip=True)
        market_value = re.split(r"last update", raw, flags=re.IGNORECASE)[0].strip()

    # Photo
    photo_el = soup.select_one("img.data-header__profile-image")
    photo_url = photo_el.get("src", "N/A") if photo_el else "N/A"

    # Club logo
    club_logo_url = "N/A"
    if info_div:
        spans_all = info_div.select("span.info-table__content")
        for i in range(0, len(spans_all) - 1, 2):
            if spans_all[i].get_text(strip=True).rstrip(":") == "Current club":
                img_el = spans_all[i + 1].select_one("img")
                if img_el:
                    src = img_el.get("src") or img_el.get("data-src", "N/A")
                    club_logo_url = src or "N/A"
                break

    return {
        "full_name":       full_name,
        "dob_age":         info.get("Date of birth/Age", "N/A"),
        "nationality":     info.get("Citizenship", "N/A"),
        "position":        info.get("Position", "N/A"),
        "club":            info.get("Current club", "N/A"),
        "club_logo_url":   club_logo_url,
        "market_value":    market_value,
        "contract_expiry": info.get("Contract expires", "N/A"),
        "photo_url":       photo_url,
        "profile_url":     profile_url,
    }


def _html_is_waf(html: str) -> bool:
    """Return True if the raw HTML looks like a WAF challenge page."""
    return (
        "awsWaf" in html
        or "gokuProps" in html
        or "window.awsWaf" in html
        or "Human Verification" in html
    )


def _name_variants(player_name: str) -> list[str]:
    """
    Return a list of name variants to try when TM doesn't find the full name.

    Strategy (in order):
      1. Alias from tm_aliases.json (if present)
      2. Full name as-is
      3. First + last word only  (drops middle names: "Ahmadou Bamba Dieng" → "Ahmadou Dieng")
      4. Last two words          ("Ahmadou Bamba Dieng" → "Bamba Dieng")
      5. Last word only          (family name search)
    Apostrophes are stripped from all variants so the URL query is clean.
    """
    aliases = _load_aliases()
    key = normalize_name(player_name)
    variants: list[str] = []

    # Alias first — if defined, only use that (skip generic retries)
    if key in aliases:
        variants.append(aliases[key])
        return variants

    words = player_name.split()
    variants.append(player_name)                       # full name
    if len(words) >= 3:
        variants.append(f"{words[0]} {words[-1]}")     # first + last
        variants.append(" ".join(words[-2:]))          # last two words
        variants.append(words[-1])                     # family name only

    # Strip apostrophes (N'Soki → NSoki) as a final fallback
    stripped = [v.replace("'", "").replace("'", "") for v in variants]
    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for v in variants + stripped:
        if v not in seen:
            seen.add(v)
            result.append(v)
    return result


async def _search_tm_single(browser, query: str) -> str | None:
    """Try a single TM search query. Returns profile URL or None. Raises RuntimeError on WAF."""
    ascii_query = normalize_name(query).replace("'", "").replace("'", "")
    search_url = (
        f"{TM_BASE}/schnellsuche/ergebnis/schnellsuche"
        f"?query={ascii_query.replace(' ', '+')}"
    )
    html = await _get_page_html(browser, search_url, wait=0.8)
    if _html_is_waf(html):
        raise RuntimeError("WAF block on search page")

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    links = soup.select("table.items td.hauptlink a[href*='/profil/spieler/']")
    if not links:
        return None

    normalized_query = normalize_name(query)
    for link in links:
        if normalize_name(link.get_text()) == normalized_query:
            return TM_BASE + link["href"]
    return TM_BASE + links[0]["href"]


async def _search_tm(browser, player_name: str) -> str | None:
    """
    Search TM for a player and return their profile URL.
    Tries multiple name variants (alias → full → shorter fallbacks).
    Returns None when genuinely not found. Raises RuntimeError on WAF.
    """
    variants = _name_variants(player_name)
    for i, variant in enumerate(variants):
        if i > 0:
            print(f"    ↳ retry with: {variant!r}")
        url = await _search_tm_single(browser, variant)
        if url:
            return url
    return None


async def _reestablish_session(browser) -> None:
    """Navigate to TM homepage to refresh session cookies."""
    print("\n  ⚠  Re-establishing TM session (WAF block detected)...")
    await _get_page_html(browser, TM_BASE, wait=5.0)
    print("  → Session refreshed.")


async def fetch_and_cache_player(browser, player_name: str, cache: dict) -> bool:
    """Fetch TM data for a player and add to cache. Returns True on success."""
    key = normalize_name(player_name)
    if key in cache:
        entry = cache[key]
        if isinstance(entry, dict) and entry.get("_status") == "not_found":
            return False  # skip silently
        return True  # already have full data

    # Direct URL bypass — skip search entirely
    direct_urls = _load_direct_urls()
    if key in direct_urls:
        profile_url = direct_urls[key]
        print(f"  → Direct URL: {profile_url}")
    else:
        print(f"  → Searching: {player_name}")
        for attempt in range(3):
            try:
                profile_url = await _search_tm(browser, player_name)
                break
            except RuntimeError:
                if attempt < 2:
                    await _reestablish_session(browser)
                else:
                    print(f"  ✗ WAF persists after 3 attempts, skipping: {player_name}")
                    return False
        else:
            profile_url = None

    if not profile_url:
        print(f"  ✗ Not found on TM: {player_name} (marqué pour skip)")
        cache[key] = {"_status": "not_found", "_cached_at": datetime.now(timezone.utc).isoformat()}
        save_cache(cache)
        return False

    try:
        print(f"  → Scraping: {profile_url}")
        html = await _get_page_html(browser, profile_url, wait=1.0)

        if _html_is_waf(html):
            await _reestablish_session(browser)
            html = await _get_page_html(browser, profile_url, wait=1.0)

        data = _parse_profile(html, profile_url)

        if data["full_name"] == "N/A" and data["dob_age"] == "N/A":
            print(f"  ✗ Profile data empty — TM still blocking: {player_name}")
            return False

        data["_cached_at"] = datetime.now(timezone.utc).isoformat()
        cache[key] = data
        save_cache(cache)
        print(f"  ✓ Cached: {data['full_name']} — {data['club']} — {data['market_value']}")
        return True

    except Exception as exc:
        print(f"  ✗ Error for {player_name}: {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def _categorize(cache: dict, all_names: list[str]):
    cached, not_found, pending = [], [], []
    for n in all_names:
        entry = cache.get(normalize_name(n))
        if entry is None:
            pending.append(n)
        elif isinstance(entry, dict) and entry.get("_status") == "not_found":
            not_found.append(n)
        else:
            cached.append(n)
    return cached, not_found, pending


def show_status() -> None:
    cache = load_cache()
    all_names = all_players_from_files()
    cached, not_found, pending = _categorize(cache, all_names)

    print(f"\n  Total players : {len(all_names)}")
    print(f"  ✓ Cached      : {len(cached)}  ({100*len(cached)//max(len(all_names),1)}%)")
    print(f"  ✗ Not on TM   : {len(not_found)}")
    print(f"  ⏳ Pending     : {len(pending)}")
    print(f"  Cache file    : {CACHE_PATH}")

    if pending:
        print(f"\n  First 20 pending:")
        for n in pending[:20]:
            print(f"    - {n}")
        if len(pending) > 20:
            print(f"    ... and {len(pending)-20} more")


async def run_cache_builder(players: list[str], limit: int | None) -> None:
    import nodriver as uc

    cache = load_cache()

    # Filter to players not yet processed (excludes both cached and not_found)
    def _needs_processing(name: str) -> bool:
        entry = cache.get(normalize_name(name))
        if entry is None:
            return True
        if isinstance(entry, dict) and entry.get("_status") == "not_found":
            return False
        return False  # already cached

    uncached = [p for p in players if _needs_processing(p)]
    if limit:
        uncached = uncached[:limit]

    if not uncached:
        print("All specified players are already cached!")
        return

    print(f"\nPlayers to cache: {len(uncached)}")
    print("Opening Chrome browser (VISIBLE mode to bypass WAF)...")
    print("Cookies are saved to ~/.pitchiq_chrome_profile — challenge solved once, then reused.\n")

    # Persistent profile so TM cookies survive between runs
    profile_dir = Path.home() / ".pitchiq_chrome_profile"
    profile_dir.mkdir(exist_ok=True)

    browser = await uc.start(
        headless=False,
        user_data_dir=str(profile_dir),
    )

    # Open TM homepage to refresh/establish session
    print("  → Opening TM homepage to establish session...")
    await _get_page_html(browser, TM_BASE, wait=5.0)
    print("  → Session established.")

    ok = 0
    fail = 0
    for i, player_name in enumerate(uncached, 1):
        print(f"\n[{i}/{len(uncached)}] ", end="", flush=True)
        success = await fetch_and_cache_player(browser, player_name, cache)
        if success:
            ok += 1
        else:
            fail += 1
        # Delay between requests — 0.3s normally, 3s every 20 players
        if i % 20 == 0:
            print(f"  (pausing 3s after {i} requests...)")
            await asyncio.sleep(3)
        else:
            await asyncio.sleep(0.3)

    browser.stop()
    print(f"\n{'─'*50}")
    print(f"Done! Cached: {ok}  Failed: {fail}")
    print(f"Total in cache: {len(load_cache())} players")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build TM cache for PitchIQ")
    parser.add_argument("players", nargs="*", help="Player name(s) to cache")
    parser.add_argument("--league", help="Cache all players from a specific league")
    parser.add_argument("--limit", type=int, help="Max number of uncached players to process")
    parser.add_argument("--status", action="store_true", help="Show cache coverage stats")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.players:
        players = args.players
    else:
        players = all_players_from_files(args.league)
        league_str = args.league or "all leagues"
        print(f"Found {len(players)} players across {league_str}")

    asyncio.run(run_cache_builder(players, args.limit))


if __name__ == "__main__":
    main()
