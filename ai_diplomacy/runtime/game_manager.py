"""
Core game manager that runs phases, validates orders, and emits events.
This module maintains the clean boundary between the core engine and agents.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from ..domain.state import PhaseState

logger = logging.getLogger(__name__)

__all__ = ["GameEvent", "GameManager"]


@dataclass
class GameEvent:
    """Represents an event that occurred during a game phase."""

    event_type: str  # "order_resolved", "attack", "support", "convoy", etc.
    phase: str
    participants: Dict[str, Any]  # Powers involved and their roles
    details: Dict[str, Any]  # Additional event-specific data


class GameManager:
    """
    Core game manager that orchestrates phases and validates actions.

    This class acts as the bridge between agents and the game engine,
    maintaining clean boundaries and providing a stable API.
    """

    def __init__(self, game):
        """
        Initialize the game manager.

        Args:
            game: The diplomacy.Game instance
        """
        self.game = game
        self.events_log: List[GameEvent] = []
        logger.info("GameManager initialized")

    def get_current_phase_state(self) -> PhaseState:
        """
        Get the current game state as an immutable PhaseState.

        Returns:
            PhaseState snapshot of current game state
        """
        return PhaseState.from_game(self.game)

    def validate_orders(self, country: str, orders: List[str]) -> Tuple[List[str], List[str]]:
        """
        Validate orders for a country and return valid/invalid orders.

        Args:
            country: The country submitting orders
            orders: List of order strings

        Returns:
            Tuple of (valid_orders, invalid_orders)
        """
        valid_orders = []
        invalid_orders = []

        try:
            # Get possible orders for this power
            possible_orders = self.game.get_all_possible_orders()
            power_possible_orders = possible_orders.get(country, [])

            for order in orders:
                order_str = str(order).strip()
                if order_str in power_possible_orders:
                    valid_orders.append(order_str)
                else:
                    invalid_orders.append(order_str)
                    logger.warning(f"Invalid order for {country}: {order_str}")

        except Exception as e:
            logger.error(f"Error validating orders for {country}: {e}", exc_info=True)
            # In case of error, treat all orders as invalid
            invalid_orders = [str(order) for order in orders]

        logger.info(
            f"Validated orders for {country}: {len(valid_orders)} valid, {len(invalid_orders)} invalid"
        )
        return valid_orders, invalid_orders

    def submit_orders(self, country: str, orders: List[str]) -> bool:
        """
        Submit validated orders for a country.

        Args:
            country: The country submitting orders
            orders: List of validated order strings

        Returns:
            True if orders were successfully submitted
        """
        try:
            # Clear existing orders for this power
            self.game.clear_orders(country)

            # Submit new orders
            for order in orders:
                self.game.set_orders(country, [order])

            logger.info(f"Submitted {len(orders)} orders for {country}")
            return True

        except Exception as e:
            logger.error(f"Error submitting orders for {country}: {e}", exc_info=True)
            return False

    def process_phase(self) -> List[GameEvent]:
        """
        Process the current phase and return events that occurred.

        Returns:
            List of events that occurred during phase processing
        """
        phase_events = []
        current_phase = self.game.get_current_phase()

        try:
            logger.info(f"Processing phase {current_phase}")

            # Store pre-phase state for event generation
            pre_phase_state = self.get_current_phase_state()

            # Process the phase
            self.game.process()

            # Generate events based on what happened
            phase_events = self._generate_phase_events(pre_phase_state, current_phase)

            # Add events to log
            self.events_log.extend(phase_events)

            logger.info(f"Phase {current_phase} processed, generated {len(phase_events)} events")

        except Exception as e:
            logger.error(f"Error processing phase {current_phase}: {e}", exc_info=True)
            # Create an error event
            error_event = GameEvent(
                event_type="phase_error",
                phase=current_phase,
                participants={},
                details={"error": str(e)},
            )
            phase_events.append(error_event)

        return phase_events

    def _generate_phase_events(self, pre_phase_state: PhaseState, phase: str) -> List[GameEvent]:
        """
        Generate events by comparing pre and post phase states.

        Args:
            pre_phase_state: State before phase processing
            phase: Phase that was processed

        Returns:
            List of events that occurred
        """
        events = []

        try:
            # Get post-phase state
            post_phase_state = self.get_current_phase_state()

            # Compare unit positions to detect moves, attacks, supports, etc.
            events.extend(self._detect_unit_movements(pre_phase_state, post_phase_state, phase))

            # Compare supply center ownership
            events.extend(self._detect_center_changes(pre_phase_state, post_phase_state, phase))

            # Detect eliminations
            events.extend(self._detect_eliminations(pre_phase_state, post_phase_state, phase))

        except Exception as e:
            logger.error(f"Error generating phase events: {e}", exc_info=True)

        return events

    def _detect_unit_movements(self, pre: PhaseState, post: PhaseState, phase: str) -> List[GameEvent]:
        """Detect unit movements and related events."""
        events = []

        # This is a simplified implementation
        # Real implementation would parse the orders and results more carefully

        for country in pre.powers:
            pre_units = set(pre.get_power_units(country))
            post_units = set(post.get_power_units(country))

            # Detect lost units (could be retreats, disbands, or attacks)
            lost_units = pre_units - post_units
            for unit in lost_units:
                events.append(
                    GameEvent(
                        event_type="unit_lost",
                        phase=phase,
                        participants={"country": country, "unit": unit},
                        details={"unit_type": unit.split()[0] if unit else "unknown"},
                    )
                )

            # Detect new units (builds)
            new_units = post_units - pre_units
            for unit in new_units:
                events.append(
                    GameEvent(
                        event_type="unit_built",
                        phase=phase,
                        participants={"country": country, "unit": unit},
                        details={"unit_type": unit.split()[0] if unit else "unknown"},
                    )
                )

        return events

    def _detect_center_changes(self, pre: PhaseState, post: PhaseState, phase: str) -> List[GameEvent]:
        """Detect supply center ownership changes."""
        events = []

        for country in pre.powers:
            pre_centers = set(pre.get_power_centers(country))
            post_centers = set(post.get_power_centers(country))

            # Lost centers
            lost_centers = pre_centers - post_centers
            for center in lost_centers:
                # Try to find who took it
                new_owner = None
                for other_country in post.powers:
                    if center in post.get_power_centers(other_country):
                        new_owner = other_country
                        break

                events.append(
                    GameEvent(
                        event_type="center_lost",
                        phase=phase,
                        participants={
                            "country": country,
                            "new_owner": new_owner,
                            "center": center,
                        },
                        details={},
                    )
                )

            # Gained centers
            gained_centers = post_centers - pre_centers
            for center in gained_centers:
                events.append(
                    GameEvent(
                        event_type="center_gained",
                        phase=phase,
                        participants={"country": country, "center": center},
                        details={},
                    )
                )
        return events

    def _detect_eliminations(self, pre: PhaseState, post: PhaseState, phase: str) -> List[GameEvent]:
        """Detect which powers were eliminated."""
        events = []
        pre_powers = pre.powers - pre.eliminated_powers
        post_powers = post.powers - post.eliminated_powers
        eliminated_powers = pre_powers - post_powers

        for power in eliminated_powers:
            events.append(
                GameEvent(
                    event_type="power_eliminated",
                    phase=phase,
                    participants={"country": power},
                    details={},
                )
            )
        return events

    def is_game_over(self) -> bool:
        """Check if the game has ended."""
        return self.game.is_game_done

    def get_winner(self) -> Optional[str]:
        """
        Get the winner of the game, if it has ended.

        Returns:
            The name of the winning country, or None if no winner yet.
        """
        if not self.is_game_over():
            return None

        # Determine winner based on supply centers
        state = self.get_current_phase_state()
        max_centers = 0
        winner = None

        for power in state.powers:
            center_count = state.get_center_count(power)
            if center_count > max_centers:
                max_centers = center_count
                winner = power
            elif center_count == max_centers:
                winner = None  # Draw

        return winner

    def get_events_for_country(
        self, country: str, phase: Optional[str] = None
    ) -> List[GameEvent]:
        """
        Get all events relevant to a specific country.

        Args:
            country: The country to get events for
            phase: Optional phase to filter by

        Returns:
            List of relevant game events
        """
        relevant_events = []
        for event in self.events_log:
            if phase and event.phase != phase:
                continue
            if country in event.participants.values():
                relevant_events.append(event)
        return relevant_events

    def _is_order_valid(self, country: str, order_text: str) -> bool:
        """
        Check if a single order is valid for a country.
        (Internal helper)
        """
        try:
            possible_orders = self.game.get_all_possible_orders().get(country, [])
            return order_text in possible_orders
        except Exception:
            return False 