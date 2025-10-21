"""
Mixin class providing a simple hold order generation behaviour.
"""

from typing import List

# Adjusted import path assuming core is one level up from agents directory
from ...domain.state import PhaseState
from ...domain.order import Order

__all__ = ["HoldBehaviourMixin"]


class HoldBehaviourMixin:
    """
    Mixin class providing a simple hold order generation behaviour.
    Assumes the class using this mixin has a 'country' attribute (str).
    """

    def get_hold_orders(self, phase: PhaseState) -> List[Order]:
        """
        Generates hold orders for all units belonging to the agent.
        The lookup order is:
        1. `PhaseState.get_power_units` (preferred – new API)
        2. `PhaseState.get_power_state(...).units` (legacy API – remove once deprecated)
        3. `phase.game.get_units` (when a raw diplomacy.Game is hanging off the state)
        """
        units: List[str] = []

        # Ensure we have a valid country attribute
        if not isinstance(getattr(self, "country", None), str):
            print("Warning: HoldBehaviourMixin used without a valid `country` attribute.")
            return []

        country_upper: str = self.country.upper()

        # --- Preferred path -------------------------------------------------
        if hasattr(phase, "get_power_units"):
            units = phase.get_power_units(country_upper)

        # --- Legacy fallback ----------------------------------------------
        elif hasattr(phase, "get_power_state"):
            try:
                power_state = phase.get_power_state(country_upper)
                units = getattr(power_state, "units", [])  # type: ignore[arg-type]
            except Exception:
                units = []

        # --- Raw game fallback --------------------------------------------
        if not units and hasattr(phase, "game") and hasattr(phase.game, "get_units"):
            units = phase.game.get_units(country_upper)  # type: ignore[assignment]

        # -------------------------------------------------------------------
        orders: List[Order] = [Order(f"{str(u)} HLD") for u in units]
        return orders
