#!/usr/bin/env python3
"""
player_data.py — Pipeline de données pour le scouting football

Récupère les infos d'un joueur depuis :
  1. Understat  → stats offensives + coordonnées de tirs
  2. Transfermarkt → profil (âge, club, valeur marchande, etc.)

Usage :
    python3 player_data.py                          # joueur par défaut (Kvaratskhelia)
    python3 player_data.py "Ousmane Dembélé"        # autre joueur
"""

import sys
import json
import time
import unicodedata
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from understatapi import UnderstatClient

# ─────────────────────────────────────────────
# TM CACHE
# ─────────────────────────────────────────────

_CACHE_PATH = Path(__file__).parent / "tm_cache.json"


def _load_tm_cache() -> dict:
    try:
        return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_tm_cache(cache: dict) -> None:
    _CACHE_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _cache_key(name: str) -> str:
    return normalize_name(name)


# ─────────────────────────────────────────────
# UTILITAIRES COMMUNS
# ─────────────────────────────────────────────

def normalize_name(name: str) -> str:
    """
    Normalise un nom de joueur pour faciliter la comparaison :
    - décode les entités HTML (&#039; → ')
    - translittère les caractères non-ASCII que NFKD ne décompose pas
      (ø→o, æ→ae, ð→d, þ→th, ß→ss, œ→oe, ł→l, …)
    - supprime les accents (é → e, ü → u, etc.) via NFKD
    - met tout en minuscules et supprime les espaces en début/fin

    Exemple : "Pierre-Emile Højbjerg" → "pierre-emile hojbjerg"
    """
    import html as _html
    # Décode les entités HTML (&#039; m'bala → 'm'bala)
    name = _html.unescape(name)

    # Translittération manuelle pour les caractères que NFKD ne décompose pas
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

    # NFKD décompose les caractères accentués (é → e + ´)
    nfkd = unicodedata.normalize("NFKD", name)
    # On ne garde que les caractères ASCII (les accents sont abandonnés)
    ascii_name = nfkd.encode("ASCII", "ignore").decode("ASCII")
    return ascii_name.lower().strip()


# ─────────────────────────────────────────────
# SOURCE 1 : UNDERSTAT
# ─────────────────────────────────────────────

# Mapping des noms de ligue lisibles → codes acceptés par understatapi
LEAGUE_MAP = {
    "ligue 1":   "Ligue_1",
    "premier league": "EPL",
    "la liga":   "La_Liga",
    "bundesliga": "Bundesliga",
    "serie a":   "Serie_A",
    "rfpl":      "RFPL",
}


def _compute_games(games: int, minutes: int) -> int:
    if games > 0:
        return games
    if minutes > 0:
        return max(1, round(minutes / 75))
    return 0


@lru_cache(maxsize=16)
def _fetch_league_players_cached(league: str, season: str) -> list:
    """Downloads all players for a league/season. lru_cache keeps it in memory for the process lifetime."""
    t0 = time.time()
    print(f"  [Understat] Téléchargement liste {league}/{season}...")
    with UnderstatClient() as understat:
        players = understat.league(league=league).get_player_data(season=season)
    print(f"  [timing] Understat league list: {time.time() - t0:.2f}s — {len(players)} joueurs")
    return players


@lru_cache(maxsize=512)
def _fetch_shots_cached(player_id: str, season: str) -> list:
    """Downloads all shots for a player in a given season. lru_cache keeps it in memory."""
    t0 = time.time()
    with UnderstatClient() as understat:
        all_shots = understat.player(player=player_id).get_shot_data()
    shots = [s for s in all_shots if s.get("season") == season]
    print(f"  [timing] Understat shots (id={player_id}): {time.time() - t0:.2f}s — {len(shots)} tirs")
    return shots


