import logging
from typing import Optional, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from diplomacy import Game # This import is necessary for type hinting

# It's good practice to have a module-level logger
logger = logging.getLogger(__name__)

class PhaseType(Enum): # Moving PhaseType here as it's closely related to parsing
    MVT = "M"
    RET = "R"
    BLD = "A"

def get_phase_type_from_game(game: "Game") -> str:
    """Extracts the phase type character from the current phase string (e.g., 'M', 'R', 'A')."""
    phase_str_orig = game.get_current_phase()
    if not phase_str_orig:
        logger.warning("game.get_current_phase() returned an empty or None string.")
        # Depending on how downstream code handles it, or if Game object guarantees non-empty phase.
        # For now, assume '-' is a safe default for unparsable/empty.
        return "-"

    phase_str_upper = phase_str_orig.upper()

    if phase_str_upper in ("FORMING", "COMPLETED"):  # Check these early
        return "-"

    parts = phase_str_upper.split()

    # Check for specific keywords (full words) or their abbreviations (as parts)
    if (
        "ADJUSTMENT" in phase_str_upper
        or "BUILD" in phase_str_upper
        or "BLD" in parts
    ):
        return PhaseType.BLD.value
    elif "MOVEMENT" in phase_str_upper or "MVT" in parts:
        return PhaseType.MVT.value
    elif "RETREAT" in phase_str_upper or "RET" in parts:
        return PhaseType.RET.value

    # Fallback for compact forms like S1901M, F1901R, W1901A (no spaces)
    # Ensure it's a single segment and ends with one of the PhaseType enum values
    if " " not in phase_str_orig and phase_str_orig[-1].upper() in [
        pt.value for pt in PhaseType
    ]:
        return phase_str_orig[-1].upper()

    # If phase type cannot be determined after all checks
    logger.error(
        f"Could not determine phase type for '{phase_str_orig}'. This is an unhandled phase format."
    )
    raise RuntimeError(
        f"Unknown or unhandled phase format: '{phase_str_orig}'. Cannot determine phase type."
    )

def _extract_year_from_phase(phase_name: str) -> Optional[int]:
    """Extracts the year as int from a phase string like 'S1901M' or 'SPRING 1901 MOVEMENT'."""
    # Try short format: S1901M, F1902R, etc.
    if phase_name and len(phase_name) >= 5 and phase_name[1:5].isdigit():
        return int(phase_name[1:5])
    # Try long format: SPRING 1901 MOVEMENT
    parts = phase_name.split()
    if len(parts) >= 2 and parts[1].isdigit():
        return int(parts[1])
    return None 