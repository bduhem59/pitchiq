#!/usr/bin/env python3
"""
percentiles.py — Calcul des percentiles de joueurs de Ligue 1

Télécharge tous les joueurs de Ligue 1 (saison 2024), calcule les métriques
par 90 minutes et les percentiles par poste.

Usage :
    python3 percentiles.py                      # calcule + sauvegarde percentiles.json
    python3 percentiles.py "Ousmane Dembélé"    # affiche le résumé d'un autre joueur
"""

import json
import sys
from typing import Optional

from understatapi import UnderstatClient


# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

LEAGUE        = "Ligue_1"
SEASON        = "2025"
MIN_MINUTES   = 180   # seuil réduit en cours de saison (300 serait trop restrictif)
OUTPUT_FILE   = "percentiles.json"

# Métriques à calculer par 90 minutes
METRICS_90 = ["npxG", "xG", "xA", "xGChain", "xGBuildup"]

# Mapping du premier code de position → groupe
POSITION_GROUPS = {
    "F":  "attaquants",
    "M":  "milieux",
    "D":  "défenseurs",
    # GK exclu
}


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def get_position_group(position_str: str) -> Optional[str]:
    """
    Extrait le groupe de poste à partir du champ 'position' d'Understat.

    Le champ contient des codes séparés par des espaces, ex : 'F M S', 'D M', 'GK'.
    On prend le PREMIER code comme poste principal.

    Retourne None pour les gardiens ou les positions non reconnues.
    """
    if not position_str:
        return None
    first = position_str.strip().split()[0]
    return POSITION_GROUPS.get(first)  # None si GK ou inconnu


def per90(value: float, minutes: int) -> float:
    """Ramène une statistique cumulée à une base de 90 minutes."""
    if minutes <= 0:
        return 0.0
    return value / minutes * 90


def percentile_rank(value: float, population: list[float]) -> float:
    """
    Calcule le percentile d'une valeur dans une population.

    Utilise la méthode "nombre de valeurs strictement inférieures + 0.5 * égales"
    divisé par la taille totale, exprimé en pourcentage (0–100).

    C'est la méthode "mid" de scipy, cohérente avec l'usage en analytics sportif.
    """
    n = len(population)
    if n == 0:
        return 0.0
    below    = sum(1 for v in population if v < value)
    equal    = sum(1 for v in population if v == value)
    return round((below + 0.5 * equal) / n * 100, 1)


# ─────────────────────────────────────────────
# PIPELINE PRINCIPAL
# ─────────────────────────────────────────────

def fetch_all_players(league: str = LEAGUE, season: str = SEASON) -> list[dict]:
    """Télécharge la liste complète des joueurs via understatapi."""
    print(f"Téléchargement des joueurs ({league}, saison {season})...")
    with UnderstatClient() as understat:
        players = understat.league(league=league).get_player_data(season=season)
    print(f"  {len(players)} joueurs récupérés")
    return players


def build_player_records(raw_players: list[dict]) -> list[dict]:
    """
    Transforme les données brutes Understat en enregistrements enrichis.

    Pour chaque joueur :
      - Convertit les champs numériques
      - Filtre le minimum de minutes
      - Calcule les métriques /90
      - Assigne le groupe de poste
    """
    records = []

    for p in raw_players:
        minutes = int(p.get("time", 0))
        if minutes < MIN_MINUTES:
            continue

        position_str = p.get("position", "")
        group = get_position_group(position_str)
        if group is None:
            continue  # gardiens et positions inconnues exclus

        # Club unique : si transfert en cours de saison, prendre le plus récent
        team_raw = p.get("team_title", "")
        team = team_raw.split(",")[-1].strip() if "," in team_raw else team_raw

        record = {
            "player_name":    p.get("player_name", ""),
            "player_id":      p.get("id", ""),
            "team":           team,
            "position_raw":   position_str,
            "position_group": group,
            "minutes":        minutes,
            "games":          int(p.get("games", 0)),
            "goals":          int(p.get("goals", 0)),
            "assists":        int(p.get("assists", 0)),
        }

        # Statistiques brutes
        for stat in METRICS_90:
            record[stat] = float(p.get(stat, 0))

        # Statistiques /90
        for stat in METRICS_90:
            record[f"{stat}_90"] = round(per90(record[stat], minutes), 4)

        records.append(record)

    print(f"  {len(records)} joueurs retenus (>= {MIN_MINUTES} min, hors GK)")
    return records


