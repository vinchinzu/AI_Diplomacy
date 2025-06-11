import logging
from typing import List, Dict, Any, Optional
import jinja2

from .llm_agent import LLMAgent
from ..core.order import Order  # Corrected import
from ..core.state import PhaseState
from ..services.config import AgentConfig
from ..game_config import GameConfig as DiplomacyGameConfig
from generic_llm_framework.llm_coordinator import (
    LLMCoordinator,
)  # Ensure LLMAgent gets this type
from ..services.context_provider import ContextProviderFactory
from generic_llm_framework.llm_utils import load_prompt_file
from .. import constants as diplomacy_constants  # For diplomacy specific constants

logger = logging.getLogger(__name__)


class BlocLLMAgent(LLMAgent):
    """
    An LLM-based agent that controls a bloc of multiple countries.
    It makes decisions and generates orders for all countries in its bloc.
    """

    def __init__(
        self,
        agent_id: str,
        bloc_name: str,
        controlled_powers: List[str],
        config: AgentConfig,  # AgentConfig for LLMAgent
        game_config: DiplomacyGameConfig,
        game_id: str,  # Diplomacy game_id
        llm_coordinator: LLMCoordinator,
        context_provider_factory: ContextProviderFactory,
        prompt_loader: Optional[callable] = None,  # Remains for bloc_order_prompt.j2
    ):
        if not controlled_powers:
            raise ValueError(
                "BlocLLMAgent must be initialized with at least one controlled power."
            )

        representative_country = controlled_powers[0]

        # Ensure prompt_loader defaults to the generic load_prompt_file if None
        effective_prompt_loader = prompt_loader or load_prompt_file

        super().__init__(
            agent_id=agent_id,
            country=representative_country,
            config=config,
            game_config=game_config,
            game_id=game_id,  # Passed to LLMAgent -> GenericLLMAgent config
            llm_coordinator=llm_coordinator,  # Passed to LLMAgent -> GenericLLMAgent
            context_provider_factory=context_provider_factory,  # Used by LLMAgent
            prompt_loader=effective_prompt_loader,  # Used by LLMAgent for its system prompt
            # llm_caller_override is not explicitly handled here, LLMAgent's default is None
        )
        self.bloc_name = bloc_name
        self.controlled_powers = [p.upper() for p in controlled_powers]

        # Initialize relationships based on the bloc
        self.agent_state.initialize_bloc_relationships(
            allied_powers=self.controlled_powers,
            all_powers_in_game=diplomacy_constants.ALL_POWERS,
        )
        logger.info(
            f"BlocLLMAgent '{self.agent_id}' initialized relationships for bloc '{self.bloc_name}'. "
            f"Allies: {self.controlled_powers}. Current relationships: {self.agent_state.relationships}"
        )

        # self.country in LLMAgent is set to representative_country.
        # For BlocLLMAgent's own identity in logging or specific logic, bloc_name is clearer.
        # We can use self.bloc_name directly instead of overriding self.country after super init,
        # as self.generic_agent.agent_id will be bloc_agent_id.
        # LLMAgent's self.power_name is representative_country.
        # GenericAgent's self.agent_id is bloc_agent_id.
        # For clarity, let's keep self.country as representative_country as set by super()
        # and use self.bloc_name explicitly for bloc identity.

        # Cache for bloc orders
        self._cached_bloc_orders_this_phase: Dict[str, List[Order]] = {}
        self._cached_bloc_orders_phase_key: Optional[tuple] = None

        logger.info(
            f"BlocLLMAgent '{self.agent_id}' initialized for bloc '{self.bloc_name}' controlling {self.controlled_powers} "
            f"using model {self.model_id}. Representative country for superclass state: {representative_country}."
        )

    async def decide_orders(self, phase: PhaseState) -> List[Order]:
        """
        Decides orders for the bloc.
        Internally, it generates orders for ALL controlled powers and caches them.
        This method, to conform to BaseAgent, returns orders for the 'representative_country'
        (first power in controlled_powers list).
        A new method get_all_bloc_orders_for_phase can be used by an orchestrator
        to get all orders.
        """
        logger.debug(
            f"BlocLLMAgent '{self.agent_id}' ({self.bloc_name}) deciding orders for {self.controlled_powers} in phase {phase.phase_name}"
        )

        # Generate a unique key for the current phase state to manage caching
        # This key should represent the game state relevant to order decisions for the bloc.
        phase_repr_parts = []

        # --- Handle units information safely (tests may provide a minimal PhaseState mock) ---
        units_by_power = getattr(phase, "units", None)
        if units_by_power:
            for p_name in sorted(self.controlled_powers):
                power_units_locs_list = units_by_power.get(p_name, [])
                phase_repr_parts.append(
                    f"{p_name}_units:{tuple(sorted(power_units_locs_list))}"
                )

        # --- Handle supply center information safely ---
        scs_data = getattr(phase, "supply_centers", getattr(phase, "scs", None))
        if scs_data:
            sorted_scs_items = sorted(
                [(p, tuple(sorted(cs))) for p, cs in scs_data.items()]
            )
            phase_repr_parts.append(f"scs:{tuple(sorted(sorted_scs_items))}")

        current_phase_key = (
            phase.year,
            phase.season,
            phase.phase_name,
            tuple(phase_repr_parts),
        )

        if self._cached_bloc_orders_phase_key == current_phase_key:
            logger.debug(
                f"Using cached bloc orders for phase key elements: year={phase.year}, season={phase.season}, name={phase.phase_name}"
            )
        else:
            logger.info(
                f"New phase or state detected for bloc {self.bloc_name} (key elements: year={phase.year}, season={phase.season}, name={phase.phase_name}), querying LLM for bloc orders."
            )
            self._cached_bloc_orders_this_phase = {}  # Clear previous cache

            try:
                # self.prompt_loader is set in super().__init__
                order_prompt_template_content = self.prompt_loader(
                    "bloc_order_prompt.j2"
                )
            except FileNotFoundError:
                logger.error(
                    f"{self.agent_id}: bloc_order_prompt.j2 not found. Cannot generate bloc orders."
                )
                self._cached_bloc_orders_phase_key = current_phase_key
                return []
            except Exception as e:
                logger.error(
                    f"{self.agent_id}: Error loading bloc_order_prompt.j2: {e}",
                    exc_info=True,
                )
                self._cached_bloc_orders_phase_key = current_phase_key
                return []

            # Get all possible orders for the current phase
            all_possible_orders = phase.get_all_possible_orders()

            # Filter orders for the controlled powers of the bloc
            possible_orders_for_bloc = {
                power: orders
                for power, orders in all_possible_orders.items()
                if power in self.controlled_powers
            }

            prompt_context = {
                "bloc_name": self.bloc_name,
                "controlled_powers_list": self.controlled_powers,
                "phase": phase,
                "diary": self.agent_state.format_private_diary_for_prompt(),
                "goals": self.agent_state.goals,
                "relationships": self.agent_state.relationships,
                "possible_orders": possible_orders_for_bloc,
            }

            try:
                template = jinja2.Template(order_prompt_template_content)
                rendered_bloc_prompt = template.render(prompt_context)
            except jinja2.TemplateSyntaxError as e:
                logger.error(
                    f"{self.agent_id}: Jinja2 template syntax error: {e}", exc_info=True
                )
                self._cached_bloc_orders_phase_key = current_phase_key
                return []
            except Exception as e:
                logger.error(
                    f"{self.agent_id}: Error rendering Jinja2 template: {e}",
                    exc_info=True,
                )
                self._cached_bloc_orders_phase_key = current_phase_key
                return []

            logger.debug(
                f"BlocLLMAgent '{self.agent_id}' using pre-rendered prompt for orders (first 500 chars): {rendered_bloc_prompt[:500]}..."
            )

            # Prepare state for GenericLLMAgent, using the pre-rendered prompt
            # The action_type 'decide_bloc_orders' will instruct DiplomacyPromptStrategy to use this prompt directly.
            bloc_action_context = {
                "prompt_content": rendered_bloc_prompt,
                # Other context elements for DiplomacyPromptStrategy if it were to add headers/footers,
                # but for 'decide_bloc_orders' it uses prompt_content directly.
                "action_type": "decide_bloc_orders",  # This is more of a hint for prompt strategy
            }

            # Update GenericAgent's config for this specific call if the mock provides a 'config' attribute.
            if hasattr(self.generic_agent, "config") and self.generic_agent.config is not None:
                # The generic_agent's system_prompt is by default the one loaded by LLMAgent (representative country's or default diplomacy).
                # If bloc orders need a different system context, it should be set here or in the jinja template.
                # For now, we assume the jinja template contains all necessary instructions, including any system-like messages.
                try:
                    self.generic_agent.config["phase"] = phase.phase_name
                except Exception:
                    # In some mocks 'config' may be a simple MagicMock – ignore failures in test contexts.
                    pass

            parsed_llm_orders = {}
            try:
                # self.generic_agent is inherited from LLMAgent
                # LLMAgent's prompt_strategy is DiplomacyPromptStrategy, which now handles 'decide_bloc_orders'
                # The state passed to decide_action is the context for DiplomacyPromptStrategy.build_prompt
                parsed_llm_orders = await self.generic_agent.decide_action(
                    state=bloc_action_context,  # This context will be used by DiplomacyPromptStrategy
                    action_type=bloc_action_context.get("action_type", "decide_action"),
                    possible_actions=None,  # No separate possible_actions for bloc, it's in the prompt
                )

                if parsed_llm_orders.get("error"):
                    logger.error(
                        f"BlocLLMAgent '{self.agent_id}' error from generic_agent.decide_action: {parsed_llm_orders['error']}"
                    )
                    self._cached_bloc_orders_this_phase = {}  # Clear/set empty on error
                    self._cached_bloc_orders_phase_key = current_phase_key
                    return []

                logger.debug(
                    f"BlocLLMAgent '{self.agent_id}' raw LLM response (from generic_agent.decide_action): {parsed_llm_orders}"
                )

                valid_parsed_orders: Dict[str, List[Order]] = {}
                # parsed_llm_orders is already a dict from generic_agent.decide_action (which calls call_json)
                for power, orders_str_list in parsed_llm_orders.items():
                    # Check if the key is one of the controlled powers before processing
                    if power.upper() in self.controlled_powers:
                        if isinstance(orders_str_list, list) and all(
                            isinstance(o, str) for o in orders_str_list
                        ):
                            valid_parsed_orders[power.upper()] = [
                                Order(o) for o in orders_str_list
                            ]
                        else:
                            logger.warning(
                                f"{self.agent_id}: Invalid order list format for power {power} in LLM response. Skipping. Data: {orders_str_list}"
                            )
                    # Do not log warning for non-controlled powers if they are not expected in response,
                    # unless the prompt specifically asks for orders ONLY for controlled powers.
                    # If the LLM might return orders for other powers, this check is useful.
                    elif (
                        power != "error" and power != "details"
                    ):  # Skip our own error keys
                        logger.warning(
                            f"{self.agent_id}: LLM response included orders for non-controlled or unexpected key '{power}'. Ignoring."
                        )

                self._cached_bloc_orders_this_phase = valid_parsed_orders
                logger.info(
                    f"BlocLLMAgent '{self.agent_id}' successfully parsed orders for {list(self._cached_bloc_orders_this_phase.keys())}"
                )
                logger.debug(f"Parsed orders: {self._cached_bloc_orders_this_phase}")

            except Exception as e:  # Catch errors from generic_agent.decide_action or subsequent parsing
                logger.error(
                    f"BlocLLMAgent '{self.agent_id}' error during bloc order generation via generic_agent: {e}",
                    exc_info=True,
                )
                self._cached_bloc_orders_this_phase = {}

            self._cached_bloc_orders_phase_key = current_phase_key

        # Return orders for the representative country (first in list)
        representative_power_name = self.controlled_powers[0]
        orders_for_representative = self._cached_bloc_orders_this_phase.get(
            representative_power_name, []
        )

        if not orders_for_representative and self._cached_bloc_orders_this_phase:
            logger.warning(
                f"BlocLLMAgent '{self.agent_id}' got bloc orders, but none for representative {representative_power_name}."
            )
        elif self._cached_bloc_orders_this_phase:
            logger.info(
                f"BlocLLMAgent '{self.agent_id}' returning {len(orders_for_representative)} orders for representative {representative_power_name}."
            )

        return orders_for_representative

    def get_all_bloc_orders_for_phase(
        self,
        phase_key_tuple: tuple,  # This argument might need re-evaluation if phase state representation changes.
    ) -> Dict[str, List[Order]]:
        """
        Allows an orchestrator to retrieve all cached orders for all controlled powers for a given phase key.
        The phase_key_tuple must match the one used internally for caching.
        """
        # TODO: Review phase_key_tuple generation and usage for consistency.
        if self._cached_bloc_orders_phase_key == phase_key_tuple:
            return self._cached_bloc_orders_this_phase
        else:
            logger.warning(
                f"{self.agent_id}: Request for bloc orders for phase key {phase_key_tuple}, "
                f"but cache is for {self._cached_bloc_orders_phase_key if self._cached_bloc_orders_phase_key else 'None'}. "
                "Ensure decide_orders() was called for this phase and key matches."
            )
            return {}

    def get_agent_info(self) -> Dict[str, Any]:
        """
        Return basic information about this agent.
        """
        info = super().get_agent_info()
        info["diplomacy_agent_type"] = "BlocLLMAgent"  # Override the type from LLMAgent
        info["bloc_name"] = self.bloc_name
        info["controlled_powers"] = self.controlled_powers
        return info
