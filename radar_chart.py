#!/usr/bin/env python3
"""
radar_chart.py — Radar chart de percentiles pour un joueur de Ligue 1

Sources :
  - percentiles.json → 5 métriques /90 + percentiles par poste
  - understatapi      → goals pour le calcul de l'efficacité (6e axe)

Usage :
    python3 radar_chart.py                                  # Kvaratskhelia
    python3 radar_chart.py "Ousmane Dembélé" Ligue_1 2024
"""

import json
import sys
import math
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
import numpy as np
from understatapi import UnderstatClient

from player_data import fetch_understat_data


# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

PERCENTILES_FILE = "percentiles.json"
LEAGUE           = "Ligue_1"
SEASON           = "2024"
MIN_MINUTES      = 300

BG_COLOR    = "#0d1117"
RING_COLOR  = "#161b22"
SPOKE_COLOR = "#30363d"
FILL_COLOR  = "#38bdf8"
FILL_ALPHA  = 0.25
STROKE_COLOR= "#38bdf8"
LABEL_COLOR = "#e6edf3"
VALUE_COLOR = "#94e2d5"   # teal clair pour les valeurs /90
PCT_COLOR   = "#8b949e"   # gris pour les percentiles

RING_TICKS  = [25, 50, 75, 100]   # anneaux affichés

# Définition des 6 axes du radar
AXES = [
    {"key": "npxG_90",     "label": "npxG/90",      "fmt": ".3f"},
    {"key": "xG_90",       "label": "xG/90",         "fmt": ".3f"},
    {"key": "xA_90",       "label": "xA/90",         "fmt": ".3f"},
    {"key": "xGChain_90",  "label": "xGChain/90",    "fmt": ".3f"},
    {"key": "xGBuildup_90","label": "xGBuildup/90",  "fmt": ".3f"},
    {"key": "efficiency",  "label": "Efficacité\n(buts/xG)", "fmt": ".0%"},
]
N = len(AXES)


# ─────────────────────────────────────────────
# DONNÉES
# ─────────────────────────────────────────────

def load_percentiles_json(path: str = PERCENTILES_FILE) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_player(records: list[dict], name: str) -> dict:
    name_lower = name.lower()
    matches = [r for r in records if name_lower in r["player_name"].lower()]
    if not matches:
        raise ValueError(
            f"Joueur '{name}' introuvable dans {PERCENTILES_FILE}.\n"
            "  Assurez-vous qu'il est dans le fichier (>= 300 min, hors GK)."
        )
    return matches[0]


def fetch_efficiency_percentiles(
    league: str,
    season: str,
    position_group: str,
) -> tuple[dict[str, float], float]:
    """
    Récupère tous les joueurs de la ligue et calcule les percentiles
    d'efficacité (buts / xG, plafonné à 1.5) par poste.

    Retourne (dict player_id → efficiency_ratio, max_efficiency_used).
    """
    POSITION_GROUPS = {"F": "attaquants", "M": "milieux", "D": "défenseurs"}

    print(f"  Calcul des percentiles d'efficacité ({league} {season})...")
    with UnderstatClient() as u:
        raw = u.league(league=league).get_player_data(season=season)

    efficiencies: dict[str, float] = {}   # id → efficiency capped

    for p in raw:
        minutes = int(p.get("time", 0))
        if minutes < MIN_MINUTES:
            continue
        pos_str = p.get("position", "")
        first   = pos_str.strip().split()[0] if pos_str.strip() else ""
        if POSITION_GROUPS.get(first) != position_group:
            continue
        xg = float(p.get("xG", 0))
        if xg <= 0:
            continue
        goals = int(p.get("goals", 0))
        eff   = min(goals / xg, 1.5)
        efficiencies[p["id"]] = eff

    return efficiencies


def percentile_rank(value: float, population: list[float]) -> float:
    n = len(population)
    if n == 0:
        return 0.0
    below = sum(1 for v in population if v < value)
    equal = sum(1 for v in population if v == value)
    return round((below + 0.5 * equal) / n * 100, 1)


# ─────────────────────────────────────────────
# RADAR CHART
# ─────────────────────────────────────────────

def _spoke_angle(i: int, n: int) -> float:
    """Angle en radians pour le ième rayon (départ en haut, sens horaire)."""
    return math.pi / 2 - 2 * math.pi * i / n


