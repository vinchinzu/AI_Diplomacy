"""
LLM-based agent implementation.
Extracts all LLM-specific logic from the original DiplomacyAgent while implementing the clean BaseAgent interface.
"""

# Core components from this project
from ..core.message import Message
from ..core.order import Order
from .base import (
    BaseAgent,
    PhaseState,
)  # BaseAgent for inheritance, PhaseState for type hinting
from ..services.config import AgentConfig, resolve_context_provider
from ..game_config import GameConfig as DiplomacyGameConfig
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
from generic_llm_framework.prompt_strategy import (
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
        game_config: DiplomacyGameConfig,
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
            game_config: The main game configuration object
            game_id: Game identifier for tracking
            llm_coordinator: LLM coordinator instance (will create if None)
            context_provider_factory: Context provider factory (will create if None)
            prompt_loader: Optional function to load prompts by filename
            llm_caller_override: Optional override for the LLM call logic. (Consider refactoring into GenericAgent config)
        """
        super().__init__(agent_id, country)
        self.config = config
        self.game_config = game_config
        self.power_name = country
        self.model_id = config.model_id
        self.game_id = game_id  # Diplomacy game_id
        self.llm_coordinator = (
            llm_coordinator or LLMCoordinator()
        )  # This should be the generic one

        # Context provider setup (remains Diplomacy-specific for now)
        self.context_factory = context_provider_factory or ContextProviderFactory()
        self.resolved_context_provider_type = resolve_context_provider(config)
        self.context_provider = self.context_factory.get_provider(
            self.resolved_context_provider_type
        )
        self.resolved_context_provider_type = self.context_provider.get_provider_type()

        # Agent state (Diplomacy-specific state)
        self.agent_state = DiplomacyAgentState(country=country)

        # Prompt strategy (Diplomacy-specific, but now inherits from BasePromptStrategy)
        # Pass base_prompts_dir if available from config or elsewhere
        self.diplomacy_prompt_strategy = DiplomacyPromptStrategy(
            config=config.prompt_strategy_config
            if config.prompt_strategy_config
            else None
        )

        self.prompt_loader = prompt_loader  # Potentially used by _load_system_prompt
        self.llm_caller_override = llm_caller_override

        # System prompt loading (Diplomacy-specific part)
        self.system_prompt = (
            self._load_system_prompt()
        )  # This is the diplomacy system prompt.
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
        default_prompt_filename = (
            diplomacy_constants.DEFAULT_SYSTEM_PROMPT_FILENAME
        )  # Use aliased constant
        system_prompt_str: Optional[str] = None  # Renamed to avoid conflict

        if self.prompt_loader:
            system_prompt_str = self.prompt_loader(power_prompt_filename)
            if not system_prompt_str:
                logger.warning(
                    f"Power-specific prompt '{power_prompt_filename}' not found via prompt_loader. Loading default."
                )
                system_prompt_str = self.prompt_loader(default_prompt_filename)
            else:
                logger.info(
                    f"Loaded power-specific system prompt for {self.country} via prompt_loader."
                )
        else:
            # Use generic llm_utils
            system_prompt_str = llm_utils.load_prompt_file(power_prompt_filename)
            if not system_prompt_str:
                logger.warning(
                    f"Power-specific prompt '{power_prompt_filename}' not found. Loading default."
                )
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

        logger.info(f"[{self.country}] Deciding orders for phase {phase.phase_name}")

        my_units = phase.get_power_units(self.country)
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
                "phase_name": phase.phase_name,
                "power_units": my_units,  # Added for more complete state
                "power_centers": phase.get_power_centers(self.country),  # Added
                # Add any other info DiplomacyPromptStrategy.build_order_prompt might need from context
            }

            # Possible actions for LLM (can be raw possible orders or structured context)
            # For now, using the context_result which might contain structured orders or context
            possible_orders_for_llm = context_result.get(
                "possible_orders_context", phase.get_all_possible_orders()
            )

            # Update GenericAgent's config for this specific call if needed (e.g., phase)
            self.generic_agent.config["phase"] = phase.phase_name
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

            orders_data = parsed_json_response.get(
                diplomacy_constants.LLM_RESPONSE_KEY_ORDERS
            )
            if (
                orders_data is not None
            ):  # Check for None explicitly, as empty list can be valid
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

    def _extract_orders_from_response(
        self, response_orders_data: Any, my_units: List[str]
    ) -> List[Order]:
        """Extract and validate orders from LLM response. Raises ValueError on failure."""
        # This method's internal logic remains the same.
        orders = []
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
                if (
                    isinstance(unit, str)
                    and isinstance(action, str)
                    and unit.strip()
                    and action.strip()
                ):
                    orders.append(Order(f"{unit.strip()} {action.strip()}"))
                else:
                    logger.warning(
                        f"[{self.country}] Invalid order dictionary item: {item}"
                    )
            else:
                logger.warning(f"[{self.country}] Invalid item in orders list: {item}")

        if not orders and my_units:
            error_msg = f"[{self.country}] No valid orders extracted from LLM response, though units exist. LLM provided: {response_orders_data}"
            logger.warning(error_msg)
            raise ValueError(error_msg)
        elif not my_units and orders:
            logger.warning(
                f"[{self.country}] LLM provided orders but no units to command. Orders: {orders}"
            )
            return []
        return orders

    async def negotiate(self, phase: PhaseState) -> List[Message]:
        """
        Generate diplomatic messages to send to other powers.

        Args:
            phase: Immutable snapshot of current game state

        Returns:
            List of messages to send
        """
        if self.config.type == "neutral":
            logger.info(f"[{self.country}] Skipping negotiation for neutral agent.")
            return []

        logger.info(
            f"[{self.country}] Generating messages for phase {phase.phase_name}"
        )

        try:
            context_data_obj = ContextData(  # Renamed
                phase_state=phase,
                possible_orders={"MOCK": ["Hold"]},  # Placeholder
                game_history=None,  # Placeholder
                recent_messages=None,  # Placeholder
                strategic_analysis=None,  # Placeholder
            )
            context_result = await self.context_provider.provide_context(
                agent_id=self.agent_id,
                country=self.country,
                context_data=context_data_obj,
                agent_config=self.config,
            )

            active_powers_list = [
                p
                for p in phase.powers
                if not phase.is_power_eliminated(p) and p != self.country
            ]

            diplomacy_specific_state_for_negotiation = {
                "country": self.country,
                "active_powers": active_powers_list,
                "goals": self.agent_state.goals,
                "relationships": self.agent_state.relationships,
                "formatted_diary": self.agent_state.format_private_diary_for_prompt(),
                "context_text": context_result.get("context_text", ""),
                "tools_available": context_result.get("tools_available", False),
                "phase_name": phase.phase_name,
                # Add any other info DiplomacyPromptStrategy.build_negotiation_prompt might need
            }

            # Update GenericAgent's config for this specific call if needed
            self.generic_agent.config["phase"] = phase.phase_name
            if context_result.get("tools_available"):
                self.generic_agent.config["tools"] = context_result.get("tools")
            else:
                self.generic_agent.config.pop("tools", None)

            # Call GenericLLMAgent's generate_communication
            # DiplomacyPromptStrategy will use action_type='generate_diplomacy_messages'
            parsed_json_response = await self.generic_agent.generate_communication(
                state=diplomacy_specific_state_for_negotiation,
                recipients=active_powers_list,  # Or a more structured recipient list if needed by generic agent
                action_type="generate_diplomacy_messages",
            )

            if parsed_json_response.get("error"):
                error_msg = f"[{self.country}] GenericAgent reported error during negotiation: {parsed_json_response['error']}"
                logger.error(error_msg)
                return []  # Return empty on error, or raise

            messages_data = parsed_json_response.get(
                diplomacy_constants.LLM_RESPONSE_KEY_MESSAGES
            )
            if messages_data is not None:  # Check for None explicitly
                messages = self._extract_messages_from_response(
                    parsed_json_response, phase
                )  # Pass the whole dict
                logger.info(
                    f"[{self.country}] Generated {len(messages)} messages using {context_result.get('provider_type', 'unknown')} context via GenericAgent"
                )
                return messages
            else:
                logger.warning(
                    f"[{self.country}] No '{diplomacy_constants.LLM_RESPONSE_KEY_MESSAGES}' field in LLM response via GenericAgent or response is None. Response: {parsed_json_response}"
                )
                return []

        except Exception as e:
            logger.error(
                f"[{self.country}] Error generating messages: {e}", exc_info=True
            )
            return []

    def _extract_messages_from_response(
        self,
        response: Optional[Dict[str, Any]],
        phase: PhaseState,  # response is the full JSON dict
    ) -> List[Message]:
        """Extract and validate messages from LLM response."""
        # This method's internal logic remains largely the same.
        messages = []
        if (
            response is None
            or diplomacy_constants.LLM_RESPONSE_KEY_MESSAGES not in response
        ):
            logger.warning(
                f"[{self.country}] No '{diplomacy_constants.LLM_RESPONSE_KEY_MESSAGES}' field in LLM response or response is None"
            )
            return messages

        message_data = response[diplomacy_constants.LLM_RESPONSE_KEY_MESSAGES]
        if not isinstance(message_data, list):
            logger.warning(f"[{self.country}] Messages field is not a list")
            return messages

        valid_recipients = phase.powers

        for msg_item in message_data:
            if not isinstance(msg_item, dict):
                logger.warning(f"[{self.country}] Invalid message item: {msg_item}")
                continue

            recipient = msg_item.get(diplomacy_constants.LLM_MESSAGE_KEY_RECIPIENT)
            content = msg_item.get(diplomacy_constants.LLM_MESSAGE_KEY_CONTENT)
            message_type_str = msg_item.get(diplomacy_constants.LLM_MESSAGE_KEY_TYPE)

            if not isinstance(recipient, str) or not recipient.strip():
                logger.warning(
                    f"[{self.country}] Invalid or missing recipient: {recipient}"
                )
                continue
            if not isinstance(content, str) or not content.strip():
                logger.warning(
                    f"[{self.country}] Invalid or missing content for recipient {recipient}"
                )
                continue

            recipient_upper = recipient.upper()
            if recipient_upper not in valid_recipients:
                logger.warning(
                    f"[{self.country}] Recipient '{recipient_upper}' is not a valid power."
                )
                continue

            final_message_type = diplomacy_constants.MESSAGE_TYPE_BROADCAST  # Default
            if (
                isinstance(message_type_str, str)
                and message_type_str.upper() in diplomacy_constants.VALID_MESSAGE_TYPES
            ):
                final_message_type = message_type_str.upper()
            elif message_type_str is not None:
                logger.warning(
                    f"[{self.country}] Invalid message type '{message_type_str}', defaulting to BROADCAST."
                )

            messages.append(
                Message(
                    recipient_upper, content.strip(), message_type=final_message_type
                )
            )
        return messages

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
        log_power = power_name or self.country
        logger.info(f"[{log_power}] Updating state after phase {phase.phase_name}")

        self.agent_state._update_relationships_from_events(self.country, events)

        # Call Generic Agent's update_internal_state
        await self.generic_agent.update_internal_state(state=phase, events=events)

        # The diplomacy-specific part of the state update (diary, goals) happens here.
        # Generate and add a diary entry for the concluded phase
        await self._generate_phase_diary_entry_with_generic_agent(phase, events, power_name=log_power)

        # Re-evaluate and update goals based on the new game state
        await self._analyze_and_update_goals_with_generic_agent(phase, power_name=log_power)

        logger.debug(
            f"[{log_power}] state updated for phase {phase.phase_name}. Current goals: {self.agent_state.goals}"
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
            "acting_power": log_power, # The specific power context for this action
            "phase_name": phase.phase_name,
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
            logger.error(
                f"[{log_power}] GenericAgent failed to generate diary entry: {response['error']}"
            )
            return

        diary_entry = response.get(diplomacy_constants.LLM_RESPONSE_KEY_DIARY_ENTRY)
        if diary_entry:
            self.agent_state.add_diary_entry(phase.phase_name, diary_entry)
            logger.info(
                f"[{log_power}] Added new diary entry for phase {phase.phase_name}"
            )
        else:
            logger.warning(
                f"[{log_power}] LLM did not return a diary entry for phase {phase.phase_name}. Response: {response}"
            )

    async def _analyze_and_update_goals_with_generic_agent(self, phase: PhaseState, power_name: Optional[str] = None):
        """
        Analyzes the current game state and updates the agent's goals using the generic agent.
        """
        log_power = power_name or self.country
        logger.debug(f"[{log_power}] Analyzing and updating goals...")

        # Prepare context for DiplomacyPromptStrategy
        diplomacy_specific_context = {
            "country": self.country, # The overarching agent/country identity
            "acting_power": log_power, # The specific power context for this action
            "phase_name": phase.phase_name,
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

        new_goals = response.get(diplomacy_constants.LLM_RESPONSE_KEY_GOALS)
        if new_goals and isinstance(new_goals, list):
            self.agent_state.update_goals(new_goals)
            logger.info(f"[{log_power}] Goals updated: {new_goals}")
        elif new_goals:
            logger.warning(
                f"[{log_power}] Goals response from LLM was not a list: {new_goals}. Type: {type(new_goals)}"
            )
        else:
            logger.warning(
                f"[{log_power}] LLM did not return new goals. Response: {response}"
            )

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

    async def consolidate_year_diary_entries(
        self, year: str, game: Any, llm_log_path: Optional[str]
    ) -> None:
        """
        Consolidates diary entries for a specific year using an LLM.
        Placeholder implementation.
        """
        if self.config.type == "neutral":
            logger.info(
                f"[{self.country}] Skipping diary consolidation for neutral agent (year {year})."
            )
            return

        logger.info(
            f"[{self.country}] Attempting to consolidate diary entries for year {year}. (Placeholder)"
        )
        # TODO: Implement actual LLM-based diary consolidation logic
        # 1. Collect all diary entries for the given 'year'.
        # 2. Format them into a prompt asking the LLM to summarize.
        # 3. Call the LLM (e.g., self.llm_coordinator.call_text or call_json).
        # 4. Process the LLM's summary.
        # 5. Replace the old entries with the summary or store them appropriately.
        #    (e.g., self.agent_state.replace_diary_entries_for_year(year, summary_text))
        # For now, just log and do nothing to prevent AttributeError.
        pass
