import logging
from typing import Optional, TYPE_CHECKING
from enum import Enum
import re

if TYPE_CHECKING:
    from diplomacy import Game # This import is necessary for type hinting

# It's good practice to have a module-level logger
logger = logging.getLogger(__name__)

VALID_SEASON_KEYWORDS = {
    "SPRING": "S", "SPR": "S",
    "SUMMER": "S", "SUM": "S", # Summer is often same as Spring for phases
    "FALL": "F", "FAL": "F",
    "AUTUMN": "A", "AUT": "A", # Autumn can be 'A' or 'F' in some notations
    "WINTER": "W", "WIN": "W"
}
VALID_SEASON_INITIALS = {"S", "F", "A", "W"}

class PhaseType(Enum): # Moving PhaseType here as it's closely related to parsing
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

    if phase_str_upper in ("FORMING", "COMPLETED"):  # Check these early
        return "-"

    parts = phase_str_upper.split()
    year_val = _extract_year_from_phase(phase_str_orig)

    first_part_is_valid_season_or_compact_season_year = True # Default true for single-word/compact forms
    if len(parts) > 1 and year_val is not None:
        # Check if the first part is a full season keyword e.g. "SPRING"
        if _is_valid_season_keyword(parts[0]):
            first_part_is_valid_season_or_compact_season_year = True
        # Check if the first part is a season initial + year e.g. "F1903" from "F1903 RET"
        elif len(parts[0]) > 0 and parts[0][0] in VALID_SEASON_INITIALS and _extract_year_from_phase(parts[0]) == year_val:
            first_part_is_valid_season_or_compact_season_year = True
        else:
            first_part_is_valid_season_or_compact_season_year = False
    elif len(parts) == 1 and year_val is not None: # For compact forms like S1901M, handled by _is_valid_compact_form
        pass # valid_season check is implicit in _is_valid_compact_form

    # Movement Phases (M)
    if (
        ("MOVEMENT" in phase_str_upper and year_val is not None and first_part_is_valid_season_or_compact_season_year) or
        (not " " in phase_str_orig and phase_str_upper.endswith(PhaseType.MVT.value) and _is_valid_compact_form(phase_str_orig, PhaseType.MVT.value)) or
        (not " " in phase_str_orig and phase_str_upper.endswith("MVT") and _is_valid_compact_form(phase_str_orig, "MVT")) or
        (len(parts) > 0 and parts[-1] == PhaseType.MVT.value and year_val is not None and first_part_is_valid_season_or_compact_season_year) or
        ("MVT" in parts and year_val is not None and first_part_is_valid_season_or_compact_season_year)
    ):
        return PhaseType.MVT.value

    # Retreat Phases (R)
    if (
        ("RETREAT" in phase_str_upper and year_val is not None and first_part_is_valid_season_or_compact_season_year) or
        (not " " in phase_str_orig and phase_str_upper.endswith(PhaseType.RET.value) and _is_valid_compact_form(phase_str_orig, PhaseType.RET.value)) or
        (len(parts) > 0 and parts[-1] == PhaseType.RET.value and year_val is not None and first_part_is_valid_season_or_compact_season_year) or
        ("RET" in parts and year_val is not None and first_part_is_valid_season_or_compact_season_year)
    ):
        return PhaseType.RET.value

    # Build/Adjustment Phases (A)
    if (
        (("ADJUSTMENT" in phase_str_upper or "BUILD" in phase_str_upper) and year_val is not None and first_part_is_valid_season_or_compact_season_year) or
        (not " " in phase_str_orig and phase_str_upper.endswith(PhaseType.BLD.value) and _is_valid_compact_form(phase_str_orig, PhaseType.BLD.value)) or
        (not " " in phase_str_orig and phase_str_upper.startswith("A") and phase_str_upper.endswith("B") and _is_valid_compact_form(phase_str_orig, "B")) or
        (len(parts) > 0 and parts[-1] == PhaseType.BLD.value and year_val is not None and first_part_is_valid_season_or_compact_season_year) or
        ("BLD" in parts and year_val is not None and first_part_is_valid_season_or_compact_season_year)
    ):
        return PhaseType.BLD.value

    # If phase type cannot be determined after all checks
    logger.error(
        f"Could not determine phase type for '{phase_str_orig}'. This is an unhandled phase format."
    )
    raise RuntimeError(
        f"Unknown or unhandled phase format: '{phase_str_orig}'. Cannot determine phase type."
    )

def _is_valid_season_keyword(season_part: str) -> bool:
    """Checks if the given part is a recognized season keyword or abbreviation."""
    return season_part.upper() in VALID_SEASON_KEYWORDS

def _is_valid_compact_form(phase_str: str, suffix: str) -> bool:
    """Checks if a compact form like 'S1901M' has a valid season initial and year before the suffix."""
    phase_str_upper = phase_str.upper()
    suffix_upper = suffix.upper()
    if not phase_str_upper.endswith(suffix_upper):
        return False

    prefix = phase_str_upper[:-len(suffix_upper)] 
    if not prefix: 
        return False

    season_initial = prefix[0]
    
    # Special handling for 'B' suffix (Build phase, typically Autumn)
    if suffix_upper == 'B':
        if season_initial != 'A': # For 'B' suffix, season initial MUST be 'A' (e.g., A1901B)
            return False
    # For other standard suffixes (M, R, A), season initial must be in VALID_SEASON_INITIALS
    elif season_initial not in VALID_SEASON_INITIALS:
        return False
            
    # Year check: expects season initial then 4 digits, e.g., S1901, A1901
    if len(prefix) < 5: # Needs at least one char for season + 4 for year
        return False
    year_part = prefix[1:5]
    return year_part.isdigit() and len(year_part) == 4

def _extract_year_from_phase(phase_name: Optional[str]) -> Optional[int]:
    """Extracts the year as int from a phase string like 'S1901M' or 'SPRING 1901 MOVEMENT'."""
    if not phase_name:  # Handle None or empty string input first
        return None

    # Try to find any 4-digit number in the string using regex, as it's most robust
    match = re.search(r'\b(\d{4})\b', phase_name)
    if match:
        return int(match.group(1))

    # Fallback for compact forms like S1901M if regex didn't catch it (e.g. no word boundaries)
    # and the phase_name is long enough and contains digits at expected place
    if len(phase_name) >= 5 and phase_name[1:5].isdigit():
        return int(phase_name[1:5])

    return None 