"""
Immutable game state dataclasses for agent communication.
These provide a stable, frozen snapshot of game state without coupling to the full Game object.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, FrozenSet, Any

__all__ = ["PhaseState"]


@dataclass(frozen=True)
class PhaseState:
    """
    Immutable snapshot of game state for a specific phase.
    Agents receive this instead of direct access to the Game object.
    """

    phase_name: str
    year: int
    season: str  # "SPRING", "FALL", "WINTER"
    phase_type: str  # "MOVEMENT", "RETREAT", "ADJUSTMENT"

    # Power state
    powers: FrozenSet[str] = field(default_factory=frozenset)
    eliminated_powers: FrozenSet[str] = field(default_factory=frozenset)

    # Board state
    units: Dict[str, List[str]] = field(default_factory=dict)  # power -> list of unit strings
    supply_centers: Dict[str, List[str]] = field(default_factory=dict)  # power -> list of center names

    # Possible orders
    possible_orders: Dict[str, List[str]] = field(default_factory=dict)  # power -> list of order strings

    # Game progress
    is_game_over: bool = False
    winner: Optional[str] = None

    # Messages (read-only view) - using Any to avoid diplomacy import
    recent_messages: List[Any] = field(default_factory=list)

    @classmethod
    def from_game(cls, game, recent_messages: Optional[List[Any]] = None) -> "PhaseState":
        """Create a PhaseState from a diplomacy.Game object."""
        try:
            # Parse phase information
            current_phase = game.get_current_phase()
            year = int(current_phase[1:5]) if len(current_phase) >= 5 else 1901
            season = current_phase[0] if current_phase else "S"
            phase_type = current_phase[5:] if len(current_phase) > 5 else "M"

            # Convert season codes to readable names
            season_map = {"S": "SPRING", "F": "FALL", "W": "WINTER"}
            season_name = season_map.get(season, "SPRING")

            # Convert phase type codes to readable names
            type_map = {"M": "MOVEMENT", "R": "RETREAT", "A": "ADJUSTMENT"}
            phase_type_name = type_map.get(phase_type, "MOVEMENT")

            # Extract power information
            all_powers = frozenset(game.powers.keys())
            eliminated = frozenset(p.name for p in game.powers.values() if p.is_eliminated())

            # Extract units and centers
            units_dict = {}
            centers_dict = {}
            possible_orders_dict = {}

            # Check if game object has get_all_possible_orders method
            if hasattr(game, "get_all_possible_orders"):
                # The structure is Dict[power_name, List[order_str]]
                possible_orders_dict = game.get_all_possible_orders()

            for power_name, power_obj in game.powers.items():
                units_dict[power_name] = [str(unit) for unit in power_obj.units]
                centers_dict[power_name] = [str(center) for center in power_obj.centers]

            # Game status
            game_over = game.is_game_done
            winner_power = None
            if game_over:
                # Find winner (power with most supply centers)
                max_centers = max(len(centers) for centers in centers_dict.values()) if centers_dict else 0
                for power, centers in centers_dict.items():
                    if len(centers) == max_centers:
                        winner_power = power
                        break

            return cls(
                phase_name=current_phase,
                year=year,
                season=season_name,
                phase_type=phase_type_name,
                powers=all_powers,
                eliminated_powers=eliminated,
                units=units_dict,
                supply_centers=centers_dict,
                possible_orders=possible_orders_dict,
                is_game_over=game_over,
                winner=winner_power,
                recent_messages=recent_messages or [],
            )

        except Exception:
            # Fallback to minimal state if game object access fails
            return cls(
                phase_name="UNKNOWN",
                year=1901,
                season="SPRING",
                phase_type="MOVEMENT",
                powers=frozenset(),
                eliminated_powers=frozenset(),
                units={},
                supply_centers={},
                possible_orders={},
                is_game_over=False,
                winner=None,
                recent_messages=recent_messages or [],
            )

    def get_power_units(self, power: str) -> List[str]:
        """Get units for a specific power."""
        return self.units.get(power, [])

    def get_power_centers(self, power: str) -> List[str]:
        """Get supply centers for a specific power."""
        return self.supply_centers.get(power, [])

    def get_all_possible_orders(self) -> Dict[str, List[str]]:
        """Gets all possible orders for all powers."""
        return self.possible_orders

    def is_power_eliminated(self, power: str) -> bool:
        """Check if a power is eliminated."""
        return power in self.eliminated_powers

    def get_center_count(self, power: str) -> int:
        """Get number of supply centers for a power."""
        return len(self.get_power_centers(power))
