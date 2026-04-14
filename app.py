#!/usr/bin/env python3
"""
app.py — PitchIQ : Football Intelligence Platform
"""

import json
import urllib.parse
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

from player_data import fetch_understat_data, fetch_transfermarkt_data
from shot_map_plotly import generate_shot_map_plotly
from radar_plotly import generate_radar_plotly

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="PitchIQ",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

LEAGUE  = "Ligue_1"
SEASON  = "2025"

METRICS = [
    ("xG_90",        "xG / 90",
     "Buts espérés par 90 min selon la qualité des tirs tentés"),
    ("npxG_90",      "npxG / 90",
     "xG hors pénalties — mesure la menace offensive sans influence des pénos"),
    ("xA_90",        "xA / 90",
     "Passes décisives espérées par 90 min — qualité des passes menant à un tir"),
    ("xGChain_90",   "xGChain / 90",
     "xG de toutes les actions offensives impliquant le joueur par 90 min"),
    ("xGBuildup_90", "xGBuildup / 90",
     "Contribution à la construction offensive en amont des tirs par 90 min"),
]

TM_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.transfermarkt.com/",
}

POS_SINGULAR: dict[str, str] = {
    "attaquants": "Attaquant",
    "milieux":    "Milieu",
    "défenseurs": "Défenseur",
}
POS_FILTER_MAP: dict[str, str] = {v: k for k, v in POS_SINGULAR.items()}

POSITION_MAP: dict[str, str] = {
    "Attack - Centre-Forward":       "Avant-centre",
    "Attack - Left Winger":          "Ailier gauche",
    "Attack - Right Winger":         "Ailier droit",
    "Attack - Second Striker":       "Second attaquant",
    "Midfield - Central Midfield":   "Milieu central",
    "Midfield - Attacking Midfield": "Milieu offensif",
    "Midfield - Defensive Midfield": "Milieu défensif",
    "Midfield - Right Midfield":     "Milieu droit",
    "Midfield - Left Midfield":      "Milieu gauche",
    "Midfield - Right Wing":         "Ailier droit",
    "Midfield - Left Wing":          "Ailier gauche",
    "Defence - Centre-Back":         "Défenseur central",
    "Defence - Left-Back":           "Latéral gauche",
    "Defence - Right-Back":          "Latéral droit",
    "Defence - Left Wing-Back":      "Piston gauche",
    "Defence - Right Wing-Back":     "Piston droit",
    "Defence - Sweeper":             "Libéro",
    "Goalkeeper":                    "Gardien",
}

NATIONALITY_FLAGS: dict[str, str] = {
    "France": "🇫🇷", "Spain": "🇪🇸", "Germany": "🇩🇪", "Portugal": "🇵🇹",
    "Italy": "🇮🇹", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Netherlands": "🇳🇱", "Belgium": "🇧🇪",
    "Switzerland": "🇨🇭", "Austria": "🇦🇹", "Croatia": "🇭🇷", "Serbia": "🇷🇸",
    "Poland": "🇵🇱", "Czech Republic": "🇨🇿", "Slovakia": "🇸🇰", "Hungary": "🇭🇺",
    "Denmark": "🇩🇰", "Sweden": "🇸🇪", "Norway": "🇳🇴", "Finland": "🇫🇮",
    "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "Wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿", "Ireland": "🇮🇪", "Turkey": "🇹🇷",
    "Greece": "🇬🇷", "Romania": "🇷🇴", "Bulgaria": "🇧🇬", "Ukraine": "🇺🇦",
    "Russia": "🇷🇺", "Georgia": "🇬🇪", "Armenia": "🇦🇲", "Albania": "🇦🇱",
    "Bosnia-Herzegovina": "🇧🇦", "Montenegro": "🇲🇪", "North Macedonia": "🇲🇰",
    "Slovenia": "🇸🇮", "Kosovo": "🇽🇰", "Iceland": "🇮🇸",
    "Brazil": "🇧🇷", "Argentina": "🇦🇷", "Colombia": "🇨🇴", "Uruguay": "🇺🇾",
    "Chile": "🇨🇱", "Peru": "🇵🇪", "Ecuador": "🇪🇨", "Paraguay": "🇵🇾",
    "Mexico": "🇲🇽", "United States": "🇺🇸", "Canada": "🇨🇦",
    "Morocco": "🇲🇦", "Algeria": "🇩🇿", "Tunisia": "🇹🇳", "Senegal": "🇸🇳",
    "Ivory Coast": "🇨🇮", "Ghana": "🇬🇭", "Nigeria": "🇳🇬", "Cameroon": "🇨🇲",
    "Mali": "🇲🇱", "Guinea": "🇬🇳", "DR Congo": "🇨🇩", "Congo": "🇨🇬",
    "Gabon": "🇬🇦", "Egypt": "🇪🇬", "Burkina Faso": "🇧🇫",
    "Guinea-Bissau": "🇬🇼", "Comoros": "🇰🇲", "Cape Verde": "🇨🇻",
    "Gambia": "🇬🇲", "Japan": "🇯🇵", "South Korea": "🇰🇷", "Australia": "🇦🇺",
}


def _normalize_position(pos: str) -> str:
    if pos in POSITION_MAP:
        return POSITION_MAP[pos]
    if " - " in pos:
        return pos.split(" - ", 1)[1]
    return pos


def _nat_with_flag(nat: str) -> str:
    """Handle single or space-separated multi-nationality strings.
    e.g. "Spain Guinea-Bissau" → "🇪🇸 Spain / 🇬🇼 Guinea-Bissau"
    """
    if not nat or nat in ("—", "N/A"):
        return nat
    # Fast path: exact match
    if nat in NATIONALITY_FLAGS:
        return f"{NATIONALITY_FLAGS[nat]} {nat}"
    # Multi-nationality: greedy left-to-right, try 2-word combos first
    parts = nat.split()
    if len(parts) == 1:
        return nat  # unknown single nationality
    resolved: list[str] = []
    i = 0
    while i < len(parts):
        matched = False
        if i + 1 < len(parts):
            two = f"{parts[i]} {parts[i + 1]}"
            if two in NATIONALITY_FLAGS:
                resolved.append(f"{NATIONALITY_FLAGS[two]} {two}")
                i += 2
                matched = True
        if not matched:
            flag = NATIONALITY_FLAGS.get(parts[i], "")
            resolved.append(f"{flag} {parts[i]}".strip() if flag else parts[i])
            i += 1
    return " / ".join(resolved)


