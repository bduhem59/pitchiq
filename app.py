#!/usr/bin/env python3
"""
app.py — xScout : Football Intelligence Platform
"""

import json
import urllib.parse
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

from player_data import fetch_understat_data, fetch_transfermarkt_data
from shot_map_plotly import generate_shot_map_plotly
from radar_plotly import generate_radar_plotly

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="xScout",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
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

# Groupes de poste au singulier
POS_SINGULAR: dict[str, str] = {
    "attaquants": "Attaquant",
    "milieux":    "Milieu",
    "défenseurs": "Défenseur",
}
# Filtre → clé interne
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
    flag = NATIONALITY_FLAGS.get(nat, "")
    return f"{flag} {nat}".strip() if flag else nat


# ─────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
    background-color: #0a1628 !important;
    color: #ffffff;
}
#MainMenu, footer { visibility: hidden; }
header { display: none !important; }
.main .block-container {
    padding: 2rem 2.5rem 3rem !important;
    max-width: 1380px !important;
}

/* ── Inputs & selectbox ── */
.stTextInput > div > div > input,
.stSelectbox > div > div > div {
    background-color: #0d1e35 !important;
    color: #e8f4ff !important;
    border: 1px solid #1e3a5f !important;
    border-radius: 8px !important;
    font-size: 13px !important;
    font-family: 'Inter', sans-serif !important;
}
.stTextInput > div > div > input::placeholder { color: #2e4d6b !important; }
.stTextInput > div > div > input:focus,
.stSelectbox > div > div > div:focus {
    border-color: #00d4ff !important;
    box-shadow: 0 0 0 3px rgba(0,212,255,0.10) !important;
}
label[data-testid="stWidgetLabel"] { display: none !important; }

/* ── Buttons ── */
.stButton > button {
    background: #0d1e35 !important;
    color: #00d4ff !important;
    border: 1px solid #1e3a5f !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    padding: 0.4rem 1rem !important;
    transition: all .15s;
    font-family: 'Inter', sans-serif !important;
}
.stButton > button:hover {
    background: #1a2e4a !important;
    border-color: #00d4ff !important;
}

/* ── Spinner ── */
.stSpinner > div { border-top-color: #00d4ff !important; }

/* ── Images ── */
img { border-radius: 12px; display: block; }

/* ── Alertes ── */
.stAlert { border-radius: 10px; }

/* ── Photo centrée ── */
[data-testid="stImage"] { display:flex !important; justify-content:center !important; }
[data-testid="stImage"] > img { display:block !important; margin:0 auto !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: #0a1628; }
::-webkit-scrollbar-thumb { background: #1a2e4a; border-radius: 3px; }

/* ── Masquer le menu "⋮" des en-têtes de colonnes du tableau ── */
[data-testid="stDataFrameColumnMenuTarget"] { display: none !important; }
</style>
"""


# ─────────────────────────────────────────────
# COMPOSANTS HTML
# ─────────────────────────────────────────────

def section_title(text: str) -> str:
    return (
        f'<div style="font-size:11px;font-weight:800;color:#2e6b8a;letter-spacing:2px;'
        f'text-transform:uppercase;margin-bottom:14px;margin-top:6px;">{text}</div>'
    )


def _row(label: str, value: str, last: bool = False) -> str:
    border = "" if last else "border-bottom:1px solid #101e30;"
    return (
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;'
        f'padding:8px 0;{border}">'
        f'<span style="color:#2e4d6b;font-size:11px;font-weight:700;'
        f'text-transform:uppercase;letter-spacing:.8px;flex-shrink:0;padding-top:1px;">{label}</span>'
        f'<span style="color:#ddeeff;font-size:13px;font-weight:600;'
        f'text-align:right;padding-left:12px;line-height:1.3;">{value}</span>'
        f'</div>'
    )


def card_identity(tm: dict | None, us: dict) -> str:
    name     = (tm or {}).get("full_name")     or us.get("player_name", "—")
    club     = (tm or {}).get("club")          or us.get("team", "—")
    logo_url = (tm or {}).get("club_logo_url", "N/A")
    age      = (tm or {}).get("dob_age",       "—")
    nat      = (tm or {}).get("nationality",   "—")
    pos_raw  = (tm or {}).get("position",      "—")
    pos      = _normalize_position(pos_raw) if pos_raw not in ("—", "N/A") else pos_raw
    val      = (tm or {}).get("market_value",  "—")
    ctr      = (tm or {}).get("contract_expiry","—")
    mins     = us.get("minutes", 0)
    games    = us.get("games", 0)

    logo_html = ""
    if logo_url and logo_url not in ("N/A", ""):
        logo_html = (
            f'<img src="{logo_url}" '
            f'style="width:28px;height:28px;object-fit:contain;'
            f'border-radius:4px;flex-shrink:0;" />'
        )

    club_block = (
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;">'
        f'{logo_html}'
        f'<div style="font-size:10px;color:#00d4ff;font-weight:700;'
        f'letter-spacing:2px;">{club.upper()}</div>'
        f'</div>'
    )

    rows = "".join([
        _row("Âge / naissance", age),
        _row("Nationalité",     _nat_with_flag(nat)),
        _row("Poste",           pos),
        _row("Valeur marchande", val),
        _row("Fin de contrat",  ctr),
        _row("Temps de jeu",    f"{mins} min · {games} matchs", last=True),
    ])

    return (
        f'<div style="background:#0d1e35;border:1px solid #1a2e4a;border-radius:14px;'
        f'padding:22px 24px 14px 24px;box-sizing:border-box;height:100%;">'
        f'<div style="font-size:22px;font-weight:900;color:#fff;line-height:1.15;'
        f'margin-bottom:3px;">{name}</div>'
        f'{club_block}{rows}</div>'
    )


def card_photo_placeholder() -> str:
    return (
        '<div style="background:#0d1e35;border:1px solid #1a2e4a;border-radius:14px;'
        'display:flex;align-items:center;justify-content:center;'
        'min-height:200px;color:#2e4d6b;font-size:48px;">👤</div>'
    )


def _pct_color(pct: float) -> str:
    if pct >= 85: return "#00d4ff"
    if pct >= 67: return "#88dd44"
    if pct >= 33: return "#ffaa00"
    return "#ff4444"


def _pct_label(pct: float) -> str:
    if pct >= 85: return "Élite"
    if pct >= 67: return "Bon"
    if pct >= 33: return "Correct"
    return "Faible"


def card_stat(
    label: str,
    value: float,
    pct: float | None,
    rank: int | None = None,
    total: int | None = None,
    pos_group: str = "joueurs",
    tooltip: str = "",
) -> str:
    tooltip_html = ""
    if tooltip:
        tooltip_html = (
            f'<style>'
            f'.kpi-i{{position:absolute;top:8px;right:8px;width:14px;height:14px;'
            f'background:#1e3a5f;border:1.5px solid #00d4ff;border-radius:50%;'
            f'color:#00d4ff;font-size:8px;font-weight:700;cursor:help;'
            f'user-select:none;display:inline-flex;align-items:center;'
            f'justify-content:center;line-height:1;font-style:normal;}}'
            f'.kpi-i::after{{content:\'\';display:none;position:absolute;right:0;top:20px;'
            f'background:#091524;border:1px solid #1a2e4a;border-radius:8px;'
            f'padding:8px 10px;font-size:11px;color:#c8dcf0;width:200px;'
            f'line-height:1.55;z-index:999;text-align:left;white-space:normal;'
            f'box-shadow:0 4px 16px rgba(0,0,0,.6);}}'
            f'.kpi-i:hover::after{{content:attr(data-tip);display:block;}}'
            f'</style>'
            f'<span class="kpi-i" data-tip="{tooltip}">i</span>'
        )

    if pct is None:
        inner = '<div style="font-size:11px;color:#2e4d6b;margin-top:8px;">—</div>'
    else:
        color = _pct_color(pct)
        lbl   = _pct_label(pct)
        bar   = (
            f'<div style="background:#101e30;border-radius:3px;height:4px;'
            f'overflow:hidden;margin:5px 0 5px;">'
            f'<div style="background:{color};width:{int(pct)}%;height:4px;'
            f'border-radius:3px;"></div></div>'
        )
        rank_str = (
            f'<div style="font-size:10px;color:#2e4d6b;font-weight:600;">'
            f'{rank}e / {total} {pos_group}</div>'
            if rank is not None and total is not None else ""
        )
        inner = (
            f'<div style="font-size:12px;color:{color};font-weight:800;'
            f'letter-spacing:.3px;margin-top:7px;">{lbl}</div>'
            f'{bar}{rank_str}'
        )

    return (
        f'<div style="background:#0d1e35;border:1px solid #1a2e4a;border-radius:14px;'
        f'padding:18px 12px;text-align:center;box-sizing:border-box;'
        f'height:100%;position:relative;">'
        f'{tooltip_html}'
        f'<div style="font-size:10px;color:#2e4d6b;font-weight:700;letter-spacing:1.2px;'
        f'text-transform:uppercase;margin-bottom:10px;">{label}</div>'
        f'<div style="font-size:30px;font-weight:900;color:#fff;'
        f'line-height:1;letter-spacing:-1px;">{value:.3f}</div>'
        f'{inner}</div>'
    )


def card_raw_stats(games: int, minutes: int, goals: int, assists: int) -> str:
    items = [("Matchs", games), ("Minutes", minutes), ("Buts", goals), ("Assists", assists)]
    cells = ""
    for i, (lbl, val) in enumerate(items):
        border = "border-right:1px solid #1a2e4a;" if i < len(items) - 1 else ""
        cells += (
            f'<div style="flex:1;text-align:center;padding:16px 8px;{border}">'
            f'<div style="font-size:36px;font-weight:900;color:#fff;'
            f'line-height:1;letter-spacing:-1.5px;">{val}</div>'
            f'<div style="font-size:10px;color:#2e4d6b;font-weight:700;'
            f'letter-spacing:1.2px;text-transform:uppercase;margin-top:6px;">{lbl}</div>'
            f'</div>'
        )
    return (
        f'<div style="background:#0d1e35;border:1px solid #1a2e4a;border-radius:14px;'
        f'display:flex;box-sizing:border-box;overflow:hidden;">{cells}</div>'
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
    """
    Selectbox avec autocomplétion pour naviguer vers un joueur.
    Le typing dans le dropdown filtre les options en temps réel.
    """
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
        # Clear explore table selection to prevent re-navigation on return
        st.session_state.pop("explore_df", None)
        st.session_state["view"]   = "player"
        st.session_state["player"] = name
        st.rerun()


# ─────────────────────────────────────────────
# VUE 1 — LANDING PAGE
# ─────────────────────────────────────────────

def view_home() -> None:
    records = _load_records()
    n_players = len(records)

    # ── Logo centré ──────────────────────────────────────────────────────────
    _, col_mid, _ = st.columns([1, 2, 1])
    with col_mid:
        st.html(
            '<div style="display:flex;flex-direction:column;align-items:center;gap:6px;">'
            '<div style="width:64px;height:64px;'
            'background:linear-gradient(135deg,#00d4ff,#0044cc);'
            'border-radius:16px;display:flex;align-items:center;justify-content:center;'
            'font-size:32px;box-shadow:0 4px 30px rgba(0,212,255,.3);">⚽</div>'
            '<div style="font-size:42px;font-weight:900;letter-spacing:-2px;'
            'background:linear-gradient(90deg,#fff 0%,#00d4ff 100%);'
            '-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
            'line-height:1.1;margin-top:4px;">xScout</div>'
            '<div style="font-size:11px;color:#2e6b8a;letter-spacing:3px;font-weight:700;">'
            'FOOTBALL INTELLIGENCE PLATFORM</div>'
            f'<div style="font-size:12px;color:#1e3a5f;margin-top:6px;letter-spacing:.5px;">'
            f'🇫🇷 &nbsp;{n_players} joueurs analysés · Ligue 1 2025/26</div>'
            '</div>'
        )

    st.html('<div style="margin-top:36px;"></div>')

    # ── Deux cartes côte à côte ──────────────────────────────────────────────
    col_l, col_r = st.columns(2, gap="large")

    # ── Carte gauche : recherche ─────────────────────────────────────────────
    with col_l:
        st.html(
            '<div style="background:#0d1e35;border:1px solid #1a2e4a;border-radius:16px;'
            'padding:28px 24px 8px;">'
            '<div style="font-size:13px;font-weight:800;color:#00d4ff;'
            'letter-spacing:2px;text-transform:uppercase;margin-bottom:18px;">'
            '🔍 &nbsp;Rechercher un joueur</div>'
            '<div style="font-size:12px;color:#4a6d8a;margin-bottom:16px;">'
            'Tapez le nom d\'un joueur pour filtrer la liste.</div>'
            '</div>'
        )
        _search_bar(records, key="home_search")

    # ── Carte droite : explorer ──────────────────────────────────────────────
    with col_r:
        st.html(
            '<div style="background:#0d1e35;border:1px solid #1a2e4a;border-radius:16px;'
            'padding:28px 24px 24px;">'
            '<div style="font-size:13px;font-weight:800;color:#00d4ff;'
            'letter-spacing:2px;text-transform:uppercase;margin-bottom:18px;">'
            '📊 &nbsp;Explorer la Ligue 1</div>'
            '<div style="font-size:13px;color:#4a6d8a;margin-bottom:24px;line-height:1.6;">'
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
    # Cache-bust une fois par session
    _CACHE_VERSION = "v3-fr"
    if st.session_state.get("_cache_version") != _CACHE_VERSION:
        _get_shot_map_fig.clear()
        _get_understat.clear()
        st.session_state["_cache_version"] = _CACHE_VERSION

    records = _load_records()

    # ── Header ────────────────────────────────────────────────────────────────
    col_back, col_logo, col_search = st.columns([1, 3, 3])

    with col_back:
        if st.button("← Retour", key="back_player"):
            st.session_state["view"] = "home"
            st.rerun()

    with col_logo:
        st.html(
            '<div style="display:flex;align-items:center;gap:10px;padding:4px 0 4px;">'
            '<div style="width:32px;height:32px;'
            'background:linear-gradient(135deg,#00d4ff,#0044cc);'
            'border-radius:8px;display:flex;align-items:center;justify-content:center;'
            'font-size:16px;flex-shrink:0;">⚽</div>'
            '<div style="font-size:22px;font-weight:900;letter-spacing:-1px;'
            'background:linear-gradient(90deg,#fff 0%,#00d4ff 100%);'
            '-webkit-background-clip:text;-webkit-text-fill-color:transparent;">'
            'xScout</div>'
            '<div style="font-size:10px;color:#1e4060;letter-spacing:2px;font-weight:700;">'
            '🇫🇷 LIGUE 1 · 2025/26</div>'
            '</div>'
        )

    with col_search:
        _search_bar(records, key="player_search")

    st.html('<hr style="border:none;border-top:1px solid #101e30;margin:.4rem 0 1.6rem;">')

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
                shot_fig.update_layout(
                    title=dict(
                        text=f"<b>{pname}</b>  ·  Ligue 1  ·  {n_goals} buts / {n_shots} tirs",
                        x=0.5, xanchor="center",
                        font=dict(color="#e6edf3", size=13, family="Inter"),
                    ),
                    margin=dict(t=100, l=20, r=20, b=20),
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
                radar_fig.update_layout(
                    title=dict(
                        text=f"<b>{pname}</b>  ·  {pos_disp}  ·  {mins_disp} min",
                        x=0.5, xanchor="center",
                        font=dict(color="#e6edf3", size=13, family="Inter"),
                    ),
                    margin=dict(t=100, l=20, r=20, b=20),
                )
        except Exception as e:
            errors["radar"] = str(e)

    # ── Section 1 : profil ────────────────────────────────────────────────────
    st.html(section_title("Profil joueur"))

    col_photo, col_identity = st.columns([1, 3], gap="medium")

    with col_photo:
        if photo_bytes:
            import base64
            mime = "image/png" if photo_bytes[:4] == b'\x89PNG' else "image/jpeg"
            b64  = base64.b64encode(photo_bytes).decode()
            tm_link = ""
            if tm and tm.get("profile_url"):
                tm_link = (
                    f'<div style="margin-top:8px;">'
                    f'<a href="{tm["profile_url"]}" target="_blank" '
                    f'style="font-size:11px;color:#2e6b8a;text-decoration:none;'
                    f'letter-spacing:.5px;">↗ Transfermarkt</a></div>'
                )
            st.html(
                f'<div style="text-align:center;">'
                f'<img src="data:{mime};base64,{b64}" '
                f'style="width:150px;border-radius:12px;display:inline-block;" />'
                f'{tm_link}</div>'
            )
        else:
            st.html(card_photo_placeholder())

    with col_identity:
        st.html(card_identity(tm, us))

    # ── Section 2 : saison ────────────────────────────────────────────────────
    st.html('<div style="margin-top:20px;"></div>')
    st.html(section_title("Saison en cours"))
    minutes = us.get("minutes", 0)
    goals   = us.get("goals", 0)
    assists = us.get("assists", 0)
    games   = us.get("games", 0)
    if games == 0 and minutes > 0:
        games = max(1, round(minutes / 75))
    st.html(card_raw_stats(games, minutes, goals, assists))

    # ── Section 3 : stats /90 ────────────────────────────────────────────────
    st.html('<div style="margin-top:28px;"></div>')
    st.html(section_title("Stats avancées / 90 min"))

    cols      = st.columns(5, gap="medium")
    pos_group = (ctx or {}).get("pos_group", "joueurs")
    total_pos = (ctx or {}).get("total")
    ranks_map = (ctx or {}).get("ranks", {})
    pos_label = POS_SINGULAR.get(pos_group, pos_group)

    for col, (key, label, tip) in zip(cols, METRICS):
        if pct:
            val = pct.get(key, 0.0)
        else:
            raw = us.get(key.replace("_90", ""), 0.0)
            val = raw / (minutes or 1) * 90
        p    = (pct or {}).get("percentiles", {}).get(key)
        rank = ranks_map.get(key)
        with col:
            st.html(card_stat(label, val, p,
                              rank=rank, total=total_pos, pos_group=pos_label,
                              tooltip=tip))

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

    # ── Footer ────────────────────────────────────────────────────────────────
    st.html(
        '<hr style="border:none;border-top:1px solid #101e30;margin:2.5rem 0 1rem;">'
        '<div style="text-align:center;font-size:11px;color:#1e4060;letter-spacing:.5px;">'
        'Sources : Understat · Transfermarkt &nbsp;·&nbsp; Ligue 1 2025/26 '
        '· Percentiles calculés parmi les joueurs ≥ 180 min</div>'
    )


# ─────────────────────────────────────────────
# VUE 3 — EXPLORE
# ─────────────────────────────────────────────

def view_explore() -> None:
    records   = _load_records()
    all_clubs = sorted({r.get("team", "") for r in records if r.get("team")})

    # ── Header ────────────────────────────────────────────────────────────────
    col_back, col_title, col_search = st.columns([1, 3, 3])

    with col_back:
        if st.button("← Retour", key="back_explore"):
            st.session_state["view"] = "home"
            st.rerun()

    with col_title:
        st.html(
            '<div style="display:flex;align-items:center;gap:10px;padding:4px 0 4px;">'
            '<div style="font-size:22px;font-weight:900;letter-spacing:-1px;'
            'background:linear-gradient(90deg,#fff 0%,#00d4ff 100%);'
            '-webkit-background-clip:text;-webkit-text-fill-color:transparent;">'
            'xScout</div>'
            '<div style="font-size:14px;color:#2e6b8a;font-weight:700;">'
            '🇫🇷 Ligue 1 · 2025/26</div>'
            '</div>'
        )

    with col_search:
        _search_bar(records, key="explore_search")

    st.html('<hr style="border:none;border-top:1px solid #101e30;margin:.4rem 0 1.2rem;">')

    # ── Filtres ───────────────────────────────────────────────────────────────
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

    # ── Filtrage + tri par défaut (npxG/90 desc) ──────────────────────────────
    filtered = records
    if pos_filter != "Tous":
        pg = POS_FILTER_MAP.get(pos_filter, "")
        filtered = [r for r in filtered if r.get("position_group") == pg]
    if club_filter != "Tous les clubs":
        filtered = [r for r in filtered if r.get("team") == club_filter]

    filtered = sorted(filtered, key=lambda r: r.get("npxG_90", 0.0), reverse=True)

    n_total = len(filtered)

    # ── Info bar ──────────────────────────────────────────────────────────────
    st.html(
        f'<div style="font-size:12px;color:#2e6b8a;margin-bottom:6px;">'
        f'{n_total} joueurs · Cliquez sur un joueur pour voir sa fiche · '
        f'Cliquez sur un en-tête pour trier</div>'
    )

    # ── Tableau : tous les joueurs, scrollable ────────────────────────────────
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
    # ── Invalider le cache _load_records une seule fois par session ───────────
    _REC_VER = "v4-goals"
    if st.session_state.get("_rec_ver") != _REC_VER:
        _load_records.clear()
        st.session_state["_rec_ver"] = _REC_VER

    # ── Gérer les navigations JS (URL params) AVANT tout rendu ───────────────
    _click = st.query_params.get("_player_click", "")
    if _click:
        st.session_state["view"]   = "player"
        st.session_state["player"] = _click
        st.query_params.clear()
        st.rerun()

    st.markdown(_CSS, unsafe_allow_html=True)

    if "view" not in st.session_state:
        st.session_state["view"] = "home"

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
