"""
LLM-based agent implementation.
Extracts all LLM-specific logic from the original DiplomacyAgent while implementing the clean BaseAgent interface.
"""

# Core components from this project
from ai_diplomacy.domain import DiploMessage, Order, PhaseState
from .base import (
    BaseAgent,
)  # BaseAgent for inheritance, PhaseState for type hinting
from ..services.config import AgentConfig, resolve_context_provider
from ..services.context_provider import (
    ContextProviderFactory,
    ContextData,
)  # ContextData remains here

import logging
from typing import List, Dict, Optional, Any, Callable, Awaitable

# Remains for Diplomacy BaseAgent interface
from .agent_state import DiplomacyAgentState  # Remains for LLMAgent's internal state

# Updated imports for generic framework
from generic_llm_framework.agent import GenericLLMAgent
from ..prompt_strategy import (
    DiplomacyPromptStrategy,
)  # Using the specific Diplomacy strategy
from generic_llm_framework.llm_coordinator import LLMCoordinator
from generic_llm_framework import llm_utils  # Now using the generic llm_utils
from .. import (
    constants as diplomacy_constants,
)  # Alias for diplomacy-specific constants
# from generic_llm_framework.constants import DEFAULT_GAME_ID, DEFAULT_PHASE_NAME # May not be needed if LLMAgent provides these

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
        game_id: str = diplomacy_constants.DEFAULT_GAME_ID,  # Use aliased diplomacy constant
        llm_coordinator: Optional[LLMCoordinator] = None,
        context_provider_factory: Optional[ContextProviderFactory] = None,
        prompt_loader: Optional[Callable[[str], Optional[str]]] = None,
        llm_caller_override: Optional[
            Callable[..., Awaitable[Dict[str, Any]]]
        ] = None,  # This might become part of GenericAgent's config
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
            llm_caller_override: Optional override for the LLM call logic. (Consider refactoring into GenericAgent config)
        """
        super().__init__(agent_id, country)
        self.config = config
        self.power_name = country
        self.model_id = config.model_id
        self.game_id = game_id  # Diplomacy game_id
        self.llm_coordinator = llm_coordinator or LLMCoordinator()  # This should be the generic one

        # Context provider setup (remains Diplomacy-specific for now)
        self.context_factory = context_provider_factory or ContextProviderFactory()
        self.resolved_context_provider_type = resolve_context_provider(config)
        self.context_provider = self.context_factory.get_provider(self.resolved_context_provider_type)
        self.resolved_context_provider_type = self.context_provider.get_provider_type()

        # Agent state (Diplomacy-specific state)
        self.agent_state = DiplomacyAgentState(country=country)

        # Prompt strategy (Diplomacy-specific, but now inherits from BasePromptStrategy)
        # Pass base_prompts_dir if available from config or elsewhere
        self.diplomacy_prompt_strategy = DiplomacyPromptStrategy(
            config=config.prompt_strategy_config if config.prompt_strategy_config else None
        )

        self.prompt_loader = prompt_loader  # Potentially used by _load_system_prompt
        self.llm_caller_override = llm_caller_override

        # System prompt loading (Diplomacy-specific part)
        self.system_prompt = self._load_system_prompt()  # This is the diplomacy system prompt.
        # GenericAgent's config will also get a system_prompt.

        # Generic Agent instantiation
        # We need to ensure the config passed to GenericLLMAgent is suitable.
        # It expects attributes like 'model_id', 'system_prompt', 'game_id', 'phase', 'verbose_llm_debug'.
        # We can construct a new dict or adapt AgentConfig.
        generic_agent_config = {
            "model_id": self.model_id,
            "system_prompt": self.system_prompt,  # Generic agent uses this as its default system prompt
            "game_id": self.game_id,  # Generic agent's game_id
            "verbose_llm_debug": self.config.verbose_llm_debug,
            # 'tools': if tools are used by generic agent
            # 'expected_action_fields': if generic agent needs this
        }
        if (
            self.llm_caller_override
        ):  # Pass override if present (though GenericAgent doesn't directly use this)
            generic_agent_config["llm_caller_override"] = self.llm_caller_override

        self.generic_agent = GenericLLMAgent(
            agent_id=self.agent_id,  # or self.power_name
            config=generic_agent_config,  # Pass the constructed config
            llm_coordinator=self.llm_coordinator,
            prompt_strategy=self.diplomacy_prompt_strategy,  # Pass the Diplomacy-specific strategy
        )

        logger.info(
            f"Initialized LLMAgent for {self.country} with model {self.config.model_id}, context provider: {self.resolved_context_provider_type}. GenericAgent also initialized."
        )
        self.agent_state.add_journal_entry(
            f"Agent initialized with model {self.config.model_id}, context provider: {self.resolved_context_provider_type}"
        )

    def _load_system_prompt(self) -> Optional[str]:
        """Load power-specific or default system prompt for Diplomacy."""
        power_prompt_filename = f"{self.country.lower()}_system_prompt.txt"
        default_prompt_filename = diplomacy_constants.DEFAULT_SYSTEM_PROMPT_FILENAME  # Use aliased constant
        system_prompt_str: Optional[str] = None  # Renamed to avoid conflict

        if self.prompt_loader:
            system_prompt_str = self.prompt_loader(power_prompt_filename)
            if not system_prompt_str:
                logger.warning(
                    f"Power-specific prompt '{power_prompt_filename}' not found via prompt_loader. Loading default."
                )
                system_prompt_str = self.prompt_loader(default_prompt_filename)
            else:
                logger.info(f"Loaded power-specific system prompt for {self.country} via prompt_loader.")
        else:
            # Use generic llm_utils
            system_prompt_str = llm_utils.load_prompt_file(power_prompt_filename)
            if not system_prompt_str:
                logger.warning(f"Power-specific prompt '{power_prompt_filename}' not found. Loading default.")
                system_prompt_str = llm_utils.load_prompt_file(default_prompt_filename)
            else:
                logger.info(f"Loaded power-specific system prompt for {self.country}.")

        if not system_prompt_str:
            logger.error(f"Could not load system prompt for {self.country}!")

        return system_prompt_str

    async def decide_orders(self, phase: PhaseState) -> List[Order]:
        """
        Decide what orders to submit for the current phase.

        Args:
            phase: Immutable snapshot of current game state

        Returns:
            List of orders to submit
        """
        if self.config.type == "neutral":
            logger.info(f"[{self.country}] Skipping order decision for neutral agent.")
            return []

        logger.info(f"[{self.country}] Deciding orders for phase {phase.name}")

        my_units = phase.board.get_units(self.country)
        if not my_units:
            logger.info(f"[{self.country}] No units to command")
            return []

        try:
            # Prepare context for DiplomacyPromptStrategy
            context_data_obj = ContextData(  # Renamed to avoid conflict with inner context_data
                phase_state=phase,
                # TODO: Replace MOCK possible orders with actual data if available to context_provider
                possible_orders={"MOCK": ["Hold"]},
                game_history=None,  # TODO: Pass actual game history if available
                recent_messages=None,  # TODO: Pass recent messages if available
                strategic_analysis=None,  # TODO: Pass analysis if available
            )
            context_result = await self.context_provider.provide_context(
                agent_id=self.agent_id,
                country=self.country,
                context_data=context_data_obj,
                agent_config=self.config,
            )

            # Construct diplomacy_specific_state_representation for GenericLLMAgent
            diplomacy_specific_state_representation = {
                "country": self.country,
                "goals": self.agent_state.goals,
                "relationships": self.agent_state.relationships,
                "formatted_diary": self.agent_state.format_private_diary_for_prompt(),
                "context_text": context_result.get("context_text", ""),
                "tools_available": context_result.get("tools_available", False),
                "phase_name": phase.name,
                "power_units": my_units,  # Added for more complete state
                "power_centers": phase.board.supply_centers.get(self.country, []),  # Added
                # Add any other info DiplomacyPromptStrategy.build_order_prompt might need from context
            }

            # Possible actions for LLM (can be raw possible orders or structured context)
            # For now, using the context_result which might contain structured orders or context
            possible_orders_for_llm = context_result.get(
                "possible_orders_context", {} # phase.get_all_possible_orders() - this method doesn't exist yet
            )

            # Update GenericAgent's config for this specific call if needed (e.g., phase)
            self.generic_agent.config["phase"] = phase.name
            if context_result.get("tools_available"):
                self.generic_agent.config["tools"] = context_result.get("tools")
            else:
                self.generic_agent.config.pop("tools", None)

            # Call GenericLLMAgent's decide_action
            # DiplomacyPromptStrategy will use action_type='decide_diplomacy_orders'
            parsed_json_response = await self.generic_agent.decide_action(
                state=diplomacy_specific_state_representation,
                possible_actions=possible_orders_for_llm,
                action_type="decide_diplomacy_orders",
            )

            if parsed_json_response.get("error"):
                error_msg = f"[{self.country}] GenericAgent reported error deciding orders: {parsed_json_response['error']} - {parsed_json_response.get('details')}"
                logger.error(error_msg)
                # Decide on strictness: raise error or return empty list
                raise ValueError(error_msg)

            orders_data = parsed_json_response.get(diplomacy_constants.LLM_RESPONSE_KEY_ORDERS)
            if orders_data is not None:  # Check for None explicitly, as empty list can be valid
                orders = self._extract_orders_from_response(orders_data, my_units)
                logger.info(
                    f"[{self.country}] Generated {len(orders)} orders using {context_result.get('provider_type', 'unknown')} context via GenericAgent"
                )
                return orders
            else:
                error_msg = f"[{self.country}] No valid '{diplomacy_constants.LLM_RESPONSE_KEY_ORDERS}' field in LLM response via GenericAgent. Response: {parsed_json_response}"
                logger.error(error_msg)
                raise ValueError(error_msg)

        except ValueError as ve:
            logger.error(f"[{self.country}] ValueError deciding orders: {ve}")
            raise
        except Exception as e:
            error_msg = f"[{self.country}] Unexpected error deciding orders: {e}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e

    def _extract_orders_from_response(self, response_orders_data: Any, my_units: List[str]) -> List[Order]:
        """Extract and validate orders from LLM response. Raises ValueError on failure."""
        # This method's internal logic remains the same.
        orders = []
        if not isinstance(response_orders_data, list):
            error_msg = (
                f"[{self.country}] Orders field from LLM is not a list. Got: {type(response_orders_data)}"
            )
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

        if not orders and my_units:
            error_msg = f"[{self.country}] No valid orders extracted from LLM response, though units exist. LLM provided: {response_orders_data}"
            logger.warning(error_msg)
            raise ValueError(error_msg)
        elif not my_units and orders:
            logger.warning(f"[{self.country}] LLM provided orders but no units to command. Orders: {orders}")
            return []
        return orders

    async def negotiate(self, phase: PhaseState) -> List[DiploMessage]:
        """
        Engage in diplomacy with other agents.

        Args:
            phase: Immutable snapshot of current game state

        Returns:
            List of messages to send
        """
        logger.info(f"[{self.country}] Negotiating for phase {phase.name}")

        try:
            # Prepare context for DiplomacyPromptStrategy (similar to decide_orders)
            context_data_obj = ContextData(
                phase_state=phase,
                possible_orders={},
                game_history=None,
                recent_messages=None,
                strategic_analysis=None,
            )
            context_result = await self.context_provider.provide_context(
                agent_id=self.agent_id,
                country=self.country,
                context_data=context_data_obj,
                agent_config=self.config,
            )

            diplomacy_specific_state_representation = {
                "country": self.country,
                "goals": self.agent_state.goals,
                "relationships": self.agent_state.relationships,
                "formatted_diary": self.agent_state.format_private_diary_for_prompt(),
                "context_text": context_result.get("context_text", ""),
                "phase_name": phase.name,
            }

            self.generic_agent.config["phase"] = phase.name

            # Call GenericLLMAgent's decide_action for negotiation
            # DiplomacyPromptStrategy will use action_type='decide_diplomacy_messages'
            parsed_json_response = await self.generic_agent.decide_action(
                state=diplomacy_specific_state_representation,
                possible_actions={},  # No specific actions for negotiation prompts usually
                action_type="decide_diplomacy_messages",
            )

            if parsed_json_response.get("error"):
                error_msg = f"[{self.country}] GenericAgent reported error during negotiation: {parsed_json_response['error']} - {parsed_json_response.get('details')}"
                logger.error(error_msg)
                return []

            messages = self._extract_messages_from_response(parsed_json_response, phase)
            return messages

        except Exception as e:
            logger.error(f"[{self.country}] Error during negotiation: {e}", exc_info=True)
            return []

    def _extract_messages_from_response(
        self,
        response: Optional[Dict[str, Any]],
        phase: PhaseState,  # response is the full JSON dict
    ) -> List[DiploMessage]:
        """
        Extracts and validates messages from the LLM's JSON response.

        Args:
            response: The parsed JSON response from the LLM.
            phase: Current phase state, used to validate recipients.

        Returns:
            A list of valid Message objects.
        """
        if not response:
            return []

        messages_data = response.get(diplomacy_constants.LLM_RESPONSE_KEY_MESSAGES)
        if not isinstance(messages_data, list):
            logger.warning(
                f"[{self.country}] 'messages' key in response is not a list, but {type(messages_data)}. No messages extracted."
            )
            return []

        extracted_messages: List[DiploMessage] = []
        active_powers = list(phase.scs.keys())

        for msg_item in messages_data:
            if not isinstance(msg_item, dict):
                logger.warning(
                    f"[{self.country}] Item in 'messages' list is not a dictionary. Skipping."
                )
                continue

            recipient = msg_item.get(diplomacy_constants.LLM_MESSAGE_KEY_RECIPIENT)
            content = msg_item.get(diplomacy_constants.LLM_MESSAGE_KEY_CONTENT)

            if not recipient or not content:
                logger.warning(
                    f"[{self.country}] Skipping message with missing recipient or content: {msg_item}"
                )
                continue

            # Validate recipient
            if recipient.upper() not in active_powers and recipient.upper() != "GLOBAL":
                logger.warning(
                    f"[{self.country}] Skipping message to invalid recipient '{recipient}'"
                )
                continue

            # Create a simplified DiploMessage for now
            extracted_messages.append(DiploMessage())

        return extracted_messages

    async def update_state(
        self,
        phase: PhaseState,
        events: List[Dict[str, Any]],
        power_name: Optional[str] = None,
    ) -> None:
        """
        Update the agent's internal state based on the latest phase and events.
        Args:
            phase: Immutable snapshot of the current game state
            events: List of adjudicated results/events for the agent's power
            power_name: The name of the power being updated. If None, defaults to self.country.
        """
        power_name_to_update = power_name or self.country
        logger.info(f"[{power_name_to_update}] Updating state after phase {phase.name}")

        try:
            # Generate and add diary entry for the phase
            await self._generate_phase_diary_entry_with_generic_agent(
                phase, events, power_name=power_name_to_update
            )

            # Analyze and update long-term goals
            await self._analyze_and_update_goals_with_generic_agent(
                phase, power_name=power_name_to_update
            )

        except Exception as e:
            logger.error(
                f"[{power_name_to_update}] Error updating agent state: {e}",
                exc_info=True,
            )

    async def _generate_phase_diary_entry_with_generic_agent(
        self, phase: PhaseState, events: List[Dict[str, Any]], power_name: Optional[str] = None
    ):
        """
        Generates a diary entry for the current phase using the generic agent.
        """
        log_power = power_name or self.country
        logger.debug(f"[{log_power}] Generating phase-end diary entry...")

        # Prepare context for DiplomacyPromptStrategy
        diplomacy_specific_context = {
            "country": self.country,  # The overarching agent/country identity
            "acting_power": log_power,  # The specific power context for this action
            "phase_name": phase.name,
            "phase_state_repr": repr(phase),  # A string representation of the state
            "events_repr": repr(events),  # A string representation of events
        }

        # The generic agent's decide_action is used to generate text content (the diary entry)
        # The 'generate_diary_entry' action_type will be handled by DiplomacyPromptStrategy
        response = await self.generic_agent.decide_action(
            state=diplomacy_specific_context,
            action_type="generate_diary_entry",
            possible_actions=None,  # No explicit actions, it's a generation task
        )

        if response.get("error"):
            logger.error(f"[{log_power}] GenericAgent failed to generate diary entry: {response['error']}")
            return

        diary_entry = response.get(diplomacy_constants.LLM_RESPONSE_KEY_DIARY_ENTRY)
        if diary_entry:
            self.agent_state.add_journal_entry(diary_entry, phase.name)
            logger.info(f"[{log_power}] Added new diary entry for phase {phase.name}")
        else:
            logger.warning(
                f"[{log_power}] LLM did not return a diary entry for phase {phase.name}. Response: {response}"
            )

    async def _analyze_and_update_goals_with_generic_agent(
        self, phase: PhaseState, power_name: Optional[str] = None
    ):
        """
        Analyzes the current game state and updates the agent's goals using the generic agent.
        """
        log_power = power_name or self.country
        logger.debug(f"[{log_power}] Analyzing and updating goals...")

        # Prepare context for DiplomacyPromptStrategy
        diplomacy_specific_context = {
            "country": self.country,  # The overarching agent/country identity
            "acting_power": log_power,  # The specific power context for this action
            "phase_name": phase.name,
            "current_goals": self.agent_state.goals,
            "phase_state_repr": repr(phase),
        }

        # The 'update_goals' action_type will be handled by DiplomacyPromptStrategy
        response = await self.generic_agent.decide_action(
            state=diplomacy_specific_context,
            action_type="update_goals",
            possible_actions=None,  # Generation task
        )

        if response.get("error"):
            logger.error(f"[{log_power}] GenericAgent failed to update goals: {response['error']}")
            return

        new_goals = response.get(diplomacy_constants.LLM_RESPONSE_KEY_UPDATED_GOALS)
        if new_goals and isinstance(new_goals, list):
            self.agent_state.update_goals(new_goals)
            logger.info(f"[{log_power}] Goals updated: {new_goals}")
        elif new_goals:
            logger.warning(
                f"[{log_power}] Goals response from LLM was not a list: {new_goals}. Type: {type(new_goals)}"
            )
        else:
            logger.warning(f"[{log_power}] LLM did not return new goals. Response: {response}")

    def get_agent_info(self) -> Dict[str, Any]:
        """
        Return basic information about this agent.
        """
        # Get info from generic_agent and merge or nest it
        generic_info = self.generic_agent.get_agent_info()

        return {
            "diplomacy_agent_id": self.agent_id,
            "country": self.country,
            "diplomacy_agent_type": "LLMAgent",
            "diplomacy_model_id": self.config.model_id,  # Model used for Diplomacy specific system prompt if different
            "context_provider_type": self.resolved_context_provider_type,
            "diplomacy_goals": self.agent_state.goals,
            "diplomacy_relationships": self.agent_state.relationships,
            "diplomacy_diary_entries": len(self.agent_state.private_diary),
            "diplomacy_journal_entries": len(self.agent_state.private_journal),
            "generic_agent_info": generic_info,  # Nested info from the generic agent
        }

    async def consolidate_year_diary_entries(self, year: str, game: Any, llm_log_path: Optional[str]) -> None:
        """Consolidates diary entries for a given year using an LLM."""
        # This method's dependency on 'game' object needs to be removed.
        # It should operate on data passed to it, not fetch from a game object.
        # For now, we'll disable it.
        logger.warning("Consolidation of diary entries is temporarily disabled during refactoring.")
        pass