def _polar_to_xy(r: float, theta: float) -> tuple[float, float]:
    return r * math.cos(theta), r * math.sin(theta)


def _label_anchor(theta: float) -> tuple[str, str]:
    """Alignement horizontal/vertical du label selon la position angulaire."""
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    ha = "center" if abs(cos_t) < 0.35 else ("left" if cos_t > 0 else "right")
    va = "center" if abs(sin_t) < 0.35 else ("bottom" if sin_t > 0 else "top")
    return ha, va


def generate_radar(
    player_name: str = "Khvicha Kvaratskhelia",
    league: str = LEAGUE,
    season: str = SEASON,
    output_dir: str = ".",
) -> str:
    """Génère et sauvegarde le radar chart. Retourne le chemin du PNG."""

    # ── 1. Charger percentiles.json ───────────────────────────────────────────
    print("Chargement de percentiles.json...")
    records = load_percentiles_json()
    player  = find_player(records, player_name)
    position_group = player["position_group"]
    display_name   = player["player_name"]

    print(f"  Trouvé : {display_name} ({player['team']}, {position_group})")

    # ── 2. Données d'efficacité ───────────────────────────────────────────────
    print("Récupération des données d'efficacité...")
    understat_data = fetch_understat_data(display_name, league=league, season=season)
    goals  = understat_data["goals"]
    xg_tot = understat_data["xG"]

    if xg_tot > 0:
        player_eff = min(goals / xg_tot, 1.5)
    else:
        player_eff = 0.0

    eff_population_map = fetch_efficiency_percentiles(league, season, position_group)
    eff_population     = list(eff_population_map.values())

    player_id = player["player_id"]
    if player_id not in eff_population_map:
        eff_population.append(player_eff)
    eff_pct = percentile_rank(player_eff, eff_population)

    # ── 3. Valeurs radar ──────────────────────────────────────────────────────
    pcts   = player["percentiles"]
    raw_90 = {k: player.get(k, 0.0) for k in
              ["npxG_90", "xG_90", "xA_90", "xGChain_90", "xGBuildup_90"]}

    percentile_values = [
        pcts["npxG_90"],
        pcts["xG_90"],
        pcts["xA_90"],
        pcts["xGChain_90"],
        pcts["xGBuildup_90"],
        eff_pct,
    ]
    raw_values = [
        raw_90["npxG_90"],
        raw_90["xG_90"],
        raw_90["xA_90"],
        raw_90["xGChain_90"],
        raw_90["xGBuildup_90"],
        player_eff,         # ratio brut (e.g. 2.27 = 227%)
    ]

    # ── 4. Initialiser la figure ──────────────────────────────────────────────
    fig = plt.figure(figsize=(9, 10), facecolor=BG_COLOR)

    # Zone titre / sous-titre
    ax_title = fig.add_axes([0, 0.88, 1, 0.12], facecolor=BG_COLOR)
    ax_title.axis("off")

    league_label = league.replace("_", " ")
    ax_title.text(
        0.5, 0.72, display_name,
        ha="center", va="center",
        color=LABEL_COLOR, fontsize=20, fontweight="bold",
        transform=ax_title.transAxes,
    )
    ax_title.text(
        0.5, 0.2,
        f"{player['team']}  ·  {position_group.capitalize()}  ·  "
        f"{league_label} {season}/{int(season)+1}  ·  {player['minutes']} min",
        ha="center", va="center",
        color=PCT_COLOR, fontsize=9.5,
        transform=ax_title.transAxes,
    )

    # Zone radar (carrée, centrée)
    ax = fig.add_axes([0.08, 0.10, 0.84, 0.78], facecolor=BG_COLOR)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-1.55, 1.55)
    ax.set_ylim(-1.55, 1.55)

    # ── 5. Anneaux de grille ──────────────────────────────────────────────────
    for tick in RING_TICKS:
        r = tick / 100
        circle = plt.Circle(
            (0, 0), r,
            fill=True,
            facecolor=RING_COLOR if tick % 50 == 0 else BG_COLOR,
            edgecolor=SPOKE_COLOR,
            linewidth=0.8,
            zorder=1,
        )
        ax.add_patch(circle)
        # Étiquette de l'anneau à 0° (droite, entre deux rayons i=1 et i=2)
        if tick < 100:
            ax.text(
                r * math.cos(0) + 0.02,
                r * math.sin(0),
                f"{tick}",
                color=PCT_COLOR, fontsize=6.5, ha="left", va="center",
                zorder=5,
            )

    # ── 6. Rayons (spokes) ────────────────────────────────────────────────────
    angles = [_spoke_angle(i, N) for i in range(N)]

    for theta in angles:
        x, y = _polar_to_xy(1.0, theta)
        ax.plot([0, x], [0, y], color=SPOKE_COLOR, linewidth=0.9, zorder=2)

    # ── 7. Polygone du joueur ─────────────────────────────────────────────────
    xs = [pv / 100 * math.cos(th) for pv, th in zip(percentile_values, angles)]
    ys = [pv / 100 * math.sin(th) for pv, th in zip(percentile_values, angles)]
    xs.append(xs[0])
    ys.append(ys[0])

    ax.fill(xs, ys, color=FILL_COLOR, alpha=FILL_ALPHA, zorder=3)
    ax.plot(xs, ys, color=STROKE_COLOR, linewidth=2.0, zorder=4)

    for x, y in zip(xs[:-1], ys[:-1]):
        ax.scatter(x, y, color=STROKE_COLOR, s=55, zorder=5, edgecolors=BG_COLOR, linewidths=1)

    # ── 8. Labels des axes ────────────────────────────────────────────────────
    # Chaque label est un bloc texte positionné à l'extrémité du rayon.
    # On sépare le nom (blanc, gras) et les stats (couleur, taille réduite).
    LABEL_R = 1.13   # rayon du nom de la métrique

    for axis_def, pv, rv, theta in zip(AXES, percentile_values, raw_values, angles):
        ha, va = _label_anchor(theta)

        lx, ly = _polar_to_xy(LABEL_R, theta)

        if axis_def["key"] == "efficiency":
            real_str = f"{rv:.0%}"
        else:
            real_str = f"{rv:.3f}"

        # Bloc unique : nom + valeur + percentile, multi-ligne
        label_text = axis_def["label"]
        stats_text = f"{real_str}  ·  {pv:.0f}e %ile"

        ax.text(
            lx, ly,
            label_text,
            ha=ha, va=va,
            color=LABEL_COLOR,
            fontsize=8.5, fontweight="bold",
            zorder=6,
            multialignment="center",
            linespacing=1.3,
        )

        # Décale les stats dans la direction opposée au centre
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        # Offset en coords de données (pas en pixels) — adapté à la taille de l'axe
        dx = math.copysign(0.005, cos_t) if abs(cos_t) > 0.2 else 0
        dy = math.copysign(0.13, sin_t)  if abs(sin_t) > 0.2 else -0.13

        ax.text(
            lx + dx, ly + dy,
            stats_text,
            ha=ha, va=va,
            color=VALUE_COLOR,
            fontsize=7.5,
            zorder=6,
            multialignment="center",
        )

    # ── 9. Note de bas de page ────────────────────────────────────────────────
    ax_foot = fig.add_axes([0, 0, 1, 0.10], facecolor=BG_COLOR)
    ax_foot.axis("off")
    ax_foot.text(
        0.5, 0.65,
        f"Percentiles calculés parmi les {position_group} de {league_label} {season}/{int(season)+1}"
        f" (>= {MIN_MINUTES} min).",
        ha="center", va="center", color=PCT_COLOR, fontsize=7.5,
        transform=ax_foot.transAxes,
    )
    ax_foot.text(
        0.5, 0.25,
        "Efficacité = buts / xG, plafonnée à 150%.   Source : Understat.",
        ha="center", va="center", color=PCT_COLOR, fontsize=7.5,
        style="italic", transform=ax_foot.transAxes,
    )

    # ── 10. Sauvegarde ───────────────────────────────────────────────────────
    safe_name = display_name.lower().replace(" ", "_")
    filename  = f"radar_{safe_name}_{league.lower()}_{season}.png"
    output    = Path(output_dir) / filename

    plt.savefig(output, dpi=180, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)
    print(f"  Radar chart sauvegardé : {output}")
    return str(output)


# ─────────────────────────────────────────────
# POINT D'ENTRÉE
# ─────────────────────────────────────────────

def main() -> None:
    args   = sys.argv[1:]
    player = args[0] if args else "Khvicha Kvaratskhelia"
    league = args[1] if len(args) > 1 else LEAGUE
    season = args[2] if len(args) > 2 else SEASON
    generate_radar(player, league=league, season=season)


if __name__ == "__main__":
    main()