def fetch_understat_data(player_name: str,
                         league: str = "Ligue_1",
                         season: str = "2024") -> dict:
    """
    Récupère les statistiques Understat d'un joueur.

    Étapes :
      1. Télécharge la liste de tous les joueurs de la ligue + saison donnée (cachée).
      2. Trouve le joueur par correspondance de nom (normalisé).
      3. Récupère ses tirs individuels (cachés par player_id).
    """
    normalized_search = normalize_name(player_name)

    # ── Étape 1 : liste des joueurs (lru_cache — réseau seulement au 1er appel) ──
    try:
        all_players = _fetch_league_players_cached(league, season)
    except Exception as e:
        raise ValueError(
            f"Impossible de récupérer les joueurs de {league} saison {season}.\n"
            f"  Vérifiez le nom de ligue (valides : {list(LEAGUE_MAP.values())}).\n"
            f"  Erreur technique : {e}"
        )

    # ── Étape 2 : trouver le joueur par son nom ───────────────────────────────
    player_stats = None
    player_id    = None

    for p in all_players:
        if normalize_name(p.get("player_name", "")) == normalized_search:
            player_stats = p
            player_id    = p.get("id")
            break

    if player_stats is None:
        for p in all_players:
            pname = normalize_name(p.get("player_name", ""))
            if normalized_search in pname or pname in normalized_search:
                player_stats = p
                player_id    = p.get("id")
                print(f"  ⚠ Correspondance partielle trouvée : {p.get('player_name')}")
                break

    if player_stats is None:
        raise ValueError(
            f"Joueur '{player_name}' introuvable dans {league} saison {season}.\n"
            f"  Astuce : vérifiez l'orthographe ou la ligue/saison."
        )

    print(f"  Joueur trouvé : {player_stats.get('player_name')} (ID {player_id})")

    # ── Étape 3 : tirs individuels (lru_cache — réseau seulement au 1er appel) ─
    shot_coords = []

    if player_id:
        try:
            season_shots = _fetch_shots_cached(str(player_id), season)
            shot_coords = [
                {
                    "x":         float(s.get("X", 0)),
                    "y":         float(s.get("Y", 0)),
                    "xG":        float(s.get("xG", 0)),
                    "result":    s.get("result", ""),
                    "situation": s.get("situation", ""),
                    "minute":    s.get("minute", ""),
                    "h_team":    s.get("h_team", ""),
                    "a_team":    s.get("a_team", ""),
                    "h_goals":   s.get("h_goals"),
                    "a_goals":   s.get("a_goals"),
                    "h_a":       s.get("h_a", ""),
                }
                for s in season_shots
            ]
        except Exception as e:
            print(f"  ⚠ Tirs individuels indisponibles : {e}")

    # ── Construction du résultat ─────────────────────────────────────────────
    return {
        "player_name": player_stats.get("player_name"),
        "player_id":   player_id,
        "league":      league,
        "season":      season,

        # Stats offensives attendues (expected)
        "xG":        float(player_stats.get("xG", 0)),        # expected goals
        "npxG":      float(player_stats.get("npxG", 0)),      # xG hors penalties
        "xA":        float(player_stats.get("xA", 0)),        # expected assists
        "xGChain":   float(player_stats.get("xGChain", 0)),   # xG des actions où il participe
        "xGBuildup": float(player_stats.get("xGBuildup", 0)), # xG construction de jeu

        # Compteurs bruts
        "shots":   int(player_stats.get("shots", 0)),
        "goals":   int(player_stats.get("goals", 0)),
        "assists": int(player_stats.get("assists", 0)),
        "minutes": int(player_stats.get("time", 0)),
        "games":   _compute_games(
                       int(player_stats.get("games", 0)),
                       int(player_stats.get("time", 0)),
                   ),

        # Tirs au niveau individuel
        "shot_coords": shot_coords,
    }


# ─────────────────────────────────────────────
# SOURCE 2 : TRANSFERMARKT
# ─────────────────────────────────────────────

# En-têtes HTTP qui imitent un navigateur réel
# (nécessaire pour que Transfermarkt ne bloque pas la requête)
TM_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.transfermarkt.com/",
}

TM_BASE = "https://www.transfermarkt.com"


