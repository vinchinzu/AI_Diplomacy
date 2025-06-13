from dataclasses import dataclass, field
from typing import Dict, List

@dataclass(frozen=True)
class BoardState:
    """Represents the state of the board."""
    units: Dict[str, List[str]] = field(default_factory=dict)
    supply_centers: Dict[str, List[str]] = field(default_factory=dict)

    def get_units(self, power: str) -> List[str]:
        """Returns the units for a given power."""
        return self.units.get(power, [])
