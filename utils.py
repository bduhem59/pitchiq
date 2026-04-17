#!/usr/bin/env python3
"""
utils.py — Utilitaires partagés PitchIQ
"""

import unicodedata


def normalize_tm_key(name: str) -> str:
    """
    Normalise un nom de joueur pour la recherche dans tm_cache.json.
    Correspond à la normalisation utilisée par build_tm_cache.py.
    """
    nfkd = unicodedata.normalize("NFKD", name.lower().strip())
    return nfkd.encode("ASCII", "ignore").decode("ASCII")


def get_position_group(tm_position: str, understat_position: str = "") -> str:
    """
    Retourne "Forward", "Midfielder", "Defender", "Goalkeeper" ou "Unknown".
    Priorité : Transfermarkt > Understat > "Unknown"

    IMPORTANT : vérifie Midfielder AVANT Forward
    pour éviter que "Attacking Midfield" soit classé Forward.
    """
    if tm_position and tm_position != "N/A":
        pos = tm_position.lower()

        # 1. Midfielder EN PREMIER
        if any(x in pos for x in [
            "midfield", "central mid", "defensive mid",
            "attacking mid", "left mid", "right mid",
        ]):
            return "Midfielder"

        # 2. Forward
        if any(x in pos for x in [
            "forward", "winger", "striker",
            "attack", "second striker",
        ]):
            return "Forward"

        # 3. Defender
        if any(x in pos for x in [
            "back", "defender", "centre-back",
            "left-back", "right-back",
            "wing-back", "libero",
        ]):
            return "Defender"

        # 4. Goalkeeper
        if "goalkeeper" in pos or "keeper" in pos:
            return "Goalkeeper"

    # Fallback Understat si TM non disponible
    if understat_position:
        first = understat_position.strip().split()[0]
        if first == "F":
            return "Forward"
        if first == "M":
            return "Midfielder"
        if first == "D":
            return "Defender"
        if first == "GK":
            return "Goalkeeper"

    return "Unknown"