def _tm_get(url: str, params: dict = None) -> BeautifulSoup:
    """
    Effectue une requête GET sur Transfermarkt et retourne le HTML parsé.
    Gère les erreurs réseau (timeout, code HTTP d'erreur).
    """
    try:
        resp = requests.get(url, params=params, headers=TM_HEADERS, timeout=12)
        resp.raise_for_status()  # lève une exception si code HTTP 4xx ou 5xx
    except requests.Timeout:
        raise ConnectionError(f"Timeout lors de la connexion à {url}")
    except requests.HTTPError as e:
        raise ConnectionError(f"Erreur HTTP {e.response.status_code} sur {url}")
    except requests.RequestException as e:
        raise ConnectionError(f"Erreur réseau : {e}")

    return BeautifulSoup(resp.text, "lxml")


def search_transfermarkt(player_name: str) -> Optional[str]:
    """
    Cherche un joueur sur Transfermarkt via la barre de recherche.
    Retourne l'URL du profil du joueur, ou None si rien n'est trouvé.
    """
    normalized_search = normalize_name(player_name)

    soup = _tm_get(
        f"{TM_BASE}/schnellsuche/ergebnis/schnellsuche",
        params={"query": player_name}
    )

    # Les résultats de joueurs contiennent des liens vers /profil/spieler/
    # On les cherche dans les cellules "hauptlink" des tableaux de résultats
    candidate_links = soup.select(
        "table.items td.hauptlink a[href*='/profil/spieler/']"
    )

    if not candidate_links:
        return None

    # Correspondance exacte par nom normalisé
    for link in candidate_links:
        if normalize_name(link.get_text()) == normalized_search:
            return TM_BASE + link["href"]

    # Si pas de correspondance exacte, on prend le premier résultat
    return TM_BASE + candidate_links[0]["href"]


def scrape_tm_profile(profile_url: str) -> dict:
    """
    Scrape la page de profil d'un joueur sur Transfermarkt.
    Extrait : nom, âge, nationalité, poste, club, valeur, contrat, photo.

    Structure HTML actuelle de Transfermarkt :
    - Infos joueur : div.info-table avec des paires de span
        span.info-table__content--regular  → label  (ex: "Date of birth/Age:")
        span.info-table__content--bold     → valeur  (ex: "12/02/2001 (25)")
    - Valeur marchande : a.data-header__market-value-wrapper
    - Photo : img.data-header__profile-image
    """
    soup = _tm_get(profile_url)

    # ── Nom complet ───────────────────────────────────────────────────────────
    name_el = soup.select_one("h1.data-header__headline-wrapper")
    if name_el:
        # Supprime le numéro de maillot et les badges imbriqués
        for badge in name_el.select("[class]"):
            badge.decompose()
        full_name = re.sub(r"\s+", " ", name_el.get_text(" ", strip=True)).strip()
    else:
        full_name = "N/A"

    # ── Table d'informations ──────────────────────────────────────────────────
    # Transfermarkt utilise des paires de span dans un div.info-table
    # Les spans alternent : label (--regular) / valeur (--bold)
    info = {}
    info_div = soup.select_one("div.info-table")
    if info_div:
        spans = info_div.select("span.info-table__content")
        # On parcourt les spans deux par deux
        for i in range(0, len(spans) - 1, 2):
            label = spans[i].get_text(strip=True).rstrip(":")
            value = spans[i + 1].get_text(" ", strip=True)
            value = re.sub(r"\s+", " ", value).strip()
            info[label] = value

    # ── Valeur marchande ──────────────────────────────────────────────────────
    market_value = "N/A"
    mv_el = soup.select_one("a.data-header__market-value-wrapper")
    if mv_el:
        raw = mv_el.get_text(" ", strip=True)
        market_value = re.split(r"last update", raw, flags=re.IGNORECASE)[0].strip()

    # ── Photo du joueur ───────────────────────────────────────────────────────
    photo_el = soup.select_one("img.data-header__profile-image")
    photo_url = photo_el.get("src", "N/A") if photo_el else "N/A"

    # ── Logo du club ──────────────────────────────────────────────────────────
    # Le logo est dans un <img> à l'intérieur du span "Current club" de l'info-table
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