# ─────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@700;800&family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Inter', system-ui, sans-serif !important;
    background-color: #091423 !important;
    color: #d9e3f8 !important;
}
#MainMenu, footer { visibility: hidden; }
header { display: none !important; }
.main .block-container {
    padding: 1.5rem 2rem 3rem !important;
    max-width: 1420px !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #091423 !important;
    border-right: 1px solid rgba(255,255,255,0.04) !important;
    box-shadow: 4px 0 24px rgba(0,0,0,0.5) !important;
    min-width: 240px !important;
    max-width: 240px !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding: 0 !important;
}
[data-testid="stSidebarCollapseButton"] {
    display: none !important;
}
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    color: #4a6d8a !important;
    border: none !important;
    border-left: 3px solid transparent !important;
    border-radius: 0 !important;
    font-family: 'Manrope', sans-serif !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
    padding: 14px 24px !important;
    width: 100% !important;
    text-align: left !important;
    justify-content: flex-start !important;
    transition: all 0.2s ease !important;
    margin: 0 !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,255,255,0.05) !important;
    color: #d9e3f8 !important;
    border-color: transparent !important;
    transform: translateX(4px) !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .stButton > button:focus {
    box-shadow: none !important;
    outline: none !important;
}

/* ── Inputs ── */
.stTextInput > div > div > input,
.stSelectbox > div > div > div {
    background-color: #121c2b !important;
    color: #d9e3f8 !important;
    border: 1px solid #3c494e !important;
    border-radius: 10px !important;
    font-size: 13px !important;
    font-family: 'Inter', sans-serif !important;
}
.stTextInput > div > div > input::placeholder { color: #bbc9cf !important; opacity: 0.4; }
.stTextInput > div > div > input:focus,
.stSelectbox > div > div > div:focus {
    border-color: #00d2ff !important;
    box-shadow: 0 0 0 3px rgba(0,210,255,0.12) !important;
}
label[data-testid="stWidgetLabel"] { display: none !important; }

/* ── Buttons (main) ── */
.main .stButton > button {
    background: #162030 !important;
    color: #a5e7ff !important;
    border: 1px solid #3c494e !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    padding: 0.5rem 1.2rem !important;
    transition: all .2s ease !important;
    font-family: 'Inter', sans-serif !important;
}
.main .stButton > button:hover {
    background: #202a3a !important;
    border-color: #a5e7ff !important;
    transform: translateY(-1px) !important;
}

/* ── Spinner ── */
.stSpinner > div { border-top-color: #00d2ff !important; }

/* ── Images ── */
img { border-radius: 12px; display: block; }

/* ── Alertes ── */
.stAlert { border-radius: 12px !important; }

/* ── Photo centrée ── */
[data-testid="stImage"] { display:flex !important; justify-content:center !important; }
[data-testid="stImage"] > img { display:block !important; margin:0 auto !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: #091423; }
::-webkit-scrollbar-thumb { background: #2b3546; border-radius: 3px; }

/* ── Dataframe ── */
[data-testid="stDataFrameColumnMenuTarget"] { display: none !important; }

/* ── Caption ── */
.stCaption { color: #bbc9cf !important; font-size: 11px !important; }

/* ── Glass effect on Plotly chart containers ── */
[data-testid="stPlotlyChart"] {
    border-radius: 20px !important;
    overflow: hidden !important;
    border: 1px solid rgba(165,231,255,0.08) !important;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4) !important;
}
[data-testid="stPlotlyChart"] > div {
    background: linear-gradient(
        135deg,
        rgba(43,53,70,0.4) 0%,
        rgba(18,28,43,0.6) 100%
    ) !important;
    backdrop-filter: blur(12px) !important;
    border-radius: 20px !important;
    overflow: hidden !important;
}
</style>
"""


# ─────────────────────────────────────────────
# COMPOSANTS HTML
# ─────────────────────────────────────────────

def section_title(text: str) -> str:
    return (
        f'<div style="font-family:Manrope,sans-serif;font-size:10px;font-weight:800;'
        f'color:#bbc9cf;letter-spacing:3px;text-transform:uppercase;'
        f'margin-bottom:14px;margin-top:8px;">{text}</div>'
    )



def _gauge_color(pct: float) -> str:
    if pct >= 85: return "#00d2ff"
    if pct >= 67: return "#47d6ff"
    if pct >= 33: return "#ffaa00"
    return "#ff4444"


def _gauge_level(pct: float | None) -> tuple[str, str]:
    """Return (label, color) for the level badge below the gauge."""
    if pct is None:
        return "—", "#3c4a5a"
    if pct >= 85:
        return "Élite", "#00d2ff"
    if pct >= 67:
        return "Bon", "#47d6ff"
    if pct >= 33:
        return "Correct", "#ffaa00"
    return "Faible", "#ff4444"


def _gauge_fig(
    label: str,
    value: float,
    pct: float | None,
    rank: int | None = None,
    total: int | None = None,
) -> go.Figure:
    if pct is None:
        color    = "#2b3546"
        pct_val  = 0.0
        pct_disp = "—"
    else:
        pct_val  = float(pct)
        color    = _gauge_color(pct_val)
        pct_disp = f"{int(pct_val)}%"

    level_label, level_color = _gauge_level(pct)

    fig = go.Figure()

    # Donut ring — top-center of card
    fig.add_trace(go.Pie(
        values=[max(pct_val, 0.001), max(100 - pct_val, 0.001)],
        hole=0.70,
        direction="clockwise",
        rotation=90,
        marker=dict(colors=[color, "#2b3546"], line=dict(width=0)),
        hoverinfo="none",
        textinfo="none",
        showlegend=False,
        domain=dict(x=[0.18, 0.82], y=[0.46, 0.98]),
    ))

    annotations = [
        # Percentile inside donut hole
        dict(
            text=f"<b>{pct_disp}</b>",
            x=0.50, y=0.745,
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=11, color=color, family="Inter"),
            xanchor="center", yanchor="middle",
        ),
        # Metric label — below donut
        dict(
            text=label.upper(),
            x=0.50, y=0.38,
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=8, color="#bbc9cf", family="Inter"),
            xanchor="center", yanchor="middle",
        ),
        # Big stat value — center
        dict(
            text=f"<b>{value:.3f}</b>",
            x=0.50, y=0.21,
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=24, color="#d9e3f8", family="Manrope"),
            xanchor="center", yanchor="middle",
        ),
        # Level label — bottom
        dict(
            text=f"<b>{level_label}</b>",
            x=0.50, y=0.04,
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=9, color=level_color, family="Inter"),
            xanchor="center", yanchor="bottom",
            bgcolor=f"rgba({','.join(str(int(level_color.lstrip('#')[i:i+2], 16)) for i in (0,2,4))},0.12)" if level_color.startswith("#") else "transparent",
            borderpad=4,
        ),
    ]

    if rank is not None and total is not None:
        annotations.append(dict(
            text=f"#{rank} / {total}",
            x=0.50, y=-0.03,
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=8, color="#4a6d8a", family="Inter"),
            xanchor="center", yanchor="top",
        ))

    fig.update_layout(
        height=190,
        paper_bgcolor="#121c2b",
        plot_bgcolor="#121c2b",
        margin=dict(l=8, r=8, t=8, b=28),
        showlegend=False,
        annotations=annotations,
    )

    return fig


def card_raw_stats(
    games: int,
    minutes: int,
    goals: int,
    assists: int,
    xg_total: float = 0.0,
    xa_total: float = 0.0,
) -> str:
    def _diff(actual: int, expected: float, metric: str) -> str:
        d = round(actual - expected, 1)
        sign  = "+" if d >= 0 else ""
        color = "#4ade80" if d >= 0 else "#f87171"
        return (
            f'<div style="font-size:10px;font-weight:700;color:{color};'
            f'margin-top:3px;letter-spacing:.2px;">{sign}{d:.1f} vs {metric}</div>'
        )

    items = [
        ("Matchs",  str(games),              ""),
        ("Minutes", str(minutes),            ""),
        ("Buts",    str(goals),              _diff(goals,   xg_total, "xG")),
        ("Assists",  str(assists),           _diff(assists, xa_total, "xA")),
        ("xG",      f"{xg_total:.1f}",       ""),
        ("xA",      f"{xa_total:.1f}",       ""),
    ]

    cells = ""
    for i, (lbl, val, extra) in enumerate(items):
        border = "border-right:1px solid rgba(255,255,255,0.05);" if i < len(items) - 1 else ""
        cells += (
            f'<div style="flex:1;text-align:center;padding:18px 6px;{border}">'
            f'<div style="font-size:30px;font-weight:900;font-family:Manrope,sans-serif;'
            f'color:#d9e3f8;line-height:1;letter-spacing:-1.5px;">{val}</div>'
            f'<div style="font-size:10px;color:#bbc9cf;font-weight:600;'
            f'letter-spacing:1.5px;text-transform:uppercase;margin-top:6px;">{lbl}</div>'
            f'{extra}'
            f'</div>'
        )
    return (
        f'<div style="background:#162030;border:1px solid rgba(255,255,255,0.05);'
        f'border-radius:16px;display:flex;box-sizing:border-box;overflow:hidden;">'
        f'{cells}</div>'
    )



def _insights_section_html(
    pct: dict | None = None,
    goals: int = 0,
    assists: int = 0,
) -> str:
    # ── Metric display names ─────────────────────────────────────────────────
    METRIC_NAMES = {
        "xG_90":        "xG / 90",
        "npxG_90":      "npxG / 90",
        "xA_90":        "xA / 90",
        "xGChain_90":   "xGChain / 90",
        "xGBuildup_90": "xGBuildup / 90",
    }

    percentiles: dict[str, float] = {}
    values: dict[str, float] = {}
    if pct:
        for key in METRIC_NAMES:
            p = (pct.get("percentiles") or {}).get(key)
            if p is not None:
                percentiles[key] = float(p)
                values[key] = float(pct.get(key) or 0.0)

    avg_pct: float | None = None
    if percentiles:
        avg_pct = sum(percentiles.values()) / len(percentiles)

    def _pct_badge(p: float, bg: str) -> str:
        return (
            f'<span style="display:inline-block;padding:2px 8px;border-radius:999px;'
            f'font-size:10px;font-weight:800;color:#fff;background:{bg};'
            f'letter-spacing:.5px;white-space:nowrap;">{int(p)}e perc.</span>'
        )

    def _bullet(key: str, p: float, bg: str) -> str:
        name = METRIC_NAMES.get(key, key)
        val  = values.get(key, 0.0)
        return (
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.04);">'
            f'<span style="font-size:12px;color:#d9e3f8;">{name} '
            f'<span style="color:#bbc9cf;font-size:11px;">({val:.3f})</span></span>'
            f'{_pct_badge(p, bg)}'
            f'</div>'
        )

    # Strengths: percentile > 67, sorted desc
    strong_items = sorted(
        [(k, v) for k, v in percentiles.items() if v > 67], key=lambda x: -x[1]
    )
    if strong_items:
        bullets_html = "".join(_bullet(k, v, "#1a6b3a") for k, v in strong_items)
    else:
        bullets_html = '<p style="color:#bbc9cf;font-size:12px;font-style:italic;margin:0;">Aucun point fort identifié</p>'
    strengths = (
        '<div style="background:#202a3a;border:1px solid rgba(255,255,255,0.05);'
        'border-radius:16px;padding:24px;">'
        '<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">'
        '<span style="font-size:16px;">⚡</span>'
        '<span style="font-family:Manrope,sans-serif;font-size:11px;font-weight:900;'
        'text-transform:uppercase;letter-spacing:2px;color:#d9e3f8;">Points forts</span>'
        '</div>'
        f'{bullets_html}'
        '</div>'
    )

    # Development: percentile < 33, sorted asc
    dev_items = sorted(
        [(k, v) for k, v in percentiles.items() if v < 33], key=lambda x: x[1]
    )
    if dev_items:
        dev_html = "".join(_bullet(k, v, "#7a4e00") for k, v in dev_items)
    else:
        dev_html = '<p style="color:#bbc9cf;font-size:12px;font-style:italic;margin:0;">Aucun axe de progression identifié</p>'
    development = (
        '<div style="background:#202a3a;border:1px solid rgba(255,255,255,0.05);'
        'border-radius:16px;padding:24px;">'
        '<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">'
        '<span style="font-size:16px;">📈</span>'
        '<span style="font-family:Manrope,sans-serif;font-size:11px;font-weight:900;'
        'text-transform:uppercase;letter-spacing:2px;color:#d9e3f8;">Axes de progression</span>'
        '</div>'
        f'{dev_html}'
        '</div>'
    )

    # Scout verdict
    if avg_pct is not None and avg_pct >= 75:
        verdict_badge = '#2ecc71'
        verdict_label = 'Recommandé'
        verdict_note  = round(avg_pct / 10, 1)
        verdict_text  = (
            "Profil offensif de haut niveau. Ses métriques xG et xA placent ce joueur "
            "parmi les meilleurs de son poste en Ligue 1."
        )
    elif avg_pct is not None and avg_pct >= 50:
        verdict_badge = '#ffaa00'
        verdict_label = 'Intéressant'
        verdict_note  = round(avg_pct / 10, 1)
        verdict_text  = (
            "Profil solide avec des points forts notables. "
            "Une progression sur les métriques de création pourrait franchir un palier."
        )
    else:
        verdict_badge = '#ff4444'
        verdict_label = 'À surveiller'
        verdict_note  = round((avg_pct or 40) / 10, 1)
        verdict_text  = (
            "Les performances actuelles restent en dessous de la médiane du poste. "
            "Évolution à suivre sur la durée."
        )

    xg90  = values.get("xG_90", 0.0)
    xa90  = values.get("xA_90", 0.0)
    verdict = (
        f'<div style="background:linear-gradient(135deg,rgba(165,231,255,0.07),transparent);'
        f'border:1px solid rgba(165,231,255,0.15);border-radius:16px;padding:24px;">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">'
        f'<span style="font-family:Manrope,sans-serif;font-size:11px;font-weight:900;'
        f'text-transform:uppercase;letter-spacing:2px;color:#a5e7ff;">Scout Verdict</span>'
        f'<span style="display:flex;align-items:center;gap:8px;">'
        f'<span style="padding:3px 10px;border-radius:999px;font-size:10px;font-weight:800;'
        f'color:#fff;background:{verdict_badge};">{verdict_label}</span>'
        f'<span style="font-family:Manrope,sans-serif;font-size:18px;font-weight:900;'
        f'color:#d9e3f8;">{verdict_note}<span style="font-size:11px;color:#bbc9cf;">/10</span></span>'
        f'</span></div>'
        f'<p style="color:#bbc9cf;font-size:12px;line-height:1.6;margin:0 0 16px 0;">{verdict_text}</p>'
        f'<div style="display:flex;gap:0;border:1px solid rgba(255,255,255,0.06);border-radius:10px;overflow:hidden;">'
        f'<div style="flex:1;text-align:center;padding:10px 6px;border-right:1px solid rgba(255,255,255,0.06);">'
        f'<div style="font-size:18px;font-weight:900;font-family:Manrope,sans-serif;color:#d9e3f8;">{goals}</div>'
        f'<div style="font-size:10px;color:#bbc9cf;text-transform:uppercase;letter-spacing:1px;margin-top:3px;">Buts</div>'
        f'</div>'
        f'<div style="flex:1;text-align:center;padding:10px 6px;border-right:1px solid rgba(255,255,255,0.06);">'
        f'<div style="font-size:18px;font-weight:900;font-family:Manrope,sans-serif;color:#d9e3f8;">{assists}</div>'
        f'<div style="font-size:10px;color:#bbc9cf;text-transform:uppercase;letter-spacing:1px;margin-top:3px;">Assists</div>'
        f'</div>'
        f'<div style="flex:1;text-align:center;padding:10px 6px;border-right:1px solid rgba(255,255,255,0.06);">'
        f'<div style="font-size:18px;font-weight:900;font-family:Manrope,sans-serif;color:#d9e3f8;">{xg90:.2f}</div>'
        f'<div style="font-size:10px;color:#bbc9cf;text-transform:uppercase;letter-spacing:1px;margin-top:3px;">xG/90</div>'
        f'</div>'
        f'<div style="flex:1;text-align:center;padding:10px 6px;">'
        f'<div style="font-size:18px;font-weight:900;font-family:Manrope,sans-serif;color:#d9e3f8;">{xa90:.2f}</div>'
        f'<div style="font-size:10px;color:#bbc9cf;text-transform:uppercase;letter-spacing:1px;margin-top:3px;">xA/90</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )

    return (
        f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-top:8px;">'
        f'{strengths}{development}{verdict}'
        f'</div>'
    )


# ─────────────────────────────────────────────
# HEADER JOUEUR — PHOTO + BADGES
# ─────────────────────────────────────────────

def _player_profile_html(
    name: str,
    club: str,
    logo_url: str,
    nat: str,
    pos: str,
    age: str,
    val: str,
    ctr: str,
    avg_pct: float | None,
    photo_bytes: bytes | None,
    profile_url: str = "",
) -> str:
    import base64

    # ── Photo ────────────────────────────────────────────────────────────────
    if photo_bytes:
        mime = "image/png" if photo_bytes[:4] == b'\x89PNG' else "image/jpeg"
        b64  = base64.b64encode(photo_bytes).decode()
        tm_link = ""
        if profile_url:
            tm_link = (
                f'<a href="{profile_url}" target="_blank" '
                f'style="display:block;margin-top:7px;font-size:10px;color:#bbc9cf;'
                f'text-decoration:none;text-align:center;letter-spacing:.5px;">'
                f'↗ Transfermarkt</a>'
            )
        photo_html = (
            f'<img src="data:{mime};base64,{b64}" '
            f'style="width:150px;height:150px;object-fit:cover;'
            f'border-radius:16px;display:block;" />{tm_link}'
        )
    else:
        photo_html = (
            '<div style="width:150px;height:150px;background:#162030;'
            'border:1px solid rgba(255,255,255,0.05);border-radius:16px;'
            'display:flex;align-items:center;justify-content:center;'
            'font-size:48px;color:#3c494e;">👤</div>'
        )

    # ── Badge style ───────────────────────────────────────────────────────────
    bs = (
        "display:inline-flex;align-items:center;gap:5px;padding:4px 12px;"
        "background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);"
        "border-radius:999px;font-size:11px;font-weight:700;color:#bbc9cf;"
        "text-transform:uppercase;letter-spacing:1.5px;white-space:nowrap;"
        "font-family:Inter,sans-serif;"
    )

    logo_img = ""
    if logo_url and logo_url not in ("N/A", ""):
        logo_img = (
            f'<img src="{logo_url}" style="width:16px;height:16px;'
            f'object-fit:contain;border-radius:3px;" />'
        )

    # ── Build badge list ──────────────────────────────────────────────────────
    badges: list[str] = []
    if club and club not in ("—", ""):
        badges.append(f'<span style="{bs}">{logo_img}{club}</span>')
    if nat and nat not in ("—", ""):
        badges.append(f'<span style="{bs}">{_nat_with_flag(nat)}</span>')
    if pos and pos not in ("—", ""):
        badges.append(f'<span style="{bs}">{pos}</span>')
    if age and age not in ("—", ""):
        badges.append(f'<span style="{bs}">{age}</span>')
    if val and val not in ("—", "N/A", ""):
        # Strip leading € from TM value then display without duplicate
        val_clean = val.lstrip("€").strip()
        badges.append(f'<span style="{bs}">{val_clean} €</span>')
    if ctr and ctr not in ("—", "N/A", ""):
        badges.append(f'<span style="{bs}">{ctr}</span>')
    if avg_pct is not None and avg_pct >= 85:
        badges.append(
            '<span style="display:inline-flex;align-items:center;padding:4px 14px;'
            'background:#00d2ff;border-radius:999px;font-size:10px;font-weight:900;'
            'color:#003543;text-transform:uppercase;letter-spacing:2px;'
            'box-shadow:0 0 16px rgba(0,210,255,0.3);">★ ELITE RANK</span>'
        )

    badges_row = (
        '<div style="display:flex;flex-wrap:wrap;gap:8px;">'
        + "".join(badges)
        + '</div>'
    )

    return (
        f'<div style="display:flex;gap:28px;align-items:flex-start;'
        f'margin-bottom:16px;padding-bottom:16px;'
        f'border-bottom:1px solid rgba(255,255,255,0.05);">'
        f'<div style="flex-shrink:0;">{photo_html}</div>'
        f'<div style="flex:1;min-width:0;padding-top:4px;">'
        f'<h1 style="font-family:Manrope,sans-serif;'
        f'font-size:clamp(1.8rem,3.5vw,3rem);font-weight:900;color:#d9e3f8;'
        f'letter-spacing:-2px;line-height:1.05;margin:0 0 18px 0;">{name}</h1>'
        f'{badges_row}'
        f'</div>'
        f'</div>'
    )


# ─────────────────────────────────────────────
# SIDEBAR NAVIGATION
# ─────────────────────────────────────────────

def _sidebar_nav() -> None:
    view = st.session_state.get("view", "home")

    def _item(icon: str, label: str, target: str) -> str:
        active = view == target
        if active:
            s = (
                "display:flex;align-items:center;gap:14px;padding:14px 24px;"
                "text-decoration:none;width:100%;box-sizing:border-box;"
                "background:linear-gradient(to right,rgba(0,210,255,0.15),transparent);"
                "border-left:3px solid #00d2ff;color:#a5e7ff;"
                "font-family:Manrope,sans-serif;font-size:11px;font-weight:700;"
                "text-transform:uppercase;letter-spacing:2px;"
            )
        else:
            s = (
                "display:flex;align-items:center;gap:14px;padding:14px 27px;"
                "text-decoration:none;width:100%;box-sizing:border-box;"
                "color:#4a6d8a;border-left:3px solid transparent;"
                "font-family:Manrope,sans-serif;font-size:11px;font-weight:700;"
                "text-transform:uppercase;letter-spacing:2px;"
            )
        return f'<a href="?_nav={target}" target="_top" style="{s}">{icon}&nbsp;&nbsp;{label}</a>'

    with st.sidebar:
        st.html(
            f'<div style="padding:28px 0 16px;">'
            f'<div style="padding:0 20px 28px;">'
            f'<div style="display:flex;align-items:center;gap:12px;">'
            f'<div style="width:40px;height:40px;border-radius:12px;background:#00d2ff;'
            f'display:flex;align-items:center;justify-content:center;font-size:20px;'
            f'box-shadow:0 4px 16px rgba(0,210,255,0.25);">⚽</div>'
            f'<div>'
            f'<div style="font-family:Manrope,sans-serif;font-weight:900;font-style:italic;'
            f'color:#a5e7ff;font-size:14px;text-transform:uppercase;letter-spacing:3px;">PitchIQ</div>'
            f'<div style="font-size:10px;color:#4a6d8a;text-transform:uppercase;'
            f'letter-spacing:1px;margin-top:2px;">Elite Scout</div>'
            f'</div></div></div>'
            f'<nav>'
            f'{_item("🏠", "Home", "home")}'
            f'{_item("📊", "Explorer Ligue 1", "explore")}'
            f'</nav>'
            f'</div>'
        )


# ─────────────────────────────────────────────
# DONNÉES CACHÉES
# ─────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _load_records() -> list[dict]:
    path = Path("percentiles.json")
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def _get_understat(name: str, league: str, season: str) -> dict:
    return fetch_understat_data(name, league=league, season=season)


@st.cache_data(show_spinner=False)
def _get_transfermarkt(name: str) -> dict | None:
    try:
        return fetch_transfermarkt_data(name)
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def _get_percentile_record(name: str) -> dict | None:
    for r in _load_records():
        if name.lower() in r["player_name"].lower():
            return r
    return None


@st.cache_data(show_spinner=False)
def _get_percentile_context(name: str) -> dict | None:
    records = _load_records()
    player  = next((r for r in records if name.lower() in r["player_name"].lower()), None)
    if player is None:
        return None

    pos_group = player.get("position_group", "joueurs")
    same_pos  = [r for r in records if r.get("position_group") == pos_group]
    total     = len(same_pos)

    ranks: dict[str, int] = {}
    for key in ["xG_90", "npxG_90", "xA_90", "xGChain_90", "xGBuildup_90"]:
        val        = player.get(key, 0.0)
        sorted_pop = sorted([r.get(key, 0.0) for r in same_pos], reverse=True)
        ranks[key] = next(
            (i + 1 for i, v in enumerate(sorted_pop) if abs(v - val) < 1e-9),
            sum(1 for v in sorted_pop if v > val) + 1,
        )

    return {"total": total, "pos_group": pos_group, "ranks": ranks}


@st.cache_data(show_spinner=False)
def _get_photo_bytes(url: str) -> bytes | None:
    try:
        r = requests.get(url, headers=TM_HEADERS, timeout=8)
        r.raise_for_status()
        return r.content
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def _get_shot_map_fig(name: str, league: str, season: str):
    return generate_shot_map_plotly(name, league=league, season=season)


@st.cache_data(show_spinner=False)
def _get_radar_fig(name: str, league: str, season: str):
    return generate_radar_plotly(name, league=league, season=season)


# ─────────────────────────────────────────────
# COMPOSANT PARTAGÉ — BARRE DE RECHERCHE
# ─────────────────────────────────────────────

def _search_bar(records: list[dict], key: str) -> None:
    placeholder = "🔍  Rechercher un joueur…"
    options = [placeholder] + [
        f"{r['player_name']}  —  {r.get('team', '')}"
        for r in records
    ]
    sel = st.selectbox(
        "search",
        options,
        key=key,
        label_visibility="collapsed",
    )
    if sel and sel != placeholder:
        name = sel.split("  —  ")[0]
        st.session_state.pop("explore_df", None)
        st.session_state["view"]   = "player"
        st.session_state["player"] = name
        st.rerun()


# ─────────────────────────────────────────────
# VUE 1 — LANDING PAGE
# ─────────────────────────────────────────────

def view_home() -> None:
    records   = _load_records()
    n_players = len(records)

    _, col_mid, _ = st.columns([1, 2, 1])
    with col_mid:
        st.html(
            '<div style="display:flex;flex-direction:column;align-items:center;'
            'gap:8px;padding:32px 0 8px;">'
            '<div style="width:64px;height:64px;background:#00d2ff;border-radius:16px;'
            'display:flex;align-items:center;justify-content:center;font-size:30px;'
            'box-shadow:0 4px 30px rgba(0,210,255,0.3);">⚽</div>'
            '<div style="font-family:Manrope,sans-serif;font-size:42px;font-weight:900;'
            'letter-spacing:-2px;background:linear-gradient(90deg,#d9e3f8 0%,#a5e7ff 100%);'
            '-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
            'line-height:1.1;margin-top:6px;">PitchIQ</div>'
            '<div style="font-family:Manrope,sans-serif;font-size:10px;color:#bbc9cf;'
            'letter-spacing:4px;font-weight:700;text-transform:uppercase;">'
            'Football Intelligence Platform</div>'
            f'<div style="font-size:12px;color:#3c494e;margin-top:4px;letter-spacing:.5px;">'
            f'🇫🇷 &nbsp;{n_players} joueurs analysés · Ligue 1 2025/26</div>'
            '</div>'
        )

    st.html('<div style="margin-top:32px;"></div>')

    col_l, col_r = st.columns(2, gap="large")

    with col_l:
        st.html(
            '<div style="background:#162030;border:1px solid rgba(255,255,255,0.05);'
            'border-radius:16px;padding:28px 24px 8px;">'
            '<div style="font-family:Manrope,sans-serif;font-size:11px;font-weight:800;'
            'color:#00d2ff;letter-spacing:2px;text-transform:uppercase;margin-bottom:12px;">'
            '🔍 &nbsp;Rechercher un joueur</div>'
            '<div style="font-size:12px;color:#bbc9cf;margin-bottom:16px;">'
            'Tapez le nom d\'un joueur pour filtrer la liste.</div>'
            '</div>'
        )
        _search_bar(records, key="home_search")

    with col_r:
        st.html(
            '<div style="background:#162030;border:1px solid rgba(255,255,255,0.05);'
            'border-radius:16px;padding:28px 24px 24px;">'
            '<div style="font-family:Manrope,sans-serif;font-size:11px;font-weight:800;'
            'color:#00d2ff;letter-spacing:2px;text-transform:uppercase;margin-bottom:12px;">'
            '📊 &nbsp;Explorer la Ligue 1</div>'
            '<div style="font-size:13px;color:#bbc9cf;margin-bottom:24px;line-height:1.6;">'
            'Classement complet des joueurs de Ligue 1. '
            'Filtrez par poste et par club, triez par n\'importe quelle métrique '
            'en cliquant sur les colonnes.'
            '</div>'
            '</div>'
        )
        if st.button("🇫🇷 &nbsp; Ligue 1 2025/26", use_container_width=True, key="btn_explore"):
            st.session_state["view"] = "explore"
            st.rerun()


# ─────────────────────────────────────────────
# VUE 2 — FICHE JOUEUR
# ─────────────────────────────────────────────

def view_player() -> None:
    _CACHE_VERSION = "v3-fr"
    if st.session_state.get("_cache_version") != _CACHE_VERSION:
        _get_shot_map_fig.clear()
        _get_understat.clear()
        st.session_state["_cache_version"] = _CACHE_VERSION

    records = _load_records()

    # ── Header bar ───────────────────────────────────────────────────────────
    col_back, col_logo, col_search = st.columns([1, 3, 3])

    with col_back:
        if st.button("← Retour", key="back_player"):
            st.session_state["view"] = "home"
            st.rerun()

    with col_logo:
        st.html(
            '<div style="display:flex;align-items:center;gap:10px;padding:4px 0;">'
            '<div style="width:32px;height:32px;background:#00d2ff;border-radius:8px;'
            'display:flex;align-items:center;justify-content:center;font-size:16px;">⚽</div>'
            '<div style="font-family:Manrope,sans-serif;font-size:22px;font-weight:900;'
            'letter-spacing:-1px;background:linear-gradient(90deg,#d9e3f8 0%,#a5e7ff 100%);'
            '-webkit-background-clip:text;-webkit-text-fill-color:transparent;">PitchIQ</div>'
            '<div style="font-size:10px;color:#3c494e;letter-spacing:2px;font-weight:700;">'
            '🇫🇷 LIGUE 1 · 2025/26</div>'
            '</div>'
        )

    with col_search:
        _search_bar(records, key="player_search")

    st.html('<hr style="border:none;border-top:1px solid rgba(255,255,255,0.05);margin:.4rem 0 1.6rem;">')

    player = st.session_state.get("player", "Khvicha Kvaratskhelia")
    errors: dict[str, str] = {}

    with st.spinner("⏳  Chargement…"):
        try:
            us = _get_understat(player, LEAGUE, SEASON)
        except Exception as e:
            st.error(f"Understat — joueur introuvable ou erreur réseau : {e}")
            return

        tm  = _get_transfermarkt(player)
        pct = _get_percentile_record(player)
        ctx = _get_percentile_context(player)

        photo_bytes: bytes | None = None
        photo_url = (tm or {}).get("photo_url", "")
        if photo_url and photo_url != "N/A":
            photo_bytes = _get_photo_bytes(photo_url)

        shot_fig = None
        try:
            shot_fig = _get_shot_map_fig(player, LEAGUE, SEASON)
            if shot_fig is not None:
                n_goals = sum(1 for s in us.get("shot_coords", []) if s.get("result") == "Goal")
                n_shots = len(us.get("shot_coords", []))
                pname   = us.get("player_name", player)
                conv_pct = (n_goals / n_shots * 100) if n_shots > 0 else 0.0
                shot_annotations = list(shot_fig.layout.annotations or [])
                shot_annotations.append(dict(
                    text=f"<b>{conv_pct:.1f}% conversion</b>",
                    x=80, y=124,
                    xref="x", yref="y",
                    showarrow=False,
                    font=dict(size=10, color="#003543", family="Inter"),
                    bgcolor="#2ecc71",
                    borderpad=5,
                    xanchor="right", yanchor="top",
                ))
                shot_fig.update_layout(
                    title=dict(
                        text=f"<b>{pname}</b>  ·  Ligue 1  ·  {n_goals} buts / {n_shots} tirs",
                        x=0.5, xanchor="center",
                        font=dict(color="#d9e3f8", size=13, family="Manrope"),
                    ),
                    margin=dict(t=100, l=20, r=20, b=20),
                    annotations=shot_annotations,
                )
        except Exception as e:
            errors["shot_map"] = str(e)

        radar_fig = None
        try:
            radar_fig = _get_radar_fig(player, LEAGUE, SEASON)
            if radar_fig is not None:
                pname     = us.get("player_name", player)
                pos_disp  = POS_SINGULAR.get((ctx or {}).get("pos_group", ""), "")
                mins_disp = us.get("minutes", 0)
                radar_annotations = list(radar_fig.layout.annotations or [])
                if avg_pct is not None:
                    top_pct = 100 - avg_pct
                    radar_annotations.append(dict(
                        text=f"<b>Top {top_pct:.0f}%</b>",
                        xref="paper", yref="paper",
                        x=1.0, y=1.06,
                        showarrow=False,
                        font=dict(size=10, color="#003543", family="Inter"),
                        bgcolor="#00d2ff",
                        borderpad=5,
                        xanchor="right", yanchor="top",
                    ))
                radar_fig.update_layout(
                    title=dict(
                        text=f"<b>{pname}</b>  ·  {pos_disp}  ·  {mins_disp} min",
                        x=0.5, xanchor="center",
                        font=dict(color="#d9e3f8", size=13, family="Manrope"),
                    ),
                    margin=dict(t=100, l=20, r=20, b=20),
                    annotations=radar_annotations,
                )
        except Exception as e:
            errors["radar"] = str(e)

    # ── Compute avg percentile for ELITE badge ────────────────────────────────
    avg_pct: float | None = None
    if pct:
        pct_vals = [pct.get("percentiles", {}).get(k) for k, _, _ in METRICS]
        valid    = [p for p in pct_vals if p is not None]
        if valid:
            avg_pct = sum(valid) / len(valid)

    # ── Player profile header ────────────────────────────────────────────────
    name_disp = (tm or {}).get("full_name")       or us.get("player_name", player)
    club_disp = (tm or {}).get("club")            or us.get("team", "—")
    logo_url  = (tm or {}).get("club_logo_url",   "")
    nat_disp  = (tm or {}).get("nationality",     "—")
    pos_raw   = (tm or {}).get("position",         "—")
    pos_disp  = _normalize_position(pos_raw) if pos_raw not in ("—", "N/A") else pos_raw
    age_disp  = (tm or {}).get("dob_age",          "—")
    val_disp  = (tm or {}).get("market_value",     "—")
    ctr_disp  = (tm or {}).get("contract_expiry",  "—")
    prof_url  = (tm or {}).get("profile_url",      "")

    st.html(section_title("Profil joueur"))
    st.html(_player_profile_html(
        name=name_disp, club=club_disp, logo_url=logo_url,
        nat=nat_disp, pos=pos_disp, age=age_disp,
        val=val_disp, ctr=ctr_disp, avg_pct=avg_pct,
        photo_bytes=photo_bytes, profile_url=prof_url,
    ))

    # ── Section 2 : saison ────────────────────────────────────────────────────
    minutes = us.get("minutes", 0)
    goals   = us.get("goals", 0)
    assists = us.get("assists", 0)
    games   = us.get("games", 0)
    if games == 0 and minutes > 0:
        games = max(1, round(minutes / 75))
    xg_total = float(us.get("xG") or 0.0)
    xa_total = float(us.get("xA") or 0.0)
    st.html(section_title("Saison en cours"))
    st.html(card_raw_stats(games, minutes, goals, assists, xg_total, xa_total))

    # ── Section 3 : stats /90 ────────────────────────────────────────────────
    st.html('<div style="margin-top:28px;"></div>')
    st.html(section_title("Statistiques avancées / 90 min"))

    cols      = st.columns(5, gap="medium")
    total_pos = (ctx or {}).get("total")
    ranks_map = (ctx or {}).get("ranks", {})
    for col, (key, label, _) in zip(cols, METRICS):
        if pct:
            val = pct.get(key, 0.0)
        else:
            raw = us.get(key.replace("_90", ""), 0.0)
            val = raw / (minutes or 1) * 90
        p    = (pct or {}).get("percentiles", {}).get(key)
        rank = ranks_map.get(key)
        with col:
            st.plotly_chart(
                _gauge_fig(label, val, p, rank=rank, total=total_pos),
                use_container_width=True,
                config={"displayModeBar": False},
            )

    if pct is None:
        st.caption(
            "⚠️ Percentiles indisponibles — joueur absent de percentiles.json "
            "(< 180 min ou hors Ligue 1). Relancez `python3 percentiles.py`."
        )

    # ── Section 4 : visualisations ───────────────────────────────────────────
    st.html('<div style="margin-top:28px;"></div>')
    col_shot, col_radar = st.columns(2, gap="large")

    with col_shot:
        st.html(section_title("Carte des tirs"))
        if shot_fig is not None:
            st.plotly_chart(shot_fig, use_container_width=True,
                            config={"displayModeBar": False})
        else:
            st.warning(f"Carte des tirs indisponible. {errors.get('shot_map', '')}")

    with col_radar:
        st.html(section_title("Radar de performance"))
        if radar_fig is not None:
            st.plotly_chart(radar_fig, use_container_width=True,
                            config={"displayModeBar": False})
        else:
            st.warning(f"Radar indisponible. {errors.get('radar', '')}")

    # ── Section 5 : insights ─────────────────────────────────────────────────
    st.html('<div style="margin-top:28px;"></div>')
    st.html(section_title("Analyse Scout"))
    st.html(_insights_section_html(pct=pct, goals=goals, assists=assists))

    # ── Footer ────────────────────────────────────────────────────────────────
    st.html(
        '<hr style="border:none;border-top:1px solid rgba(255,255,255,0.05);margin:2.5rem 0 1rem;">'
        '<div style="text-align:center;font-size:11px;color:#3c494e;letter-spacing:.5px;">'
        'Sources : Understat · Transfermarkt &nbsp;·&nbsp; Ligue 1 2025/26 '
        '· Percentiles calculés parmi les joueurs ≥ 180 min</div>'
    )


# ─────────────────────────────────────────────
# VUE 3 — EXPLORE
# ─────────────────────────────────────────────

def view_explore() -> None:
    records   = _load_records()
    all_clubs = sorted({r.get("team", "") for r in records if r.get("team")})

    col_back, col_title, col_search = st.columns([1, 3, 3])

    with col_back:
        if st.button("← Retour", key="back_explore"):
            st.session_state["view"] = "home"
            st.rerun()

    with col_title:
        st.html(
            '<div style="display:flex;align-items:center;gap:10px;padding:4px 0;">'
            '<div style="font-family:Manrope,sans-serif;font-size:22px;font-weight:900;'
            'letter-spacing:-1px;background:linear-gradient(90deg,#d9e3f8 0%,#a5e7ff 100%);'
            '-webkit-background-clip:text;-webkit-text-fill-color:transparent;">PitchIQ</div>'
            '<div style="font-size:14px;color:#bbc9cf;font-weight:700;">'
            '🇫🇷 Ligue 1 · 2025/26</div>'
            '</div>'
        )

    with col_search:
        _search_bar(records, key="explore_search")

    st.html('<hr style="border:none;border-top:1px solid rgba(255,255,255,0.05);margin:.4rem 0 1.2rem;">')

    f1, f2 = st.columns([2, 3])
    with f1:
        pos_filter = st.selectbox(
            "Poste", ["Tous"] + list(POS_SINGULAR.values()),
            key="exp_pos", label_visibility="collapsed",
        )
    with f2:
        club_filter = st.selectbox(
            "Équipe", ["Tous les clubs"] + all_clubs,
            key="exp_club", label_visibility="collapsed",
        )

    filtered = records
    if pos_filter != "Tous":
        pg = POS_FILTER_MAP.get(pos_filter, "")
        filtered = [r for r in filtered if r.get("position_group") == pg]
    if club_filter != "Tous les clubs":
        filtered = [r for r in filtered if r.get("team") == club_filter]

    filtered = sorted(filtered, key=lambda r: r.get("npxG_90", 0.0), reverse=True)
    n_total  = len(filtered)

    st.html(
        f'<div style="font-size:12px;color:#bbc9cf;margin-bottom:6px;">'
        f'{n_total} joueurs · Cliquez sur un joueur pour voir sa fiche · '
        f'Cliquez sur un en-tête pour trier</div>'
    )

    _SAFE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~ àáâãäåæçèéêëìíîïðñòóôõöùúûüýþÿÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖÙÚÛÜÝÞŸ'"
    df = pd.DataFrame([
        {
            "#":           i + 1,
            "Joueur":      f"?_player_click={urllib.parse.quote(r['player_name'], safe=_SAFE)}",
            "Club":        r.get("team", "—"),
            "Poste":       POS_SINGULAR.get(r.get("position_group", ""), "—"),
            "Min":         r.get("minutes", 0),
            "Buts":        r.get("goals", 0),
            "Ass.":        r.get("assists", 0),
            "xG/90":       round(r.get("xG_90",        0.0), 3),
            "npxG/90":     round(r.get("npxG_90",      0.0), 3),
            "xA/90":       round(r.get("xA_90",        0.0), 3),
            "xGChain/90":  round(r.get("xGChain_90",   0.0), 3),
            "xGBuildup/90":round(r.get("xGBuildup_90", 0.0), 3),
        }
        for i, r in enumerate(filtered)
    ])

    st.dataframe(
        df,
        key="explore_df",
        use_container_width=True,
        hide_index=True,
        height=650,
        column_config={
            "#":            st.column_config.NumberColumn("#", format="%d", width="small"),
            "Joueur":       st.column_config.LinkColumn(
                                "Joueur",
                                display_text=r"_player_click=(.+)",
                                width="medium",
                            ),
            "Club":         st.column_config.TextColumn("Club",   width="medium"),
            "Poste":        st.column_config.TextColumn("Poste",  width="small"),
            "Min":          st.column_config.NumberColumn("Min",  format="%d", width="small"),
            "Buts":         st.column_config.NumberColumn("Buts", format="%d", width="small"),
            "Ass.":         st.column_config.NumberColumn("Ass.", format="%d", width="small"),
            "xG/90":        st.column_config.NumberColumn("xG/90"),
            "npxG/90":      st.column_config.NumberColumn("npxG/90"),
            "xA/90":        st.column_config.NumberColumn("xA/90"),
            "xGChain/90":   st.column_config.NumberColumn("xGChain/90"),
            "xGBuildup/90": st.column_config.NumberColumn("xGBuildup/90"),
        },
    )


# ─────────────────────────────────────────────
# POINT D'ENTRÉE
# ─────────────────────────────────────────────

def main() -> None:
    _REC_VER = "v4-goals"
    if st.session_state.get("_rec_ver") != _REC_VER:
        _load_records.clear()
        st.session_state["_rec_ver"] = _REC_VER

    # ── Navigation via URL params (table clicks + sidebar nav) ───────────────
    _click = st.query_params.get("_player_click", "")
    if _click:
        st.session_state["view"]   = "player"
        st.session_state["player"] = _click
        st.query_params.clear()
        st.rerun()

    _nav = st.query_params.get("_nav", "")
    if _nav:
        st.session_state["view"] = _nav
        st.query_params.clear()
        st.rerun()

    st.markdown(_CSS, unsafe_allow_html=True)

    if "view" not in st.session_state:
        st.session_state["view"] = "home"

    _sidebar_nav()

    view = st.session_state["view"]

    if view == "home":
        view_home()
    elif view == "player":
        view_player()
    elif view == "explore":
        view_explore()
    else:
        st.session_state["view"] = "home"
        st.rerun()


if __name__ == "__main__":
    main()
