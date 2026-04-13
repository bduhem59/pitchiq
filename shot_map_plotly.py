#!/usr/bin/env python3
"""
shot_map_plotly.py — Shot map interactive Plotly pour un joueur Understat
"""

import numpy as np
import plotly.graph_objects as go

from player_data import fetch_understat_data

PITCH_BG = "#0d1117"
LINE_COLOR = "#30363d"

RESULT_COLORS = {
    "Goal":        "#2ecc71",
    "SavedShot":   "#e74c3c",
    "BlockedShot": "#c0392b",
    "MissedShots": "#7f8c8d",
    "ShotOnPost":  "#f39c12",
}
RESULT_LABELS = {
    "Goal":        "Goal",
    "SavedShot":   "Saved",
    "BlockedShot": "Blocked",
    "MissedShots": "Missed",
    "ShotOnPost":  "Post",
}
SITUATION_LABELS = {
    "OpenPlay":        "Jeu ouvert",
    "FromCorner":      "Corner",
    "SetPiece":        "Coup de pied arrêté",
    "DirectFreekick":  "Coup franc direct",
    "Penalty":         "Pénalty",
}
DEFAULT_COLOR = "#7f8c8d"


def _classify_zone(x_sb: float, y_sb: float) -> str:
    if x_sb >= 114 and 30 <= y_sb <= 50:
        return "six_yard"
    elif x_sb >= 102 and 18 <= y_sb <= 62:
        return "penalty_area"
    return "outside_box"


ZONE_LABELS = {
    "six_yard":    "Surface de but",
    "penalty_area": "Surface de réparation",
    "outside_box": "Hors surface",
}


def _add_pitch_shapes(fig: go.Figure) -> None:
    """Draws the half-pitch:
       plot_x = y_sb (transversal 0-80), plot_y = x_sb (longitudinal 60→120 = goal at top)
    """
    def rect(x0, y0, x1, y1, fill="rgba(0,0,0,0)", lw=1.5):
        fig.add_shape(type="rect", x0=x0, y0=y0, x1=x1, y1=y1,
                      fillcolor=fill,
                      line=dict(color=LINE_COLOR, width=lw))

    rect(0, 60, 80, 120)                                          # half-pitch outline
    fig.add_shape(type="line", x0=0, y0=60, x1=80, y1=60,
                  line=dict(color=LINE_COLOR, width=1.5))          # halfway line
    rect(18, 102, 62, 120, fill="rgba(0,80,160,0.07)")            # penalty area (18-yd)
    rect(30, 114, 50, 120, fill="rgba(0,160,255,0.09)")           # six-yard box
    rect(36, 120, 44, 122, fill="rgba(255,255,255,0.04)")         # goal
    fig.add_trace(go.Scatter(                                      # penalty spot
        x=[40], y=[108], mode="markers",
        marker=dict(color=LINE_COLOR, size=4),
        hoverinfo="skip", showlegend=False,
    ))
    theta = np.linspace(0, np.pi, 60)                             # centre arc
    fig.add_trace(go.Scatter(
        x=40 + 10 * np.cos(theta),
        y=60 + 10 * np.sin(theta),
        mode="lines",
        line=dict(color=LINE_COLOR, width=1.5),
        hoverinfo="skip", showlegend=False,
    ))


