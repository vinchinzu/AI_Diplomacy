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
from .. import constants # Import constants

logger = logging.getLogger(__name__)

__all__ = ["LLMAgent"]

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
        game_id: str = constants.DEFAULT_GAME_ID,
        llm_coordinator: Optional[LLMCoordinator] = None,
        context_provider_factory: Optional[ContextProviderFactory] = None,
        prompt_loader: Optional[Callable[[str], Optional[str]]] = None,
        llm_caller_override: Optional[Callable[..., Awaitable[Dict[str, Any]]]] = None,
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
        default_prompt_filename = constants.DEFAULT_SYSTEM_PROMPT_FILENAME
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
            tools_definition = context_result.get("tools") if context_result.get("tools_available") else None

            if self.llm_caller_override:
                result = await self.llm_caller_override(
                    prompt=prompt,
                    model_id=self.model_id,
                    agent_id=self.agent_id,
                    game_id=self.game_id,
                    phase=phase.phase_name,
                    system_prompt=self.system_prompt,
                    expected_fields=[constants.LLM_RESPONSE_KEY_ORDERS],
                    tools=tools_definition if tools_definition else None,
                    verbose_llm_debug=self.config.verbose_llm_debug
                )
            else:
                result = await self.llm_coordinator.call_json(
                    prompt=prompt,
                    model_id=self.model_id,
                    agent_id=self.agent_id,
                    game_id=self.game_id,
                    phase=phase.phase_name,
                    system_prompt=self.system_prompt,
                    expected_fields=[constants.LLM_RESPONSE_KEY_ORDERS],
                    tools=tools_definition if tools_definition else None,
                    verbose_llm_debug=self.config.verbose_llm_debug
                )

            orders_data = result.get(constants.LLM_RESPONSE_KEY_ORDERS) if result else None
            if orders_data:
                orders = self._extract_orders_from_response(orders_data, my_units)
                logger.info(
                    f"[{self.country}] Generated {len(orders)} orders using {context_result.get('provider_type', 'unknown')} context"
                )
                return orders
            else:
                # Strict mode: If orders_data is not usable, raise an error instead of defaulting.
                error_msg = f"[{self.country}] No valid '{constants.LLM_RESPONSE_KEY_ORDERS}' field in LLM response or response was None. Response: {result}"
                logger.error(error_msg)
                raise ValueError(error_msg) # This will propagate up

        except ValueError as ve: # Catch our specific ValueError to re-raise
            logger.error(f"[{self.country}] ValueError deciding orders: {ve}")
            raise
        except Exception as e:
            # General errors still log and could potentially raise or return empty list depending on broader strategy
            error_msg = f"[{self.country}] Unexpected error deciding orders: {e}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e # Propagate as a new error type to distinguish from direct LLM failure

    def _extract_orders_from_response(
        self, response_orders_data: Any, my_units: List[str]
    ) -> List[Order]:
        """Extract and validate orders from LLM response. Raises ValueError on failure."""
        orders = []
        # Argument renamed from 'response' to 'response_orders_data' to reflect it's the 'orders' part of the response

        if not isinstance(response_orders_data, list):
            error_msg = f"[{self.country}] Orders field from LLM is not a list. Got: {type(response_orders_data)}"
            logger.warning(error_msg)
            raise ValueError(error_msg)

        for item in response_orders_data:
            if isinstance(item, str) and item.strip():
                orders.append(Order(item.strip()))
            elif isinstance(item, dict):
                unit = item.get("unit")
                action = item.get("action")
                if isinstance(unit, str) and isinstance(action, str) and unit.strip() and action.strip():
                    orders.append(Order(f"{unit.strip()} {action.strip()}"))
                else:
                    logger.warning(f"[{self.country}] Invalid order dictionary item: {item}")
            else:
                logger.warning(f"[{self.country}] Invalid item in orders list: {item}")

        if not orders and my_units: # If we have units but extracted no valid orders
            error_msg = f"[{self.country}] No valid orders extracted from LLM response, though units exist. LLM provided: {response_orders_data}"
            logger.warning(error_msg)
            raise ValueError(error_msg)
        elif not my_units and orders: # If we have no units but LLM provided orders
            logger.warning(f"[{self.country}] LLM provided orders but no units to command. Orders: {orders}")
            # This case might be acceptable, return empty list as no orders can be actioned.
            return []
        
        # Here, we only return if orders were successfully extracted for existing units, or if no units/no orders.
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
            tools_definition = context_result.get("tools") if context_result.get("tools_available") else None

            if self.llm_caller_override:
                result = await self.llm_caller_override(
                    prompt=prompt,
                    model_id=self.model_id,
                    agent_id=self.agent_id,
                    game_id=self.game_id,
                    phase=phase.phase_name,
                    system_prompt=self.system_prompt,
                    expected_fields=[constants.LLM_RESPONSE_KEY_MESSAGES],
                    tools=tools_definition if tools_definition else None,
                    verbose_llm_debug=self.config.verbose_llm_debug
                )
            else:
                result = await self.llm_coordinator.call_json(
                    prompt=prompt,
                    model_id=self.model_id,
                    agent_id=self.agent_id,
                    game_id=self.game_id,
                    phase=phase.phase_name,
                    system_prompt=self.system_prompt,
                    expected_fields=[constants.LLM_RESPONSE_KEY_MESSAGES],
                    tools=tools_definition if tools_definition else None,
                    verbose_llm_debug=self.config.verbose_llm_debug
                )

            messages_data = result.get(constants.LLM_RESPONSE_KEY_MESSAGES) if result else None
            if messages_data:
                messages = self._extract_messages_from_response(messages_data, phase)
                logger.info(
                    f"[{self.country}] Generated {len(messages)} messages using {context_result.get('provider_type', 'unknown')} context"
                )
                return messages
            else:
                logger.warning(f"[{self.country}] No '{constants.LLM_RESPONSE_KEY_MESSAGES}' field in LLM response or response is None")
                return []

        except Exception as e:
            logger.error(
                f"[{self.country}] Error generating messages: {e}", exc_info=True
            )
            return []

    def _extract_messages_from_response(
        self, response: Optional[Dict[str, Any]], phase: PhaseState
    ) -> List[Message]:
        """Extract and validate messages from LLM response."""
        messages = []
        if response is None or constants.LLM_RESPONSE_KEY_MESSAGES not in response:
            logger.warning(
                f"[{self.country}] No '{constants.LLM_RESPONSE_KEY_MESSAGES}' field in LLM response or response is None"
            )
            return messages

        message_data = response[constants.LLM_RESPONSE_KEY_MESSAGES]
        if not isinstance(message_data, list):
            logger.warning(f"[{self.country}] Messages field is not a list")
            return messages

        valid_recipients = phase.powers # Get all powers in the game as potential recipients

        for msg_item in message_data:
            if not isinstance(msg_item, dict):
                logger.warning(f"[{self.country}] Invalid message item: {msg_item}")
                continue

            recipient = msg_item.get(constants.LLM_MESSAGE_KEY_RECIPIENT)
            content = msg_item.get(constants.LLM_MESSAGE_KEY_CONTENT)
            message_type_str = msg_item.get(constants.LLM_MESSAGE_KEY_TYPE)

            if not isinstance(recipient, str) or not recipient.strip():
                logger.warning(f"[{self.country}] Invalid or missing recipient: {recipient}")
                continue
            if not isinstance(content, str) or not content.strip():
                logger.warning(f"[{self.country}] Invalid or missing content for recipient {recipient}")
                continue
            
            recipient_upper = recipient.upper()
            if recipient_upper not in valid_recipients:
                logger.warning(f"[{self.country}] Recipient '{recipient_upper}' is not a valid power.")
                continue
            
            # Validate message_type
            final_message_type = constants.MESSAGE_TYPE_BROADCAST # Default
            if isinstance(message_type_str, str) and message_type_str.upper() in constants.VALID_MESSAGE_TYPES:
                final_message_type = message_type_str.upper()
            elif message_type_str is not None: # Log if a type was provided but invalid
                logger.warning(f"[{self.country}] Invalid message type '{message_type_str}', defaulting to BROADCAST.")

            messages.append(Message(recipient_upper, content.strip(), message_type=final_message_type))

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

            if self.llm_caller_override:
                result = await self.llm_caller_override(
                    prompt=prompt,
                    model_id=self.model_id,
                    agent_id=self.agent_id,
                    game_id=self.game_id,
                    phase=phase.phase_name,
                    system_prompt=self.system_prompt,
                    expected_fields=[constants.LLM_RESPONSE_KEY_DIARY_ENTRY],
                    verbose_llm_debug=self.config.verbose_llm_debug
                )
            else:
                result = await self.llm_coordinator.call_json(
                    prompt=prompt,
                    model_id=self.model_id,
                    agent_id=self.agent_id,
                    game_id=self.game_id,
                    phase=phase.phase_name,
                    system_prompt=self.system_prompt,
                    expected_fields=[constants.LLM_RESPONSE_KEY_DIARY_ENTRY],
                    verbose_llm_debug=self.config.verbose_llm_debug
                )
            
            diary_entry = result.get(constants.LLM_RESPONSE_KEY_DIARY_ENTRY) if result else None

            if diary_entry and isinstance(diary_entry, str):
                self.agent_state.add_diary_entry(diary_entry, phase.phase_name)

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
            "context_provider_type": self.resolved_context_provider_type,
            "goals": self.agent_state.goals,
            "relationships": self.agent_state.relationships,
            "diary_entries": len(self.agent_state.private_diary),
            "journal_entries": len(self.agent_state.private_journal),
        }

    async def consolidate_year_diary_entries(
        self, year: str, game: Any, llm_log_path: Optional[str]
    ) -> None:
        """
        Consolidates diary entries for a specific year using an LLM.
        Placeholder implementation.
        """
        logger.info(f"[{self.country}] Attempting to consolidate diary entries for year {year}. (Placeholder)")
        # TODO: Implement actual LLM-based diary consolidation logic
        # 1. Collect all diary entries for the given 'year'.
        # 2. Format them into a prompt asking the LLM to summarize.
        # 3. Call the LLM (e.g., self.llm_coordinator.call_text or call_json).
        # 4. Process the LLM's summary.
        # 5. Replace the old entries with the summary or store them appropriately.
        #    (e.g., self.agent_state.replace_diary_entries_for_year(year, summary_text))
        # For now, just log and do nothing to prevent AttributeError.
        pass
