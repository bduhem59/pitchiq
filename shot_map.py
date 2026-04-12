#!/usr/bin/env python3
"""
shot_map.py — Shot map d'un joueur à partir des données Understat

Génère une visualisation des tirs sur une demi-terrain mplsoccer
avec taille proportionnelle au xG et couleurs par résultat.

Usage :
    python3 shot_map.py                                          # Kvaratskhelia (défaut)
    python3 shot_map.py "Ousmane Dembélé" Ligue_1 2024         # autre joueur
    python3 shot_map.py "Erling Haaland" EPL 2023
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from mplsoccer import VerticalPitch

from player_data import fetch_understat_data


# ─────────────────────────────────────────────
# CONFIGURATION VISUELLE
# ─────────────────────────────────────────────

PITCH_COLOR  = "#0d1117"   # fond très sombre (github dark)
LINE_COLOR   = "#30363d"   # lignes terrain discrètes
GRID_COLOR   = "#21262d"   # séparateurs

# Couleurs des tirs selon le résultat
RESULT_COLORS = {
    "Goal":         "#2ecc71",   # vert vif
    "SavedShot":    "#e74c3c",   # rouge
    "BlockedShot":  "#c0392b",   # rouge foncé
    "MissedShots":  "#7f8c8d",   # gris
    "ShotOnPost":   "#f39c12",   # orange (poteau)
}
DEFAULT_COLOR = "#7f8c8d"

# Taille de base : xG * XG_SCALE = surface du cercle en points²
XG_SCALE = 3000

# Transparence des cercles (0=transparent, 1=opaque)
ALPHA_SHOT = 0.75


# ─────────────────────────────────────────────
# CONVERSION DE COORDONNÉES
# ─────────────────────────────────────────────

def understat_to_statsbomb(x_us: float, y_us: float):
    """
    Convertit les coordonnées normalisées Understat (0–1) vers le
    système StatsBomb utilisé par mplsoccer (pitch 120×80).

    Understat :
        X = 0 → but défendu, X = 1 → but attaqué  (direction longitudinale)
        Y = 0 → touche haut,  Y = 1 → touche bas   (direction transversale)

    Pour pitch.scatter sur VerticalPitch(half=True, statsbomb) :
        1er arg (x) = direction longitudinale 0–120 (goal à 120, en haut)
        2e  arg (y) = direction transversale  0–80

    Remarque : les tirs avec X < 0.5 (propre moitié) sont hors du demi-terrain
    affiché mais ne causent pas d'erreur.
    """
    x_sb = x_us * 120    # longitudinal : X Understat → 1er arg pitch.scatter
    y_sb = y_us * 80     # transversal  : Y Understat → 2e  arg pitch.scatter
    return x_sb, y_sb


# ─────────────────────────────────────────────
# GÉNÉRATION DE LA SHOT MAP
# ─────────────────────────────────────────────

def generate_shot_map(
    player_name: str,
    league: str = "Ligue_1",
    season: str = "2024",
    output_dir: str = ".",
) -> str:
    """
    Génère et sauvegarde la shot map.

    Retourne le chemin du fichier PNG créé.
    """
    # ── 1. Récupération des données ───────────────────────────────────────────
    print(f"\nRécupération des données pour '{player_name}'...")
    data = fetch_understat_data(player_name, league=league, season=season)

    shots = data.get("shot_coords", [])
    if not shots:
        raise ValueError(f"Aucun tir trouvé pour '{player_name}' ({league} {season}).")

    goals  = [s for s in shots if s["result"] == "Goal"]
    n_goals = len(goals)
    n_shots = len(shots)

    print(f"  {n_shots} tirs, {n_goals} buts")

    # ── 2. Préparation des données de tracé ───────────────────────────────────
    xs, ys, sizes, colors, edge_colors = [], [], [], [], []

    for shot in shots:
        x_sb, y_sb = understat_to_statsbomb(shot["x"], shot["y"])
        xg         = max(shot["xG"], 0.005)   # taille minimale visible

        xs.append(x_sb)
        ys.append(y_sb)
        sizes.append(xg * XG_SCALE)

        result = shot["result"]
        colors.append(RESULT_COLORS.get(result, DEFAULT_COLOR))

        # Contour blanc pour les buts, sinon couleur atténuée
        edge_colors.append("#ffffff" if result == "Goal" else "#1a1a2a")

    # ── 3. Terrain ────────────────────────────────────────────────────────────
    pitch = VerticalPitch(
        pitch_type="statsbomb",
        half=True,
        pitch_color=PITCH_COLOR,
        line_color=LINE_COLOR,
        line_zorder=2,
        linewidth=1.2,
        goal_type="box",
    )

    fig, ax = pitch.draw(figsize=(8, 8))
    fig.patch.set_facecolor(PITCH_COLOR)
    fig.subplots_adjust(top=0.88, bottom=0.08)

    # ── 4. Tracé des tirs ─────────────────────────────────────────────────────
    pitch.scatter(
        xs, ys,
        s=sizes,
        c=colors,
        edgecolors=edge_colors,
        linewidths=1.2,
        alpha=ALPHA_SHOT,
        zorder=3,
        ax=ax,
    )

    # Cercle supplémentaire pour mettre en valeur les buts
    goal_xs = [xs[i] for i, s in enumerate(shots) if s["result"] == "Goal"]
    goal_ys = [ys[i] for i, s in enumerate(shots) if s["result"] == "Goal"]
    goal_sizes = [sizes[i] for i, s in enumerate(shots) if s["result"] == "Goal"]

    if goal_xs:
        pitch.scatter(
            goal_xs, goal_ys,
            s=[sz * 1.8 for sz in goal_sizes],
            facecolors="none",
            edgecolors="#2ecc71",
            linewidths=1.8,
            alpha=0.5,
            zorder=2,
            ax=ax,
        )

    # ── 5. Titre ──────────────────────────────────────────────────────────────
    display_name = data.get("player_name", player_name)
    league_label = league.replace("_", " ")

    fig.text(
        0.5, 0.955,
        display_name,
        ha="center",
        color="#e6edf3",
        fontsize=17,
        fontweight="bold",
    )
    fig.text(
        0.5, 0.925,
        f"{league_label}  ·  Saison {season}/{int(season)+1}  ·  "
        f"{n_goals} buts sur {n_shots} tirs",
        ha="center",
        color="#8b949e",
        fontsize=9.5,
    )

    # ── 6. Légende ────────────────────────────────────────────────────────────
    legend_items = [
        mpatches.Patch(color=RESULT_COLORS["Goal"],        label="But"),
        mpatches.Patch(color=RESULT_COLORS["SavedShot"],   label="Arrêté"),
        mpatches.Patch(color=RESULT_COLORS["BlockedShot"], label="Contré"),
        mpatches.Patch(color=RESULT_COLORS["MissedShots"], label="Raté"),
        mpatches.Patch(color=RESULT_COLORS["ShotOnPost"],  label="Poteau"),
    ]

    fig.legend(
        handles=legend_items,
        loc="lower center",
        ncol=5,
        frameon=True,
        framealpha=0.3,
        facecolor="#21262d",
        edgecolor="#30363d",
        fontsize=9,
        labelcolor="#e6edf3",
        handlelength=1.2,
        handleheight=0.9,
        borderpad=0.7,
        bbox_to_anchor=(0.5, 0.04),
    )

    fig.text(
        0.5, 0.015,
        "Taille des cercles proportionnelle au xG",
        ha="center",
        color="#6e7681",
        fontsize=7.5,
        style="italic",
    )

    # ── 7. Sauvegarde ─────────────────────────────────────────────────────────
    safe_name = display_name.lower().replace(" ", "_")
    filename  = f"shot_map_{safe_name}_{league.lower()}_{season}.png"
    output    = Path(output_dir) / filename

    plt.savefig(
        output,
        dpi=180,
        bbox_inches="tight",
        facecolor=PITCH_COLOR,
    )
    plt.close(fig)

    print(f"  Shot map sauvegardée : {output}")
    return str(output)


# ─────────────────────────────────────────────
# POINT D'ENTRÉE
# ─────────────────────────────────────────────

def main() -> None:
    args   = sys.argv[1:]
    player = args[0] if len(args) > 0 else "Khvicha Kvaratskhelia"
    league = args[1] if len(args) > 1 else "Ligue_1"
    season = args[2] if len(args) > 2 else "2024"

    generate_shot_map(player, league=league, season=season)


if __name__ == "__main__":
    main()
