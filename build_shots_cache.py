#!/usr/bin/env python3
"""
build_shots_cache.py — Pré-construit le cache de tirs pour tous les joueurs.

Usage :
    python3 build_shots_cache.py                    # toutes les ligues
    python3 build_shots_cache.py Ligue_1            # une seule ligue
    python3 build_shots_cache.py EPL La_Liga        # plusieurs ligues

Le fichier shots_cache.json est commité dans git → Railway n'a jamais
besoin d'appeler Understat au runtime.
"""

import json
import sys
import time
from pathlib import Path

from player_data import _fetch_shots_cached, _shots_cache, _SHOTS_CACHE_PATH

BASE_DIR = Path(__file__).parent
SEASON   = "2025"

LEAGUE_FILES = {
    "Ligue_1":    BASE_DIR / "percentiles.json",
    "EPL":        BASE_DIR / "percentiles_epl.json",
    "La_Liga":    BASE_DIR / "percentiles_laliga.json",
    "Bundesliga": BASE_DIR / "percentiles_bundesliga.json",
    "Serie_A":    BASE_DIR / "percentiles_seriea.json",
}


def build_for_league(league: str) -> None:
    path = LEAGUE_FILES.get(league)
    if not path or not path.exists():
        print(f"  ⚠ Fichier introuvable pour {league}")
        return

    records = json.loads(path.read_text(encoding="utf-8"))
    total   = len(records)
    cached_before = len(_shots_cache)

    print(f"\n{'─'*60}")
    print(f"  {league} — {total} joueurs, saison {SEASON}")
    print(f"{'─'*60}")

    ok = skipped = errors = 0
    t_start = time.time()

    for i, r in enumerate(records, 1):
        player_id = str(r.get("player_id", ""))
        name      = r.get("player_name", "?")
        key       = f"{player_id}_{SEASON}"

        if not player_id:
            skipped += 1
            continue

        if key in _shots_cache:
            skipped += 1
            continue

        try:
            shots = _fetch_shots_cached(player_id, SEASON)
            ok += 1
            elapsed = time.time() - t_start
            eta     = elapsed / ok * (total - i) if ok else 0
            print(f"  [{i:3}/{total}] {name:<30} {len(shots):3} tirs  "
                  f"(ETA {eta/60:.1f}min)")
        except Exception as e:
            errors += 1
            print(f"  [{i:3}/{total}] {name:<30} ERREUR: {e}")

    new_entries = len(_shots_cache) - cached_before
    print(f"\n  ✓ {ok} nouveaux, {skipped} déjà cachés, {errors} erreurs")
    print(f"  {new_entries} entrées ajoutées au cache disque")


def main(leagues: list[str]) -> None:
    print(f"\n{'═'*60}")
    print(f"  PitchIQ — Build shots cache ({SEASON})")
    print(f"  Cible : {', '.join(leagues)}")
    print(f"  Cache actuel : {len(_shots_cache)} entrées")
    print(f"{'═'*60}")

    t0 = time.time()
    for league in leagues:
        build_for_league(league)

    total_time = time.time() - t0
    print(f"\n{'═'*60}")
    print(f"  Terminé en {total_time/60:.1f}min")
    print(f"  Cache total : {len(_shots_cache)} entrées → {_SHOTS_CACHE_PATH.name}")
    print(f"{'═'*60}\n")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args:
        requested = [a for a in args if a in LEAGUE_FILES]
        unknown   = [a for a in args if a not in LEAGUE_FILES]
        if unknown:
            print(f"Ligues inconnues : {unknown}")
            print(f"Valides : {list(LEAGUE_FILES.keys())}")
            sys.exit(1)
        main(requested)
    else:
        main(list(LEAGUE_FILES.keys()))
