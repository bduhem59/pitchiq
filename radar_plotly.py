#!/usr/bin/env python3
"""
radar_plotly.py — Radar chart interactif Plotly avec ligne de référence Ligue 1
"""

import json
from pathlib import Path

import plotly.graph_objects as go
from understatapi import UnderstatClient

from player_data import fetch_understat_data

PERCENTILES_FILE = "percentiles.json"
LEAGUE           = "Ligue_1"
SEASON           = "2024"
MIN_MINUTES      = 300

BG_COLOR = "#0d1117"

AXES = [
    {"key": "npxG_90",      "label": "npxG/90"},
    {"key": "xG_90",        "label": "xG/90"},
    {"key": "xA_90",        "label": "xA/90"},
    {"key": "xGChain_90",   "label": "xGChain/90"},
    {"key": "xGBuildup_90", "label": "xGBuildup/90"},
    {"key": "efficiency",   "label": "Efficiency\n(goals/xG)"},
]

# Maps Understat position_group → English plural
POS_EN = {
    "attaquants": "forwards",
    "milieux":    "midfielders",
    "défenseurs": "defenders",
}


def _load_records(path: str = PERCENTILES_FILE) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _find_player(records: list[dict], name: str) -> dict:
    nl = name.lower()
    matches = [r for r in records if nl in r["player_name"].lower()]
    if not matches:
        raise ValueError(f"Player '{name}' not found in {PERCENTILES_FILE}.")
    return matches[0]


def _percentile_rank(value: float, population: list[float]) -> float:
    n = len(population)
    if not n:
        return 0.0
    below = sum(1 for v in population if v < value)
    equal = sum(1 for v in population if v == value)
    return round((below + 0.5 * equal) / n * 100, 1)


def _rank_in_population(value: float, population: list[float]) -> int:
    """Rank 1 = best (highest value)."""
    return sum(1 for v in population if v > value) + 1


def _fetch_efficiency_population(
    league: str, season: str, position_group: str
) -> dict[str, float]:
    GROUPS = {"F": "attaquants", "M": "milieux", "D": "défenseurs"}
    with UnderstatClient() as u:
        raw = u.league(league=league).get_player_data(season=season)
    out: dict[str, float] = {}
    for p in raw:
        if int(p.get("time", 0)) < MIN_MINUTES:
            continue
        pos_str = p.get("position", "")
        first   = pos_str.strip().split()[0] if pos_str.strip() else ""
        if GROUPS.get(first) != position_group:
            continue
        xg = float(p.get("xG", 0))
        if xg <= 0:
            continue
        out[p["id"]] = min(int(p.get("goals", 0)) / xg, 1.5)
    return out


def generate_radar_plotly(
    player_name: str = "Khvicha Kvaratskhelia",
    league: str = LEAGUE,
    season: str = SEASON,
) -> go.Figure:
    records   = _load_records()
    player    = _find_player(records, player_name)
    pos_group = player["position_group"]
    display   = player["player_name"]
    pos_en    = POS_EN.get(pos_group, pos_group)

    us      = fetch_understat_data(display, league=league, season=season)
    xg_tot  = us["xG"]
    eff_val = min(us["goals"] / xg_tot, 1.5) if xg_tot > 0 else 0.0

    eff_pop_map = _fetch_efficiency_population(league, season, pos_group)
    eff_pop     = list(eff_pop_map.values())
    if player["player_id"] not in eff_pop_map:
        eff_pop.append(eff_val)
    eff_pct = _percentile_rank(eff_val, eff_pop)

    pcts   = player["percentiles"]
    raw_90 = {k: player.get(k, 0.0) for k in
              ["npxG_90", "xG_90", "xA_90", "xGChain_90", "xGBuildup_90"]}

    percentile_vals = [
        pcts["npxG_90"], pcts["xG_90"], pcts["xA_90"],
        pcts["xGChain_90"], pcts["xGBuildup_90"], eff_pct,
    ]
    raw_vals = [
        raw_90["npxG_90"], raw_90["xG_90"], raw_90["xA_90"],
        raw_90["xGChain_90"], raw_90["xGBuildup_90"], eff_val,
    ]

    same_pos = [r for r in records if r.get("position_group") == pos_group]
    n_pos    = len(same_pos)

    axis_labels = [ax["label"] for ax in AXES]

    hover_texts = []
    for ax, pv, rv in zip(AXES, percentile_vals, raw_vals):
        if ax["key"] == "efficiency":
            val_str = f"{rv:.0%}"
            rank    = _rank_in_population(rv, eff_pop)
            total   = len(eff_pop)
        else:
            val_str = f"{rv:.3f}"
            pop     = [r.get(ax["key"], 0.0) for r in same_pos]
            rank    = _rank_in_population(rv, pop)
            total   = n_pos
        hover_texts.append(
            f"<b>{ax['label']}</b><br>"
            f"Value /90: {val_str}<br>"
            f"Percentile: {pv:.0f}th<br>"
            f"Rank: #{rank} / {total} {pos_en}"
        )

    r_closed     = percentile_vals + [percentile_vals[0]]
    theta_closed = axis_labels     + [axis_labels[0]]
    hov_closed   = hover_texts     + [hover_texts[0]]

    fig = go.Figure()

    # Reference line — Ligue 1 average (50th percentile)
    fig.add_trace(go.Scatterpolar(
        r=[50] * len(axis_labels),
        theta=axis_labels,
        fill=None,
        mode="lines",
        line=dict(color="#555566", width=1.5, dash="dash"),
        name="Ligue 1 avg. (50th %ile)",
        hoverinfo="skip",
    ))

    # Player polygon
    fig.add_trace(go.Scatterpolar(
        r=r_closed,
        theta=theta_closed,
        fill="toself",
        fillcolor="rgba(56,189,248,0.18)",
        mode="lines+markers",
        line=dict(color="#38bdf8", width=2.5),
        marker=dict(color="#38bdf8", size=7,
                    line=dict(color=BG_COLOR, width=1.5)),
        name=display,
        text=hov_closed,
        hovertemplate="%{text}<extra></extra>",
    ))

    league_label = league.replace("_", " ")
    fig.update_layout(
        polar=dict(
            bgcolor=BG_COLOR,
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickvals=[25, 50, 75, 100],
                tickfont=dict(color="#8b949e", size=8, family="Inter"),
                gridcolor="#252d3a",
                linecolor="#252d3a",
            ),
            angularaxis=dict(
                tickfont=dict(color="#e6edf3", size=9, family="Inter"),
                linecolor="#252d3a",
                gridcolor="#252d3a",
            ),
        ),
        paper_bgcolor=BG_COLOR,
        title=dict(
            text=f"<b>{display}</b>  ·  {pos_en.capitalize()}  ·  {player['minutes']} min",
            x=0.5,
            xanchor="center",
            font=dict(color="#e6edf3", size=13, family="Inter"),
        ),
        legend=dict(
            bgcolor="rgba(13,17,23,0.85)",
            bordercolor="#30363d",
            borderwidth=1,
            font=dict(color="#e6edf3", size=10, family="Inter"),
            orientation="h",
            x=0.5, xanchor="center",
            y=-0.06, yanchor="top",
        ),
        margin=dict(t=100, l=20, r=20, b=20),
        height=520,
    )

    return fig