def compute_percentiles(records: list[dict]) -> list[dict]:
    """
    Ajoute un champ 'percentiles' à chaque enregistrement.

    Les percentiles sont calculés au sein du groupe de poste du joueur
    (attaquants vs attaquants, milieux vs milieux, etc.).
    """
    # Regroupe les valeurs /90 par poste pour chaque métrique
    group_populations: dict[str, dict[str, list[float]]] = {}

    for group in POSITION_GROUPS.values():
        group_populations[group] = {f"{m}_90": [] for m in METRICS_90}

    for r in records:
        group = r["position_group"]
        for stat in METRICS_90:
            group_populations[group][f"{stat}_90"].append(r[f"{stat}_90"])

    # Calcule le percentile de chaque joueur dans son groupe
    for r in records:
        group = r["position_group"]
        r["percentiles"] = {}
        for stat in METRICS_90:
            key = f"{stat}_90"
            pop = group_populations[group][key]
            r["percentiles"][key] = percentile_rank(r[key], pop)

    return records


def save_json(records: list[dict], path: str = OUTPUT_FILE) -> None:
    """Sauvegarde les enregistrements dans un fichier JSON indenté."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"  Résultats sauvegardés dans '{path}'")


# ─────────────────────────────────────────────
# AFFICHAGE DU RÉSUMÉ
# ─────────────────────────────────────────────

def print_player_summary(player_name: str, records: list[dict]) -> None:
    """
    Affiche un résumé formaté des percentiles d'un joueur.
    Recherche par correspondance partielle insensible à la casse.
    """
    name_lower = player_name.lower()
    matches = [
        r for r in records
        if name_lower in r["player_name"].lower()
    ]

    if not matches:
        print(f"\n  Joueur '{player_name}' introuvable dans les données filtrées.")
        print("  (Vérifiez l'orthographe ou les critères de filtrage.)")
        return

    r = matches[0]
    SEP = "═" * 58

    print(f"\n{SEP}")
    print(f"  PERCENTILES — {r['player_name']}")
    print(f"  {r['team']}  |  {r['position_group'].upper()}  |  {r['minutes']} min")
    print(SEP)
    print(f"\n  {'Métrique':<20} {'Valeur/90':>10} {'Percentile':>12}")
    print(f"  {'─'*20}  {'─'*10}  {'─'*12}")

    for stat in METRICS_90:
        key   = f"{stat}_90"
        val   = r[key]
        pct   = r["percentiles"][key]
        bar   = "█" * int(pct / 10)   # barre visuelle sur 10 blocs
        print(f"  {key:<20} {val:>10.3f}  {pct:>6.1f}%  {bar}")

    print(f"\n{SEP}\n")


# ─────────────────────────────────────────────
# POINT D'ENTRÉE
# ─────────────────────────────────────────────

def main(test_player: str = "Khvicha Kvaratskhelia") -> None:
    # 1. Téléchargement
    raw_players = fetch_all_players()

    # 2. Construction des enregistrements (filtre + /90)
    print("\nCalcul des métriques /90...")
    records = build_player_records(raw_players)

    # 3. Calcul des percentiles par poste
    print("Calcul des percentiles par poste...")
    records = compute_percentiles(records)

    # Résumé par groupe
    for group in POSITION_GROUPS.values():
        count = sum(1 for r in records if r["position_group"] == group)
        print(f"  {group:<15}: {count} joueurs")

    # 4. Sauvegarde JSON
    print(f"\nSauvegarde...")
    save_json(records)

    # 5. Résumé test
    print(f"\nRésumé pour '{test_player}' :")
    print_player_summary(test_player, records)


if __name__ == "__main__":
    player = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Khvicha Kvaratskhelia"
    main(test_player=player)
