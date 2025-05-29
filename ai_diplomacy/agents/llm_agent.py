"""
LLM-based agent implementation.
Extracts all LLM-specific logic from the original DiplomacyAgent while implementing the clean BaseAgent interface.
"""

import logging
from typing import List, Dict, Optional, Any, Callable, Awaitable

from .base import BaseAgent, Order, Message, PhaseState
from .agent_state import DiplomacyAgentState
from .llm_prompt_strategy import LLMPromptStrategy
from ..services.llm_coordinator import LLMCoordinator
from ..services.config import AgentConfig, resolve_context_provider
from ..services.context_provider import ContextProviderFactory, ContextData
from ai_diplomacy import llm_utils # Changed from relative to absolute package import

logger = logging.getLogger(__name__)


class LLMAgent(BaseAgent):
    """
    LLM-based diplomacy agent that implements the BaseAgent interface.

    This agent uses Large Language Models to make decisions, maintain relationships,
    and generate diplomatic communications. It receives immutable PhaseState objects
    and returns orders/messages without direct game engine access.
    """

    def __init__(
        self,
        agent_id: str,
        country: str,
        config: AgentConfig,
        game_id: str = "unknown_game",
        llm_coordinator: Optional[LLMCoordinator] = None,
        context_provider_factory: Optional[ContextProviderFactory] = None,
        prompt_loader: Optional[Callable[[str], Optional[str]]] = None,
        llm_caller_override: Optional[Callable[..., Awaitable[str]]] = None,
    ):
        """
        Initialize the LLM agent.

        Args:
            agent_id: Unique identifier for this agent instance
            country: The country/power this agent represents
            config: Agent configuration containing model_id and other settings
            game_id: Game identifier for tracking
            llm_coordinator: LLM coordinator instance (will create if None)
            context_provider_factory: Context provider factory (will create if None)
            prompt_loader: Optional function to load prompts by filename
            llm_caller_override: Optional override for the LLM call logic.
        """
        super().__init__(agent_id, country)
        self.config = config
        self.power_name = country  # Added for direct access
        self.model_id = config.model_id  # Added for direct access
        self.game_id = game_id
        self.llm_coordinator = llm_coordinator or LLMCoordinator()

        # Context provider setup
        self.context_factory = context_provider_factory or ContextProviderFactory()
        self.resolved_context_provider_type = resolve_context_provider(config)
        self.context_provider = self.context_factory.get_provider(
            self.resolved_context_provider_type
        )

        # Update resolved type to reflect actual provider used (handles fallbacks)
        self.resolved_context_provider_type = self.context_provider.get_provider_type()

        # Agent state using DiplomacyAgentState and LLMPromptStrategy
        self.agent_state = DiplomacyAgentState(country=country)
        self.prompt_strategy = LLMPromptStrategy()
        self.prompt_loader = prompt_loader
        self.llm_caller_override = llm_caller_override # Store the override

        # Load system prompt
        self.system_prompt = self._load_system_prompt()

        logger.info(
            f"Initialized LLMAgent for {self.country} with model {self.config.model_id}, context provider: {self.resolved_context_provider_type}"
        )
        self.agent_state.add_journal_entry(
            f"Agent initialized with model {self.config.model_id}, context provider: {self.resolved_context_provider_type}"
        )

    def _load_system_prompt(self) -> Optional[str]:
        """Load power-specific or default system prompt."""
        power_prompt_filename = f"{self.country.lower()}_system_prompt.txt"
        default_prompt_filename = "system_prompt.txt"
        system_prompt: Optional[str] = None

        if self.prompt_loader:
            system_prompt = self.prompt_loader(power_prompt_filename)
            if not system_prompt:
                logger.warning(
                    f"Power-specific prompt '{power_prompt_filename}' not found via prompt_loader. Loading default."
                )
                system_prompt = self.prompt_loader(default_prompt_filename)
            else:
                logger.info(f"Loaded power-specific system prompt for {self.country} via prompt_loader.")
        else:
            system_prompt = llm_utils.load_prompt_file(power_prompt_filename)
            if not system_prompt:
                logger.warning(
                    f"Power-specific prompt '{power_prompt_filename}' not found. Loading default."
                )
                system_prompt = llm_utils.load_prompt_file(default_prompt_filename)
            else:
                logger.info(f"Loaded power-specific system prompt for {self.country}.")

        if not system_prompt:
            logger.error(f"Could not load system prompt for {self.country}!")

        return system_prompt

    async def decide_orders(self, phase: PhaseState) -> List[Order]:
        """
        Decide what orders to submit for the current phase.

        Args:
            phase: Immutable snapshot of current game state

        Returns:
            List of orders to submit
        """
        logger.info(f"[{self.country}] Deciding orders for phase {phase.phase_name}")

        # Check if we have units to command
        my_units = phase.get_power_units(self.country)
        if not my_units:
            logger.info(f"[{self.country}] No units to command")
            return []

        # Build context using context provider
        try:
            # Prepare context data (simplified for now - in real implementation would include more details)
            context_data = ContextData(
                phase_state=phase,
                possible_orders={"MOCK": ["Hold"]},  # TODO: Get real possible orders
                game_history=None,
                recent_messages=None,
                strategic_analysis=None,
            )

            # Get context from provider
            context_result = await self.context_provider.provide_context(
                agent_id=self.agent_id,
                country=self.country,
                context_data=context_data,
                agent_config=self.config,
            )

            # Build prompt using prompt strategy
            prompt = self.prompt_strategy.build_order_prompt(
                country=self.country,
                goals=self.agent_state.goals,
                relationships=self.agent_state.relationships,
                formatted_diary=self.agent_state.format_private_diary_for_prompt(),
                context_text=context_result.get("context_text") or "", # Ensure empty string if None
                tools_available=context_result.get("tools_available", False),
            )

            # Call LLM
            result = await self.llm_coordinator.call_json(
                prompt=prompt,
                model_id=self.config.model_id,
                agent_id=self.agent_id,
                game_id=self.game_id,
                phase=phase.phase_name,
                system_prompt=self.system_prompt,
                expected_fields=["orders"],
                tools=(
                    context_result.get("tools", [])
                    if context_result.get("tools_available")
                    else None
                ),
                llm_caller_override=self.llm_caller_override,
            )

            # Extract orders from response
            orders = self._extract_orders_from_response(result, my_units)

            logger.info(
                f"[{self.country}] Generated {len(orders)} orders using {context_result.get('provider_type', 'unknown')} context"
            )
            return orders

        except Exception as e:
            logger.error(f"[{self.country}] Error deciding orders: {e}", exc_info=True)
            # Fallback: hold all units
            return [Order(f"{unit} H") for unit in my_units]

    def _extract_orders_from_response(
        self, response: Dict[str, Any], my_units: List[str]
    ) -> List[Order]:
        """Extract and validate orders from LLM response."""
        orders = []

        if "orders" not in response:
            logger.warning(f"[{self.country}] No 'orders' field in LLM response")
            return [Order(f"{unit} H") for unit in my_units]  # Default to hold

        order_strings = response["orders"]
        if not isinstance(order_strings, list):
            logger.warning(f"[{self.country}] Orders field is not a list")
            return [Order(f"{unit} H") for unit in my_units]

        for order_str in order_strings:
            if isinstance(order_str, str) and order_str.strip():
                orders.append(Order(order_str.strip()))

        # If no valid orders, default to holding
        if not orders:
            orders = [Order(f"{unit} H") for unit in my_units]

        return orders

    async def negotiate(self, phase: PhaseState) -> List[Message]:
        """
        Generate diplomatic messages to send to other powers.

        Args:
            phase: Immutable snapshot of current game state

        Returns:
            List of messages to send
        """
        logger.info(
            f"[{self.country}] Generating messages for phase {phase.phase_name}"
        )

        try:
            # Prepare context data for negotiations
            context_data = ContextData(
                phase_state=phase,
                possible_orders={"MOCK": ["Hold"]},  # TODO: Get real possible orders
                game_history=None,
                recent_messages=None,
                strategic_analysis=None,
            )

            # Get context from provider
            context_result = await self.context_provider.provide_context(
                agent_id=self.agent_id,
                country=self.country,
                context_data=context_data,
                agent_config=self.config,
            )

            # Build prompt using prompt strategy
            active_powers_list = [
                p for p in phase.powers if not phase.is_power_eliminated(p) and p != self.country
            ]
            prompt = self.prompt_strategy.build_negotiation_prompt(
                country=self.country,
                active_powers=active_powers_list,
                goals=self.agent_state.goals,
                relationships=self.agent_state.relationships,
                formatted_diary=self.agent_state.format_private_diary_for_prompt(),
                context_text=context_result.get("context_text") or "", # Ensure empty string if None
                tools_available=context_result.get("tools_available", False),
            )

            # Call LLM
            result = await self.llm_coordinator.call_json(
                prompt=prompt,
                model_id=self.config.model_id,
                agent_id=self.agent_id,
                game_id=self.game_id,
                phase=phase.phase_name,
                system_prompt=self.system_prompt,
                expected_fields=["messages"],
                tools=(
                    context_result.get("tools", [])
                    if context_result.get("tools_available")
                    else None
                ),
                llm_caller_override=self.llm_caller_override,
            )

            # Extract messages from response
            messages = self._extract_messages_from_response(result, phase)

            logger.info(
                f"[{self.country}] Generated {len(messages)} messages using {context_result.get('provider_type', 'unknown')} context"
            )
            return messages

        except Exception as e:
            logger.error(
                f"[{self.country}] Error generating messages: {e}", exc_info=True
            )
            return []

    def _extract_messages_from_response(
        self, response: Dict[str, Any], phase: PhaseState
    ) -> List[Message]:
        """Extract and validate messages from LLM response."""
        messages = []

        if "messages" not in response:
            return messages

        message_dicts = response["messages"]
        if not isinstance(message_dicts, list):
            return messages

        for msg_dict in message_dicts:
            if not isinstance(msg_dict, dict):
                continue

            recipient = msg_dict.get("recipient", "").upper()
            content = msg_dict.get("content", "")
            message_type = msg_dict.get("message_type", "private")

            if content and recipient:
                # Validate recipient
                if recipient in phase.powers or recipient == "GLOBAL":
                    messages.append(Message(recipient, content, message_type))
                else:
                    logger.warning(f"[{self.country}] Invalid recipient: {recipient}")

        return messages

    async def update_state(
        self, phase: PhaseState, events: List[Dict[str, Any]]
    ) -> None:
        """
        Update internal agent state based on phase results and events.

        Args:
            phase: The phase that just completed
            events: List of events that occurred
        """
        logger.info(f"[{self.country}] Updating state after phase {phase.phase_name}")

        # Generate a diary entry about the phase results
        await self._generate_phase_diary_entry(phase, events)

        # Update relationships based on events
        self.agent_state._update_relationships_from_events(self.country, events)

        # Optionally update goals based on game state analysis
        await self._analyze_and_update_goals(phase)

    async def _generate_phase_diary_entry(
        self, phase: PhaseState, events: List[Dict[str, Any]]
    ):
        """Generate a diary entry reflecting on the phase results."""
        try:
            prompt = self.prompt_strategy.build_diary_generation_prompt(
                country=self.country,
                phase_name=phase.phase_name,
                power_units=phase.get_power_units(self.country),
                power_centers=phase.get_power_centers(self.country),
                is_game_over=phase.is_game_over,
                events=events,
                goals=self.agent_state.goals,
                relationships=self.agent_state.relationships,
            )

            result = await self.llm_coordinator.call_json(
                prompt=prompt,
                model_id=self.config.model_id,
                agent_id=self.agent_id,
                game_id=self.game_id,
                phase=phase.phase_name,
                system_prompt=self.system_prompt,
                expected_fields=["diary_entry"],
                llm_caller_override=self.llm_caller_override,
            )

            diary_text = result.get(
                "diary_entry", f"Phase {phase.phase_name} completed."
            )
            self.agent_state.add_diary_entry(diary_text, phase.phase_name)

        except Exception as e:
            logger.error(
                f"[{self.country}] Error generating diary entry: {e}", exc_info=True
            )
            self.agent_state.add_diary_entry(
                f"Phase {phase.phase_name} completed (diary generation failed).",
                phase.phase_name,
            )

    async def _analyze_and_update_goals(self, phase: PhaseState):
        """Analyze current situation and potentially update goals."""
        # For now, this uses rule-based logic.
        # If LLM-driven, would use:
        # prompt = self.prompt_strategy.build_goal_analysis_prompt(...)
        # result = await self.llm_coordinator.call_json(...)
        # self.agent_state.goals = result.get("updated_goals", self.agent_state.goals)
        # self.agent_state.add_journal_entry(result.get("reasoning", "Goals updated by LLM."))
        try:
            my_center_count = phase.get_center_count(self.country)
            new_goals = []

            if my_center_count < 3:
                new_goals.append("Survive and avoid elimination")
            elif my_center_count < 8:
                new_goals.append("Expand territory and gain supply centers")
            else:
                new_goals.append("Consolidate position and prepare for victory")

            active_powers = [p for p in phase.powers if not phase.is_power_eliminated(p)]
            if active_powers: # Ensure there are active powers to check
                max_centers = max(phase.get_center_count(p) for p in active_powers)
                if max_centers > 10 and phase.get_center_count(self.country) != max_centers:
                    new_goals.append("Form coalition against the leader")
            
            if new_goals != self.agent_state.goals:
                old_goals = self.agent_state.goals.copy()
                self.agent_state.goals = new_goals
                self.agent_state.add_journal_entry(f"Goals updated from {old_goals} to {new_goals}")

        except Exception as e:
            logger.error(f"[{self.country}] Error analyzing goals: {e}", exc_info=True)

    def get_agent_info(self) -> Dict[str, Any]:
        """Return information about this agent."""
        return {
            "agent_id": self.agent_id,
            "country": self.country,
            "type": "LLMAgent",
            "model_id": self.config.model_id,
            "goals": self.agent_state.goals,
            "relationships": self.agent_state.relationships,
            "diary_entries": len(self.agent_state.private_diary),
            "journal_entries": len(self.agent_state.private_journal),
        }
