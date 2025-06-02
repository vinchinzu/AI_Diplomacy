import logging
import json  # For parsing LLM response
from typing import List, Dict, Any, Optional
import jinja2 # Import jinja2

from .llm_agent import LLMAgent
from .base import Order  # Order and Message are needed
from ..core.state import PhaseState
from ..services.config import AgentConfig
from ..services.llm_coordinator import LLMCoordinator
from ..services.context_provider import ContextProviderFactory  # , ContextProvider
from ..llm_utils import load_prompt_file  # For prompt loading

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
        config: AgentConfig,
        game_id: str,
        llm_coordinator: LLMCoordinator,
        context_provider_factory: ContextProviderFactory,
        prompt_loader: Optional[callable] = None,
    ):
        if not controlled_powers:
            raise ValueError(
                "BlocLLMAgent must be initialized with at least one controlled power."
            )
        # representative_country is used for super() call, mainly for initializing
        # things like self.model_id, self.config from LLMAgent.
        # The actual "country" context for BlocLLMAgent operations will be the bloc_name or all controlled_powers.
        representative_country = controlled_powers[0]

        super().__init__(
            agent_id=agent_id,
            country=representative_country,  # Used by superclass for some logging/state
            config=config,  # Contains model_id, temperature, max_tokens etc.
            game_id=game_id,
            llm_coordinator=llm_coordinator,
            context_provider_factory=context_provider_factory,
            prompt_loader=prompt_loader or load_prompt_file,
        )
        self.bloc_name = bloc_name
        self.controlled_powers = [p.upper() for p in controlled_powers]

        # Override self.country to be the bloc_name for clarity in agent's own identity.
        # The superclass (LLMAgent) might use its self.country for some context,
        # but BlocLLMAgent specific methods will use bloc_name or controlled_powers.
        self.country = bloc_name

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
        if phase.units: # Check if there are any units on the board for any power
            for p_name in sorted(self.controlled_powers):
                power_units_locs_list = phase.units.get(p_name, []) # Get list of unit strings
                # The original key used locations. A unit string like "A BUD" implies location BUD.
                # We need to extract locations for sorting if the original key relied on that.
                # For simplicity now, let's use the sorted list of unit strings directly.
                # If specific locations were extracted and sorted, that would need more processing.
                phase_repr_parts.append(f"{p_name}_units:{tuple(sorted(power_units_locs_list))}")

        # The original key used phase.scs.items() which implies a dict. 
        # PhaseState has `supply_centers` as Dict[power, List[center_names]].
        # To replicate `phase.scs.items()`, we can use phase.supply_centers.items()
        # then sort these items for a stable key.
        if phase.supply_centers:
             # Sort by power name, then sort the list of centers for each power
            sorted_scs_items = sorted([
                (p, tuple(sorted(cs)))
                for p, cs in phase.supply_centers.items()
            ])
            phase_repr_parts.append(f"scs:{tuple(sorted_scs_items)}")


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
                order_prompt_template_content = self.prompt_loader(
                    "bloc_order_prompt.j2"
                )
            except FileNotFoundError:
                logger.error(
                    f"{self.agent_id}: bloc_order_prompt.j2 not found. Cannot generate bloc orders."
                )
                self._cached_bloc_orders_phase_key = (
                    current_phase_key  # Cache empty result for this phase
                )
                return []  # Return empty for representative if prompt missing
            except Exception as e:
                logger.error(
                    f"{self.agent_id}: Error loading bloc_order_prompt.j2: {e}",
                    exc_info=True,
                )
                self._cached_bloc_orders_phase_key = current_phase_key
                return []

            prompt_context = {
                "bloc_name": self.bloc_name,
                "controlled_powers_list": self.controlled_powers,
                "phase": phase,  # Pass the whole PhaseState object to the template
            }

            # Use Jinja2 directly
            try:
                template = jinja2.Template(order_prompt_template_content)
                full_prompt = template.render(prompt_context)
            except jinja2.TemplateSyntaxError as e:
                logger.error(
                    f"{self.agent_id}: Jinja2 template syntax error in bloc_order_prompt.j2: {e}",
                    exc_info=True,
                )
                self._cached_bloc_orders_phase_key = current_phase_key
                return [] # Return empty for representative if template error
            except Exception as e: # Catch any other Jinja rendering errors
                logger.error(
                    f"{self.agent_id}: Error rendering Jinja2 template bloc_order_prompt.j2: {e}",
                    exc_info=True,
                )
                self._cached_bloc_orders_phase_key = current_phase_key
                return []

            logger.debug(
                f"BlocLLMAgent '{self.agent_id}' sending prompt for orders (first 500 chars): {full_prompt[:500]}..."
            )
            llm_response_text = ""
            try:
                # Use max_tokens from self.config (AgentConfig)
                max_tokens_to_use = (
                    self.config.max_tokens
                    if self.config.max_tokens is not None
                    else 2000
                )  # Default if None

                # BlocLLMAgent expects a JSON object where keys are power names.
                # LLMAgent uses call_json with expected_fields=["orders"].
                # Here, the top-level keys are the power names themselves.
                # We can use call_json and let it parse the JSON. If expected_fields is None/empty,
                # it should return the whole parsed dict.
                parsed_llm_orders = await self.llm_coordinator.call_json(
                    prompt=full_prompt,
                    model_id=self.model_id,
                    agent_id=self.agent_id, # self.agent_id is the bloc agent's ID
                    game_id=self.game_id,
                    phase=phase.phase_name,
                    system_prompt=self.system_prompt, # Inherited from LLMAgent
                    # expected_fields=None, # Let call_json return the full parsed dictionary
                    # tools=None, # No specific tools defined here for bloc order generation yet
                    verbose_llm_debug=self.config.verbose_llm_debug,
                    # Temperature and max_tokens are not direct params of call_json.
                    # They are usually handled by the underlying llm library via model defaults or if 
                    # call_json passes **kwargs to a lower level call that uses them.
                    # For now, relying on model/coordinator defaults. If direct control is needed,
                    # LLMCoordinator.request or a direct call to llm_call_internal might be an alternative, 
                    # but call_json is simpler if it works.
                )

                logger.debug(
                    f"BlocLLMAgent '{self.agent_id}' raw LLM response (from call_json): {parsed_llm_orders}"
                )

                # No need for json.loads, as call_json returns a dict.
                # parsed_llm_orders: Dict[str, List[str]] = json.loads(llm_response_text)

                valid_parsed_orders: Dict[str, List[Order]] = {}
                for power, orders_str_list in parsed_llm_orders.items():
                    power_upper = power.upper()  # Normalize key from LLM
                    if power_upper in self.controlled_powers:
                        if isinstance(orders_str_list, list) and all(
                            isinstance(o, str) for o in orders_str_list
                        ):
                            valid_parsed_orders[power_upper] = [
                                Order(o) for o in orders_str_list
                            ]
                        else:
                            logger.warning(
                                f"{self.agent_id}: Invalid order list format for power {power_upper} in LLM response. Skipping. Data: {orders_str_list}"
                            )
                    else:
                        logger.warning(
                            f"{self.agent_id}: LLM response included orders for unexpected/uncontrolled power '{power_upper}'. Ignoring."
                        )

                self._cached_bloc_orders_this_phase = valid_parsed_orders
                logger.info(
                    f"BlocLLMAgent '{self.agent_id}' successfully parsed orders for {list(self._cached_bloc_orders_this_phase.keys())}"
                )
                logger.debug(f"Parsed orders: {self._cached_bloc_orders_this_phase}")

            except json.JSONDecodeError as e:
                logger.error(
                    f"BlocLLMAgent '{self.agent_id}' failed to parse LLM JSON response: {e}. Response (first 500 chars): {llm_response_text[:500]}"
                )
                # Cache is already empty if new phase, or keep old cache if error on update?
                # For safety, let's ensure it's empty for this attempt.
                self._cached_bloc_orders_this_phase = {}
            except Exception as e:
                logger.error(
                    f"BlocLLMAgent '{self.agent_id}' error during LLM call or parsing: {e}",
                    exc_info=True,
                )
                self._cached_bloc_orders_this_phase = {}

            self._cached_bloc_orders_phase_key = current_phase_key

        # To conform to BaseAgent.decide_orders, return orders for the representative country.
        # The orchestrator can use get_all_bloc_orders_for_phase to get all orders.
        # self.country for LLMAgent was set to representative_country in super().__init__
        # but we overrode self.country to bloc_name. So use controlled_powers[0].
        representative_country_for_return = self.controlled_powers[0]
        orders_for_representative = self._cached_bloc_orders_this_phase.get(
            representative_country_for_return, []
        )

        if self._cached_bloc_orders_this_phase and not orders_for_representative:
            logger.warning(
                f"BlocLLMAgent '{self.agent_id}' (bloc {self.bloc_name}) generated bloc orders, "
                f"but no orders found for representative power {representative_country_for_return}. "
                f"Returning empty list for it. Full bloc orders cached for powers: {list(self._cached_bloc_orders_this_phase.keys())}"
            )
        elif self._cached_bloc_orders_this_phase:
            logger.info(
                f"BlocLLMAgent '{self.agent_id}' (bloc {self.bloc_name}) returning "
                f"{len(orders_for_representative)} orders for representative power {representative_country_for_return}. "
                f"Full bloc orders cached for powers: {list(self._cached_bloc_orders_this_phase.keys())}"
            )

        return orders_for_representative

    def get_all_bloc_orders_for_phase(
        self, phase_key_tuple: tuple
    ) -> Dict[str, List[Order]]:
        """
        Allows an orchestrator to retrieve all cached orders for all controlled powers for a given phase key.
        The phase_key_tuple must match the one used internally for caching.
        """
        if self._cached_bloc_orders_phase_key == phase_key_tuple:
            return self._cached_bloc_orders_this_phase
        else:
            logger.warning(
                f"{self.agent_id}: Request for bloc orders for phase key {phase_key_tuple}, "
                f"but cache is for {self._cached_bloc_orders_phase_key if self._cached_bloc_orders_phase_key else 'None'}. "
                "This may happen if get_all_bloc_orders_for_phase is called before decide_orders for the current phase, "
                "or if the phase key construction differs."
            )
            return {}

    # Inherit negotiate and update_state from LLMAgent.
    # For negotiate, the LLMAgent's default uses self.country, which is bloc_name.
    # This means the bloc negotiates as a single entity, which is intended.
    # The prompt strategy for negotiation in LLMAgent would need to be aware of this.
    # For update_state (diary), it will also use self.country (bloc_name).

    def get_agent_info(self) -> Dict[str, Any]:
        """
        Return basic information about this agent.
        """
        info = super().get_agent_info()  # Calls LLMAgent's get_agent_info
        info["type"] = "BlocLLMAgent"
        info["bloc_name"] = self.bloc_name
        info["controlled_powers"] = self.controlled_powers
        # The 'country' in info will be bloc_name due to self.country = bloc_name in __init__
        return info
