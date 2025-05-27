"""
Scripted agent implementation using hand-written heuristics.
Useful for testing and as a baseline for LLM agent performance.
"""

import random
from typing import List, Dict, Any, Optional
from .base import BaseAgent, Order, Message, PhaseState


class ScriptedAgent(BaseAgent):
    """
    Simple scripted agent with basic diplomatic heuristics.
    Makes reasonable but predictable moves without LLM calls.
    """

    def __init__(self, agent_id: str, country: str, personality: str = "neutral"):
        """
        Initialize scripted agent.

        Args:
            agent_id: Unique identifier
            country: Country/power name
            personality: Agent personality ("aggressive", "defensive", "neutral")
        """
        super().__init__(agent_id, country)
        self.personality = personality
        self.relationships = {}  # country -> relationship score (-1 to 1)
        self.priorities = []  # List of strategic priorities

        # Initialize relationships as neutral
        self._initialize_relationships()

    def _initialize_relationships(self):
        """Initialize neutral relationships with all powers."""
        all_countries = [
            "FRANCE",
            "GERMANY",
            "RUSSIA",
            "ENGLAND",
            "ITALY",
            "AUSTRIA",
            "TURKEY",
        ]
        for country in all_countries:
            if country != self.country:
                self.relationships[country] = 0.0  # Neutral

    async def decide_orders(self, phase: PhaseState) -> List[Order]:
        """
        Decide orders based on simple heuristics.

        Args:
            phase: Current game state

        Returns:
            List of orders to submit
        """
        orders = []
        my_units = phase.get_power_units(self.country)

        if not my_units:
            return orders

        # Simple strategy based on phase type and personality
        if phase.phase_type == "MOVEMENT":
            orders = self._decide_movement_orders(phase, my_units)
        elif phase.phase_type == "RETREAT":
            orders = self._decide_retreat_orders(phase, my_units)
        elif phase.phase_type == "ADJUSTMENT":
            orders = self._decide_adjustment_orders(phase)

        return orders

    def _decide_movement_orders(
        self, phase: PhaseState, my_units: List[str]
    ) -> List[Order]:
        """Decide movement orders based on simple heuristics."""
        orders = []

        for unit in my_units:
            # Parse unit info (e.g., "A PAR" -> Army in Paris)
            unit_parts = unit.split()
            if len(unit_parts) >= 2:
                unit_type = unit_parts[0]  # A or F
                location = unit_parts[1]

                # Simple movement strategy
                if self.personality == "aggressive":
                    # Try to move toward enemy supply centers
                    order = self._aggressive_move(unit_type, location, phase)
                elif self.personality == "defensive":
                    # Try to defend own supply centers
                    order = self._defensive_move(unit_type, location, phase)
                else:
                    # Neutral: balanced expansion and defense
                    order = self._neutral_move(unit_type, location, phase)

                if order:
                    orders.append(Order(order))

        return orders

    def _aggressive_move(self, unit_type: str, location: str, phase: PhaseState) -> str:
        """Generate aggressive movement orders."""
        # Simple aggressive strategy: move toward nearest enemy center
        # This is a placeholder - real implementation would need map knowledge
        possible_moves = self._get_possible_moves(unit_type, location)
        if possible_moves:
            # Pick a random valid move (in real implementation, pick strategically)
            target = random.choice(possible_moves)
            return f"{unit_type} {location} - {target}"
        else:
            return f"{unit_type} {location} H"  # Hold if no moves available

    def _defensive_move(self, unit_type: str, location: str, phase: PhaseState) -> str:
        """Generate defensive movement orders."""
        my_centers = phase.get_power_centers(self.country)

        # If this unit is defending a supply center, hold
        if location in my_centers:
            return f"{unit_type} {location} H"

        # Otherwise, try to move to support a supply center
        possible_moves = self._get_possible_moves(unit_type, location)
        for move in possible_moves:
            if move in my_centers:
                return f"{unit_type} {location} - {move}"

        # Default to hold
        return f"{unit_type} {location} H"

    def _neutral_move(self, unit_type: str, location: str, phase: PhaseState) -> str:
        """Generate balanced movement orders."""
        # Mix of aggressive and defensive with some randomness
        if random.random() < 0.7:  # 70% chance to be defensive
            return self._defensive_move(unit_type, location, phase)
        else:
            return self._aggressive_move(unit_type, location, phase)

    def _get_possible_moves(self, unit_type: str, location: str) -> List[str]:
        """
        Get possible moves for a unit.
        This is a simplified placeholder - real implementation needs map data.
        """
        # Placeholder: return some adjacent territories
        # In reality, this would consult the game map
        adjacencies = {
            "PAR": ["BUR", "PIC", "BRE"],
            "MAR": ["SPA", "PIE", "BUR"],
            "BRE": ["PAR", "PIC", "GAS"],
            # Add more as needed...
        }
        return adjacencies.get(location, [])

    def _decide_retreat_orders(
        self, phase: PhaseState, my_units: List[str]
    ) -> List[Order]:
        """Decide retreat orders."""
        orders = []
        # Simple retreat strategy: retreat to the safest adjacent territory
        # This would need more sophisticated logic in a real implementation
        for unit in my_units:
            # For now, just disband (this is overly simplistic)
            orders.append(Order(f"{unit} D"))
        return orders

    def _decide_adjustment_orders(self, phase: PhaseState) -> List[Order]:
        """Decide build/remove orders."""
        orders = []
        my_centers = phase.get_power_centers(self.country)
        my_units = phase.get_power_units(self.country)

        unit_count = len(my_units)
        center_count = len(my_centers)

        if center_count > unit_count:
            # Can build units
            builds_needed = center_count - unit_count
            # Simple build strategy: build armies in home centers
            # This would need map knowledge in real implementation
            for i in range(builds_needed):
                orders.append(Order(f"A {self.country[:3]} B"))  # Build army in capital
        elif unit_count > center_count:
            # Must remove units
            removes_needed = unit_count - center_count
            # Remove the "least important" units (simplified)
            for i in range(min(removes_needed, len(my_units))):
                unit = my_units[i]
                orders.append(Order(f"{unit} D"))  # Disband

        return orders

    async def negotiate(self, phase: PhaseState) -> List[Message]:
        """
        Generate diplomatic messages based on simple patterns.

        Args:
            phase: Current game state

        Returns:
            List of messages to send
        """
        messages = []

        # Simple messaging strategy based on personality
        if random.random() < 0.3:  # 30% chance to send a message each phase
            target_country = self._choose_negotiation_target(phase)
            if target_country:
                message_content = self._generate_message_content(target_country, phase)
                messages.append(
                    Message(
                        recipient=target_country,
                        content=message_content,
                        message_type="private",
                    )
                )

        return messages

    def _choose_negotiation_target(self, phase: PhaseState) -> Optional[str]:
        """Choose which country to send a message to."""
        # Simple heuristic: message the strongest neighbor or a potential ally
        active_powers = [
            p
            for p in phase.powers
            if not phase.is_power_eliminated(p) and p != self.country
        ]

        if not active_powers:
            return None

        # For simplicity, just pick a random active power
        return random.choice(list(active_powers))

    def _generate_message_content(self, target: str, phase: PhaseState) -> str:
        """Generate message content based on personality and situation."""
        templates = {
            "aggressive": [
                f"I suggest we coordinate against {self._get_common_threat(target, phase)}.",
                "Your position looks vulnerable. Perhaps we can help each other.",
                "I propose a temporary alliance for mutual benefit.",
            ],
            "defensive": [
                "I mean no threat to your territories. Can we maintain peace?",
                "Perhaps we can agree to a non-aggression pact?",
                "I'm focused on defense. No need for conflict between us.",
            ],
            "neutral": [
                "How do you view the current situation?",
                "I'm open to discussing our mutual interests.",
                "Perhaps we can find some common ground.",
            ],
        }

        personality_templates = templates.get(self.personality, templates["neutral"])
        assert isinstance(
            personality_templates, list
        )  # Should always be a list due to fallback
        if (
            not personality_templates
        ):  # Should not happen with the current templates dict
            return "Holding my cards close for now."
        return random.choice(personality_templates)

    def _get_common_threat(self, target: str, phase: PhaseState) -> str:
        """Identify a common threat for alliance building."""
        # Find the power with the most supply centers (excluding self and target)
        max_centers = 0
        threat = None

        for power in phase.powers:
            if (
                power != self.country
                and power != target
                and not phase.is_power_eliminated(power)
            ):
                center_count = phase.get_center_count(power)
                if center_count > max_centers:
                    max_centers = center_count
                    threat = power

        return threat or "the leading power"

    async def update_state(
        self, phase: PhaseState, events: List[Dict[str, Any]]
    ) -> None:
        """
        Update internal state based on phase results.

        Args:
            phase: The completed phase
            events: List of events that occurred
        """
        # Update relationship scores based on events
        for event in events:
            event_type = event.get("type")

            if event_type == "attack":
                # Someone attacked us or we attacked someone
                attacker = event.get("attacker")
                target = event.get("target")

                if target == self.country:
                    # We were attacked - decrease relationship
                    if attacker in self.relationships:
                        self.relationships[attacker] -= 0.3
                elif attacker == self.country:
                    # We attacked someone - they probably don't like us now
                    if target in self.relationships:
                        self.relationships[target] -= 0.2

            elif event_type == "support":
                # Support relationships improve trust
                supporter = event.get("supporter")
                supported = event.get("supported")

                if supported == self.country and supporter in self.relationships:
                    self.relationships[supporter] += 0.2
                elif supporter == self.country and supported in self.relationships:
                    self.relationships[supported] += 0.1

        # Clamp relationship values to [-1, 1]
        for country in self.relationships:
            self.relationships[country] = max(
                -1.0, min(1.0, self.relationships[country])
            )

        # Update priorities based on game state
        self._update_priorities(phase)

    def _update_priorities(self, phase: PhaseState):
        """Update strategic priorities based on current game state."""
        self.priorities.clear()

        my_center_count = phase.get_center_count(self.country)

        if my_center_count < 3:
            self.priorities.append("survival")
        elif my_center_count < 8:
            self.priorities.append("expansion")
        else:
            self.priorities.append("consolidation")

        # Add defensive priority if someone is getting too strong
        for power in phase.powers:
            if power != self.country and phase.get_center_count(power) > 10:
                self.priorities.append("contain_leader")
                break
