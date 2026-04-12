#!/usr/bin/env python3
"""
claude_report.py — Génère un rapport de scouting via l'API Anthropic

Récupère les données depuis Understat et Transfermarkt (via player_data.py),
lit le prompt système depuis prompt_system.txt, et appelle Claude pour
produire un rapport structuré affiché dans le terminal.

Usage :
    python3 claude_report.py
    python3 claude_report.py "Ousmane Dembélé" --league EPL --season 2024 --mode pro

Prérequis :
    export ANTHROPIC_API_KEY="sk-ant-..."
"""

import os
import sys
import argparse
from pathlib import Path

import anthropic

from player_data import fetch_understat_data, fetch_transfermarkt_data

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

MODEL = "claude-sonnet-4-5"
PROMPT_SYSTEM_FILE = Path(__file__).parent / "prompt_system.txt"


# ─────────────────────────────────────────────
# UTILITAIRES
# ─────────────────────────────────────────────

def load_system_prompt() -> str:
    """Lit le prompt système depuis prompt_system.txt."""
    try:
        return PROMPT_SYSTEM_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Fichier de prompt système introuvable : {PROMPT_SYSTEM_FILE}\n"
            "  Vérifiez que prompt_system.txt est dans le même répertoire."
        )


def format_player_data(understat: dict | None, tm: dict | None, mode: str) -> str:
    """
    Formate les données du joueur en texte structuré pour l'API Claude.

    Le texte inclut le paramètre `mode` en tête afin que Claude sache
    quel style de rapport produire (fan / pro).
    """
    lines = [
        f"mode: {mode}",
        "",
    ]

    # ── Profil Transfermarkt ───────────────────────────────────────────────
    if tm:
        lines += [
            "## PROFIL (Transfermarkt)",
            f"Nom complet      : {tm.get('full_name', 'N/A')}",
            f"Date de nais./Âge: {tm.get('dob_age', 'N/A')}",
            f"Nationalité      : {tm.get('nationality', 'N/A')}",
            f"Poste            : {tm.get('position', 'N/A')}",
            f"Club actuel      : {tm.get('club', 'N/A')}",
            f"Valeur marchande : {tm.get('market_value', 'N/A')}",
            f"Fin de contrat   : {tm.get('contract_expiry', 'N/A')}",
            f"Profil complet   : {tm.get('profile_url', 'N/A')}",
            "",
        ]
    else:
        lines += [
            "## PROFIL (Transfermarkt)",
            "Données indisponibles.",
            "",
        ]

    # ── Stats Understat ────────────────────────────────────────────────────
    if understat:
        lines += [
            f"## STATS SAISON {understat['season']} (Understat — {understat['league']})",
            f"Joueur           : {understat.get('player_name', 'N/A')}",
            f"Minutes jouées   : {understat['minutes']}",
            f"Buts             : {understat['goals']}",
            f"Passes décisives : {understat['assists']}",
            f"Tirs tentés      : {understat['shots']}",
            "",
            "### Métriques attendues (expected)",
            f"xG               : {understat['xG']:.3f}",
            f"npxG             : {understat['npxG']:.3f}",
            f"xA               : {understat['xA']:.3f}",
            f"xGChain          : {understat['xGChain']:.3f}",
            f"xGBuildup        : {understat['xGBuildup']:.3f}",
            "",
        ]

        shots = understat.get("shot_coords", [])
        if shots:
            goals_scored = [s for s in shots if s["result"] == "Goal"]
            lines += [
                f"### Cartographie des tirs ({len(shots)} tirs, {len(goals_scored)} buts)",
                f"{'X':>7}  {'Y':>7}  {'xG':>7}  {'Résultat':<20}  Situation",
                f"{'─'*7}  {'─'*7}  {'─'*7}  {'─'*20}  {'─'*15}",
            ]
            for s in shots:
                lines.append(
                    f"{s['x']:>7.3f}  {s['y']:>7.3f}  {s['xG']:>7.4f}"
                    f"  {s['result']:<20}  {s.get('situation', '')}"
                )
            lines.append("")
        else:
            lines += [
                "### Cartographie des tirs",
                "Aucun tir individuel disponible pour cette saison.",
                "",
            ]
    else:
        lines += [
            "## STATS (Understat)",
            "Données indisponibles.",
            "",
        ]

    return "\n".join(lines)


# ─────────────────────────────────────────────
# PIPELINE PRINCIPAL
# ─────────────────────────────────────────────

