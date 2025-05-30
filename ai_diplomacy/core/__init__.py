"""
Core components for managing the Diplomacy game state and engine.

This package provides fundamental classes for representing the game state (PhaseState)
and managing the game progression (GameManager - though this might be more of an orchestrator).
It is designed to be independent of specific AI or LLM implementations.
"""

from .state import PhaseState
# Assuming GameManager might be defined in manager.py, or it's an older concept.
# If manager.py contains a relevant public class, it should be imported and added.
# For now, only PhaseState is confirmed from existing files.

__all__ = [
    "PhaseState",
    "GameManager",
    "GameEvent",
]
