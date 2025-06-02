"""Generate engaging narrative summaries and transparently patch the Diplomacy
Game engine to use them.

Usage: simply import `ai_diplomacy.narrative` *before* the game loop starts
(e.g. at the top of `lm_game.py`).  Import side-effects monkey-patch
`diplomacy.engine.game.Game._generate_phase_summary` so that:

1. The original (statistical) summary logic still runs.
2. The returned text is stored in `GamePhaseData.statistical_summary`.
3. A short narrative is produced via a configured LLM and saved as the main
   `.summary`.
"""

from __future__ import annotations

import logging
import os
from typing import Callable
import llm  # Import the llm library

from diplomacy.engine.game import Game

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# AI_DIPLOMACY_NARRATIVE_MODEL can be set to a specific llm-compatible model ID.
# If not set, it will attempt to use the primary model from lm_game.py arguments.
DEFAULT_NARRATIVE_MODEL_ID = os.getenv("AI_DIPLOMACY_NARRATIVE_MODEL")

# Store the model ID passed from lm_game.py (or other entry point)
# This needs to be set by the main script, e.g., lm_game.py, after parsing args.
# For now, we make it a module-level variable that can be updated.
NARRATIVE_MODEL_ID_FROM_ARGS: str | None = None

__all__ = [
    "NARRATIVE_MODEL_ID_FROM_ARGS",  # Allows external configuration
    "get_narrative_model_id",  # Allows checking which model will be used
    # The main effect is the patch, which happens on import.
]

# ---------------------------------------------------------------------------
# Helper to call the model synchronously (though llm calls can be async)
# ---------------------------------------------------------------------------


def get_narrative_model_id() -> str | None:
    """Determines the model ID to use for narrative generation."""
    if DEFAULT_NARRATIVE_MODEL_ID:  # Env var takes precedence
        return DEFAULT_NARRATIVE_MODEL_ID
    if NARRATIVE_MODEL_ID_FROM_ARGS:  # Then model from script args
        return NARRATIVE_MODEL_ID_FROM_ARGS
    LOGGER.warning(
        "Narrative model ID not configured via env var or script arguments. Narrative generation might fail or use llm default."
    )
    return None  # Or a very basic fallback model if llm has one by default without ID


def _call_llm_for_narrative(statistical_summary: str, phase_key: str) -> str:
    """Return a 2–4 sentence spectator-friendly narrative using the llm library."""

    model_id_to_use = get_narrative_model_id()

    if not model_id_to_use:
        LOGGER.warning(
            "No model ID available for narrative generation. Returning stub."
        )
        return "(Narrative generation disabled – model not configured)."

    try:
        model = llm.get_model(model_id_to_use)
    except llm.UnknownModelError:
        LOGGER.error(
            f"Narrative generation failed: Unknown model '{model_id_to_use}'. Check llm configuration and installed plugins."
        )
        return f"(Narrative generation failed - unknown model: {model_id_to_use})"
    except Exception as e:
        LOGGER.error(
            f"Narrative generation failed: Error loading model '{model_id_to_use}': {e}"
        )
        return f"(Narrative generation failed - model load error: {model_id_to_use})"

    system_prompt = (
        "You are an energetic e-sports commentator narrating a game of Diplomacy. "
        "Turn the provided phase recap into a concise, thrilling story (max 4 sentences). "
        "Highlight pivotal moves, supply-center swings, betrayals, and momentum shifts."
    )
    user_prompt = f"PHASE {phase_key}\n\nSTATISTICAL SUMMARY:\n{statistical_summary}\n\nNow narrate this phase for spectators."

    try:
        # Using prompt() for synchronous call as this is part of a patched synchronous method.
        # If this patch were async, await model.async_prompt() would be used.
        response = model.prompt(user_prompt, system=system_prompt)
        narrative_text = response.text()
        return narrative_text.strip()
    except Exception as exc:  # Broad – we only log and degrade gracefully
        LOGGER.error(
            f"Narrative generation failed with model '{model_id_to_use}': {exc}",
            exc_info=True,
        )
        return f"(Narrative generation failed with model {model_id_to_use})"


# ---------------------------------------------------------------------------
# Patch _generate_phase_summary
# ---------------------------------------------------------------------------

_original_gps: Callable = Game._generate_phase_summary  # type: ignore[attr-defined]


def _patched_generate_phase_summary(self: Game, phase_key, summary_callback=None):  # type: ignore[override]
    # 1) Call original implementation → statistical summary
    statistical = _original_gps(self, phase_key, summary_callback)
    LOGGER.debug(f"[{phase_key}] Original summary returned: {statistical!r}")

    # 2) Persist statistical summary separately
    phase_data = None
    try:
        phase_data = self.get_phase_from_history(str(phase_key))
        if hasattr(phase_data, "statistical_summary"):
            LOGGER.debug(
                f"[{phase_key}] Assigning to phase_data.statistical_summary: {statistical!r}"
            )
            phase_data.statistical_summary = statistical  # type: ignore[attr-defined]
        else:
            LOGGER.warning(
                f"[{phase_key}] phase_data object does not have attribute 'statistical_summary'. Type: {type(phase_data)}"
            )
    except Exception as exc:
        LOGGER.warning(
            "Could not retrieve phase_data or store statistical_summary for %s: %s",
            phase_key,
            exc,
        )

    # 3) Generate narrative summary
    narrative = _call_llm_for_narrative(statistical, phase_key)

    # 4) Save narrative as the canonical summary
    try:
        if phase_data and hasattr(
            phase_data, "summary"
        ):  # Check if phase_data exists and has summary attribute
            phase_data.summary = narrative  # type: ignore[attr-defined]
            # self.phase_summaries[str(phase_key)] = narrative
            LOGGER.debug(f"[{phase_key}] Narrative summary stored successfully.")
        elif phase_data:
            LOGGER.warning(
                f"[{phase_key}] phase_data exists but does not have attribute 'summary'. Cannot store narrative. Type: {type(phase_data)}"
            )
        else:
            LOGGER.warning(
                f"[{phase_key}] Cannot store narrative summary because phase_data is None."
            )
    except Exception as exc:
        LOGGER.warning("Could not store narrative summary for %s: %s", phase_key, exc)

    return narrative


# Monkey-patch
Game._generate_phase_summary = _patched_generate_phase_summary  # type: ignore[assignment]

LOGGER.info(
    "Game._generate_phase_summary patched with narrative generation using the llm library."
)