def fetch_transfermarkt_data(player_name: str) -> dict:
    """
    Point d'entrée principal pour les données Transfermarkt.
    Vérifie d'abord le cache local, puis tente de scraper le profil.
    """
    t0 = time.time()

    # ── 1. Check local cache first ───────────────────────────────────────────
    key   = _cache_key(player_name)
    cache = _load_tm_cache()
    if key in cache:
        print(f"  [timing] TM cache hit pour '{player_name}': {time.time() - t0:.3f}s")
        return cache[key]

    # ── 2. Cache miss — try live scraping ────────────────────────────────────
    print(f"  [timing] TM cache MISS pour '{player_name}' — scraping en cours...")
    print(f"  Recherche de '{player_name}' sur Transfermarkt...")

    profile_url = search_transfermarkt(player_name)

    if profile_url is None:
        raise ValueError(
            f"Joueur '{player_name}' introuvable sur Transfermarkt.\n"
            f"  Astuce : essayez le nom anglais ou une orthographe alternative."
        )

    print(f"  Profil trouvé : {profile_url}")
    data = scrape_tm_profile(profile_url)

    # ── 3. Store in cache ────────────────────────────────────────────────────
    cache[key] = data
    cache[key]["_cached_at"] = datetime.now(timezone.utc).isoformat()
    _save_tm_cache(cache)
    print(f"  Données mises en cache pour '{player_name}'")

    return data


def cache_tm_player(player_name: str, data: dict) -> None:
    """
    Stores TM data for a player in the local cache.
    Called by build_tm_cache.py after fetching via browser.
    """
    key   = _cache_key(player_name)
    cache = _load_tm_cache()
    cache[key] = data
    cache[key]["_cached_at"] = datetime.now(timezone.utc).isoformat()
    _save_tm_cache(cache)


def get_tm_cache_entry(player_name: str) -> dict | None:
    """Returns the cached TM entry for a player, or None if not cached."""
    cache = _load_tm_cache()
    return cache.get(_cache_key(player_name))


# ─────────────────────────────────────────────
# AFFICHAGE DU RAPPORT
# ─────────────────────────────────────────────