def generate_report(
    player_name: str,
    league: str = "Ligue_1",
    season: str = "2024",
    mode: str = "fan",
) -> None:
    """
    Pipeline complet :
      1. Récupère les données depuis Understat et Transfermarkt
      2. Lit le prompt système depuis prompt_system.txt
      3. Formate les données joueur en texte structuré
      4. Appelle l'API Anthropic (streaming) avec le prompt système
         et les données formatées
      5. Affiche le rapport dans le terminal
    """
    sep = "─" * 62

    # ── Étape 1 : collecte des données ────────────────────────────────────
    print(f"\n{sep}")
    print(f"  Football Scouting Pipeline — {player_name}")
    print(sep)

    print("\n[1/2] Understat ...")
    understat_data = None
    try:
        understat_data = fetch_understat_data(player_name, league=league, season=season)
        print("  OK")
    except ValueError as e:
        print(f"  ERREUR : {e}")
    except ConnectionError as e:
        print(f"  ERREUR RÉSEAU : {e}")
    except Exception as e:
        print(f"  ERREUR INATTENDUE : {type(e).__name__}: {e}")

    print("\n[2/2] Transfermarkt ...")
    tm_data = None
    try:
        tm_data = fetch_transfermarkt_data(player_name)
        print("  OK")
    except ValueError as e:
        print(f"  ERREUR : {e}")
    except ConnectionError as e:
        print(f"  ERREUR RÉSEAU : {e}")
    except Exception as e:
        print(f"  ERREUR INATTENDUE : {type(e).__name__}: {e}")

    if understat_data is None and tm_data is None:
        print("\n  Aucune donnée récupérée. Vérifiez le nom du joueur et votre connexion.")
        sys.exit(1)

    # ── Étape 2 : prompt système ──────────────────────────────────────────
    system_prompt = load_system_prompt()

    # ── Étape 3 : formatage des données ──────────────────────────────────
    player_text = format_player_data(understat_data, tm_data, mode)

    # ── Étape 4 : vérification de la clé API ─────────────────────────────
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "\n  ERREUR : variable d'environnement ANTHROPIC_API_KEY non définie.\n"
            "  Définissez-la avec : export ANTHROPIC_API_KEY='sk-ant-...'"
        )
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # ── Étape 5 : appel API et affichage du rapport ───────────────────────
    print(f"\n{'═' * 62}")
    print(f"  RAPPORT — {player_name.upper()}  [mode: {mode}]")
    print(f"{'═' * 62}\n")

    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=2048,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    # Cache le prompt système (stable entre les requêtes)
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {"role": "user", "content": player_text}
            ],
        ) as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)

    except anthropic.AuthenticationError:
        print("\n\n  ERREUR : clé API invalide. Vérifiez ANTHROPIC_API_KEY.")
        sys.exit(1)
    except anthropic.RateLimitError:
        print("\n\n  ERREUR : limite de requêtes atteinte. Réessayez dans quelques instants.")
        sys.exit(1)
    except anthropic.APIStatusError as e:
        print(f"\n\n  ERREUR API ({e.status_code}) : {e.message}")
        sys.exit(1)
    except anthropic.APIConnectionError:
        print("\n\n  ERREUR RÉSEAU : vérifiez votre connexion internet.")
        sys.exit(1)

    print(f"\n\n{'═' * 62}\n")


# ─────────────────────────────────────────────
# POINT D'ENTRÉE
# ─────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Génère un rapport de scouting football via Claude.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemples :\n"
            "  python3 claude_report.py\n"
            "  python3 claude_report.py 'Ousmane Dembélé' --league EPL --season 2024 --mode pro\n"
            "\nLigues valides : Ligue_1, EPL, La_Liga, Bundesliga, Serie_A, RFPL"
        ),
    )
    parser.add_argument(
        "player",
        nargs="?",
        default="Khvicha Kvaratskhelia",
        help="Nom du joueur (défaut : Khvicha Kvaratskhelia)",
    )
    parser.add_argument(
        "--league",
        default="Ligue_1",
        help="Code ligue Understat (défaut : Ligue_1)",
    )
    parser.add_argument(
        "--season",
        default="2024",
        help="Année de début de saison (défaut : 2024)",
    )
    parser.add_argument(
        "--mode",
        default="fan",
        choices=["fan", "pro"],
        help="Style du rapport — fan (défaut) ou pro",
    )
    args = parser.parse_args()

    generate_report(
        player_name=args.player,
        league=args.league,
        season=args.season,
        mode=args.mode,
    )


if __name__ == "__main__":
    main()
