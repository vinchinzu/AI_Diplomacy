from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .board import BoardState
    from .game_history import PhaseHistory


@dataclass(frozen=True)
class PhaseKey:
    """A unique key for a phase in a game."""

    state: dict[str, Any]
    scs: dict[str, int]
    year: int
    season: str
    name: str  # alias for 'phase'


@dataclass(frozen=True)
class PhaseState:
    """The full state of a game at a particular phase."""

    key: PhaseKey
    board: "BoardState"
    history: list["PhaseHistory"]  # optional

    # --- compatibility shims ---
    @property
    def state(self) -> dict[str, Any]:
        """The state of the board."""
        return self.key.state

    @property
    def scs(self) -> dict[str, int]:
        """The supply centers."""
        return self.key.scs

    @property
    def name(self) -> str:
        """The name of the phase."""
        return self.key.name