def generate_shot_map_plotly(
    player_name: str,
    league: str = "Ligue_1",
    season: str = "2024",
) -> go.Figure:
    data = fetch_understat_data(player_name, league=league, season=season)
    shots = data.get("shot_coords", [])
    if not shots:
        raise ValueError(f"No shots found for '{player_name}' ({league} {season}).")

    display_name = data.get("player_name", player_name)

    for s in shots:
        s["x_sb"] = s["x"] * 120
        s["y_sb"] = s["y"] * 80
        s["zone"] = _classify_zone(s["x_sb"], s["y_sb"])

    total = len(shots)
    zone_counts = {"six_yard": 0, "penalty_area": 0, "outside_box": 0}
    for s in shots:
        zone_counts[s["zone"]] += 1

    fig = go.Figure()
    _add_pitch_shapes(fig)

    result_groups: dict[str, list] = {}
    for s in shots:
        result_groups.setdefault(s["result"], []).append(s)

    for result, group in result_groups.items():
        color = RESULT_COLORS.get(result, DEFAULT_COLOR)
        label = RESULT_LABELS.get(result, result)

        plot_x = [s["y_sb"] for s in group]
        plot_y = [s["x_sb"] for s in group]
        sizes  = [max(s["xG"], 0.005) * 38 + 6 for s in group]

        hover_texts = []
        for s in group:
            # ── Contexte match ───────────────────────────────────────────
            h_team  = s.get("h_team", "")
            a_team  = s.get("a_team", "")
            h_goals = s.get("h_goals")
            a_goals = s.get("a_goals")
            h_a     = s.get("h_a", "")

            opponent = a_team if h_a == "h" else h_team if h_a == "a" else ""

            if h_goals is not None and a_goals is not None and h_team and a_team:
                score_str = f"{h_team} {h_goals}–{a_goals} {a_team}"
            else:
                score_str = ""

            if opponent and score_str:
                match_line = f"c. {opponent}  ({score_str})"
            elif opponent:
                match_line = f"c. {opponent}"
            else:
                match_line = ""

            minute    = s.get("minute", "?")
            situation_raw = s.get("situation", "")
            situation = SITUATION_LABELS.get(situation_raw, situation_raw)
            header    = f"<b>{minute}'  {match_line}</b>" if match_line else f"<b>{minute}'</b>"

            hover_texts.append(
                f"{header}<br>"
                f"xG: {s['xG']:.2f}  —  {label}<br>"
                f"{situation}"
            )

        fig.add_trace(go.Scatter(
            x=plot_x, y=plot_y,
            mode="markers",
            name=label,
            marker=dict(
                color=color,
                size=sizes,
                opacity=0.82,
                sizemode="diameter",
                line=dict(
                    width=1.5,
                    color="#ffffff" if result == "Goal" else "#1a1a2a",
                ),
            ),
            text=hover_texts,
            hovertemplate="%{text}<extra></extra>",
        ))

    pct_six     = zone_counts["six_yard"]    / total * 100
    pct_penalty = zone_counts["penalty_area"]/ total * 100
    pct_outside = zone_counts["outside_box"] / total * 100

    for ann in [
        dict(x=40,  y=117.5, text=f"<b>Surface de but</b><br>{pct_six:.0f}%",
             font=dict(color="#00d4ff", size=8)),
        dict(x=14,  y=111,   text=f"<b>Surface de réparation</b><br>{pct_penalty:.0f}%",
             font=dict(color="#7ecfff", size=8)),
        dict(x=7,   y=82,    text=f"<b>Hors surface</b><br>{pct_outside:.0f}%",
             font=dict(color="#8b949e", size=8)),
    ]:
        fig.add_annotation(**ann, showarrow=False,
                           bgcolor="rgba(0,0,0,0.45)", borderpad=3)

    n_goals = len(result_groups.get("Goal", []))
    league_label = league.replace("_", " ")

    fig.update_layout(
        title=dict(
            text=f"<b>{display_name}</b>  ·  {league_label}  ·  {n_goals} buts / {total} tirs",
            x=0.5,
            xanchor="center",
            font=dict(color="#e6edf3", size=13, family="Inter"),
        ),
        paper_bgcolor=PITCH_BG,
        plot_bgcolor=PITCH_BG,
        xaxis=dict(range=[-2, 82],  showgrid=False, zeroline=False, visible=False),
        yaxis=dict(range=[58, 124], showgrid=False, zeroline=False, visible=False,
                   scaleanchor="x", scaleratio=1),
        legend=dict(
            bgcolor="rgba(13,17,23,0.85)",
            bordercolor=LINE_COLOR,
            borderwidth=1,
            font=dict(color="#e6edf3", size=10, family="Inter"),
            orientation="h",
            x=0.5, xanchor="center",
            y=-0.03, yanchor="top",
        ),
        margin=dict(t=100, l=20, r=20, b=20),
        height=520,
    )

    return fig
