"""
Utilities for parsing Diplomacy game phase strings.

This module provides an Enum for phase types (PhaseType) and functions
to extract the phase type (e.g., Movement, Retreat, Build/Adjustment)
and the year from standard Diplomacy game phase strings.
"""

import logging
from typing import Optional, TYPE_CHECKING
from enum import Enum
import re

if TYPE_CHECKING:
    from diplomacy import Game

logger = logging.getLogger(__name__)

__all__ = [
    "PhaseType",
    "get_phase_type_from_game",
    "extract_year_from_phase",
    "VALID_SEASON_KEYWORDS",
    "VALID_SEASON_INITIALS",
]

VALID_SEASON_KEYWORDS = {
    "SPRING": "S",
    "SPR": "S",
    "SUMMER": "S",
    "SUM": "S",
    "FALL": "F",
    "FAL": "F",
    "AUTUMN": "A",
    "AUT": "A",
    "WINTER": "W",
    "WIN": "W",
}
VALID_SEASON_INITIALS = {"S", "F", "A", "W"}


class PhaseType(Enum):
    MVT = "M"
    RET = "R"
    BLD = "A"


def get_phase_type_from_game(game: "Game") -> str:
    """Extracts the phase type character from the current phase string (e.g., 'M', 'R', 'A')."""
    phase_str_orig = game.get_current_phase()
    if not phase_str_orig:
        logger.warning("game.get_current_phase() returned an empty or None string.")
        return "-"

    phase_str_upper = phase_str_orig.upper()

    if phase_str_upper in ("FORMING", "COMPLETED"):
        return "-"

    parts = phase_str_upper.split()
    year_val = extract_year_from_phase(phase_str_orig)

    first_part_is_valid_season_or_compact_season_year = True
    if len(parts) > 1 and year_val is not None:
        
        if _is_valid_season_keyword(parts[0]):
            first_part_is_valid_season_or_compact_season_year = True
        elif (
            len(parts[0]) > 0
            and parts[0][0] in VALID_SEASON_INITIALS
            and extract_year_from_phase(parts[0]) == year_val
        ):
            first_part_is_valid_season_or_compact_season_year = True
        else:
            first_part_is_valid_season_or_compact_season_year = False
    elif len(parts) == 1 and year_val is not None:
        pass

    
    if (
        (
            "MOVEMENT" in phase_str_upper
            and year_val is not None
            and first_part_is_valid_season_or_compact_season_year
        )
        or (
            " " not in phase_str_orig
            and phase_str_upper.endswith(PhaseType.MVT.value)
            and _is_valid_compact_form(phase_str_orig, PhaseType.MVT.value)
        )
        or (
            " " not in phase_str_orig
            and phase_str_upper.endswith("MVT")
            and _is_valid_compact_form(phase_str_orig, "MVT")
        )
        or (
            len(parts) > 0
            and parts[-1] == PhaseType.MVT.value
            and year_val is not None
            and first_part_is_valid_season_or_compact_season_year
        )
        or ("MVT" in parts and year_val is not None and first_part_is_valid_season_or_compact_season_year)
    ):
        return PhaseType.MVT.value

    
    if (
        (
            "RETREAT" in phase_str_upper
            and year_val is not None
            and first_part_is_valid_season_or_compact_season_year
        )
        or (
            " " not in phase_str_orig
            and phase_str_upper.endswith(PhaseType.RET.value)
            and _is_valid_compact_form(phase_str_orig, PhaseType.RET.value)
        )
        or (
            len(parts) > 0
            and parts[-1] == PhaseType.RET.value
            and year_val is not None
            and first_part_is_valid_season_or_compact_season_year
        )
        or ("RET" in parts and year_val is not None and first_part_is_valid_season_or_compact_season_year)
    ):
        return PhaseType.RET.value

    
    if (
        (
            ("ADJUSTMENT" in phase_str_upper or "BUILD" in phase_str_upper)
            and year_val is not None
            and first_part_is_valid_season_or_compact_season_year
        )
        or (
            " " not in phase_str_orig
            and phase_str_upper.endswith(PhaseType.BLD.value)
            and _is_valid_compact_form(phase_str_orig, PhaseType.BLD.value)
        )
        or (
            " " not in phase_str_orig
            and phase_str_upper.startswith("A")
            and phase_str_upper.endswith("B")
            and _is_valid_compact_form(phase_str_orig, "B")
        )
        or (
            len(parts) > 0
            and parts[-1] == PhaseType.BLD.value
            and year_val is not None
            and first_part_is_valid_season_or_compact_season_year
        )
        or ("BLD" in parts and year_val is not None and first_part_is_valid_season_or_compact_season_year)
    ):
        return PhaseType.BLD.value

    logger.error(f"Could not determine phase type for '{phase_str_orig}'. This is an unhandled phase format.")
    raise RuntimeError(f"Unknown or unhandled phase format: '{phase_str_orig}'. Cannot determine phase type.")


def _is_valid_season_keyword(season_part: str) -> bool:
    """Checks if the given part is a recognized season keyword or abbreviation."""
    return season_part.upper() in VALID_SEASON_KEYWORDS


def _is_valid_compact_form(phase_str: str, suffix: str) -> bool:
    """Checks if a compact form like 'S1901M' has a valid season initial and year before the suffix."""
    phase_str_upper = phase_str.upper()
    suffix_upper = suffix.upper()
    if not phase_str_upper.endswith(suffix_upper):
        return False

    prefix = phase_str_upper[: -len(suffix_upper)]
    if not prefix:
        return False

    season_initial = prefix[0]

    if suffix_upper == "B":
        if season_initial != "A":
            return False
    elif season_initial not in VALID_SEASON_INITIALS:
        return False

    if len(prefix) < 5:
        return False
    year_part = prefix[1:5]
    return year_part.isdigit() and len(year_part) == 4


def extract_year_from_phase(
    phase_name: Optional[str],
) -> Optional[int]:
    """Extracts the year as int from a phase string like 'S1901M' or 'SPRING 1901 MOVEMENT'."""
    if not phase_name:
        return None

    match = re.search(r"\b(\d{4})\b", phase_name)
    if match:
        return int(match.group(1))

    if len(phase_name) >= 5 and phase_name[1:5].isdigit():
        if phase_name[0].isalpha():
            return int(phase_name[1:5])

    return None