def print_report(understat: Optional[dict], tm: Optional[dict]) -> None:
    """
    Affiche un résumé propre et lisible dans le terminal.
    Fonctionne même si l'une des deux sources a échoué.
    """
    SEP = "═" * 62

    # Titre du rapport (on prend le nom disponible)
    display_name = (
        (tm or {}).get("full_name")
        or (understat or {}).get("player_name")
        or "Joueur inconnu"
    )

    print(f"\n{SEP}")
    print(f"  RAPPORT DE SCOUTING — {display_name}")
    print(SEP)

    # ── Profil Transfermarkt ──────────────────────────────────────────────────
    if tm:
        print("\n  PROFIL  (Transfermarkt)")
        print(f"  {'─' * 40}")
        print(f"  Age / Naissance : {tm.get('dob_age', 'N/A')}")
        print(f"  Nationalité     : {tm.get('nationality', 'N/A')}")
        print(f"  Club actuel     : {tm.get('club', 'N/A')}")
        print(f"  Poste           : {tm.get('position', 'N/A')}")
        print(f"  Valeur marchande: {tm.get('market_value', 'N/A')}")
        print(f"  Fin de contrat  : {tm.get('contract_expiry', 'N/A')}")
        if tm.get("photo_url") and tm["photo_url"] != "N/A":
            print(f"  Photo           : {tm.get('photo_url')}")
        print(f"  Fiche complète  : {tm.get('profile_url', 'N/A')}")
    else:
        print("\n  PROFIL  → données Transfermarkt indisponibles")

    # ── Stats Understat ───────────────────────────────────────────────────────
    if understat:
        print(f"\n  STATS SAISON {understat['season']}  (Understat — {understat['league']})")
        print(f"  {'─' * 40}")
        print(f"  Minutes jouées  : {understat['minutes']}")
        print(f"  Buts            : {understat['goals']}")
        print(f"  Passes déc.     : {understat['assists']}")
        print(f"  Tirs tentés     : {understat['shots']}")
        print()
        print(f"  xG              : {understat['xG']:.2f}   (buts attendus)")
        print(f"  npxG            : {understat['npxG']:.2f}   (xG hors pénaltys)")
        print(f"  xA              : {understat['xA']:.2f}   (passes décisives attendues)")
        print(f"  xGChain         : {understat['xGChain']:.2f}   (implication dans les actions)")
        print(f"  xGBuildup       : {understat['xGBuildup']:.2f}   (construction de jeu)")

        # ── Tirs individuels ──────────────────────────────────────────────────
        shots = understat.get("shot_coords", [])
        if shots:
            goals_scored = [s for s in shots if s["result"] == "Goal"]
            print(f"\n  CARTOGRAPHIE DES TIRS  ({len(shots)} tirs, {len(goals_scored)} buts)")
            print(f"  {'─' * 40}")
            print(f"  {'X':>6}  {'Y':>6}  {'xG':>6}  {'Résultat':<18}  Situation")
            print(f"  {'─'*6}  {'─'*6}  {'─'*6}  {'─'*18}  {'─'*15}")

            # On affiche au maximum 15 tirs pour ne pas surcharger l'écran
            display_shots = shots[:15]
            for s in display_shots:
                print(
                    f"  {s['x']:>6.3f}  {s['y']:>6.3f}  {s['xG']:>6.3f}"
                    f"  {s['result']:<18}  {s.get('situation', '')}"
                )
            if len(shots) > 15:
                print(f"  … et {len(shots) - 15} tirs supplémentaires (non affichés)")
        else:
            print("\n  Aucun tir individuel disponible pour cette saison.")
    else:
        print("\n  STATS → données Understat indisponibles")

    print(f"\n{SEP}\n")


# ─────────────────────────────────────────────
# POINT D'ENTRÉE PRINCIPAL
# ─────────────────────────────────────────────

def main(player_name: str) -> None:
    """
    Orchestre la récupération des données depuis les deux sources
    et affiche le rapport final.
    """
    print(f"\n{'─' * 62}")
    print(f"  Football Scouting Pipeline")
    print(f"  Joueur : {player_name}")
    print(f"{'─' * 62}")

    # ── Source 1 : Understat ──────────────────────────────────────────────────
    print("\n[1/2] Understat ...")
    understat_data = None
    try:
        understat_data = fetch_understat_data(
            player_name,
            league="Ligue_1",
            season="2025"
        )
        print("  OK")
    except ValueError as e:
        # Joueur introuvable ou ligue invalide
        print(f"  ERREUR : {e}")
    except ConnectionError as e:
        print(f"  ERREUR RESEAU : {e}")
    except Exception as e:
        print(f"  ERREUR INATTENDUE : {type(e).__name__}: {e}")

    # ── Source 2 : Transfermarkt ──────────────────────────────────────────────
    print("\n[2/2] Transfermarkt ...")
    tm_data = None
    try:
        tm_data = fetch_transfermarkt_data(player_name)
        print("  OK")
    except ValueError as e:
        print(f"  ERREUR : {e}")
    except ConnectionError as e:
        print(f"  ERREUR RESEAU : {e}")
    except Exception as e:
        print(f"  ERREUR INATTENDUE : {type(e).__name__}: {e}")

    # ── Rapport final ─────────────────────────────────────────────────────────
    if understat_data is None and tm_data is None:
        print("\n  Aucune donnée récupérée. Vérifiez le nom du joueur et votre connexion.")
        sys.exit(1)

    print_report(understat_data, tm_data)


if __name__ == "__main__":
    # Lecture du nom depuis la ligne de commande, ou valeur par défaut
    if len(sys.argv) > 1:
        player = " ".join(sys.argv[1:])
    else:
        player = "Khvicha Kvaratskhelia"

    main(player)
