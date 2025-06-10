import logging
import asyncio
from typing import (
    Optional,
    List,
    Dict,
    Callable,
    Coroutine,
    TYPE_CHECKING,
    Any,
    Protocol,
)
from diplomacy import Game

# Relative imports will need to be adjusted based on the new location
from ..general_utils import gather_possible_orders  # Adjusted import
from ..agents.llm_agent import LLMAgent  # Adjusted import
from ..core.state import PhaseState  # Adjusted import
from ..agents.base import BaseAgent # Corrected: Order and Message removed
from ..core.order import Order # Added: Correct import for Order
from ..core.message import Message # Added: Correct import for Message
from ..services.config import GameConfig  # Adjusted import
from ..utils.phase_parsing import (
    get_phase_type_from_game
    extract_year_from_phase
    PhaseType
)  # Adjusted import

# Import actual strategy classes
from .movement import MovementPhaseStrategy
from .retreat import RetreatPhaseStrategy
from .build import BuildPhaseStrategy

try:
    from diplomacy.utils.game_phase_data import GamePhaseData
except ImportError:
    GamePhaseData = None  # type: ignore
    logging.getLogger(__name__).info("Could not import GamePhaseData from diplomacy.utils.game_phase_data. Will rely on hasattr checks.")


# Protocol for PhaseStrategy
class PhaseStrategy(Protocol):
    async def get_orders(
        self
        game: "Game"
        orchestrator: "PhaseOrchestrator"
        game_history: "GameHistory"
    ) -> Dict[str, List[str]]: ...


if TYPE_CHECKING:
    from diplomacy import Game
    from ..agent_manager import AgentManager  # Adjusted import
    from ..game_history import GameHistory  # Adjusted import
    from ..agents.base import BaseAgent # Corrected: Order and Message removed
    # Order and Message already imported above, no need to re-import here if this block is separate
    from ..services.config import GameConfig  # Adjusted import
"""
Orchestrates the main game loop and phase transitions in a Diplomacy game.

This module defines the PhaseOrchestrator class, which is responsible for
managing the overall game flow. It coordinates agent actions, negotiations
order submissions, and game state processing across different game phases
(Movement, Retreat, Build). It utilizes specific strategy classes for each
phase type.
"""
from .. import constants  # Import constants

logger = logging.getLogger(__name__)

__all__ = ["PhaseOrchestrator", "PhaseStrategy"]  # Added PhaseStrategy Protocol

GetValidOrdersFuncType = Callable[
    [
        "Game"
        str
        str
        Any
        str
        Dict[str, List[str]]
        "GameHistory"
        str
        "GameConfig"
        Optional[List[str]]
        Optional[Dict[str, str]]
        Optional[str]
        str
        str
    ]
    Coroutine[Any, Any, List[str]]
]


class PhaseOrchestrator:  # Renamed from GamePhaseOrchestrator
    # Class docstring already exists and is good.

    def __init__(
        self
        game_config: "GameConfig"
        agent_manager: "AgentManager"
        get_valid_orders_func: GetValidOrdersFuncType,  # This might be removed if all agents use the new API
    ):
        self.config = game_config
        self.agent_manager = agent_manager
        self.get_valid_orders_func = get_valid_orders_func
        self.active_powers: List[str] = []

        if self.config.powers_and_models:
            self.active_powers = list(self.config.powers_and_models.keys())
        else:
            logger.warning(
                "GameConfig.powers_and_models not set when PhaseOrchestrator is initialized. Active powers list will be empty initially."
            )

        self._phase_map: Dict[
            PhaseType, PhaseStrategy
        ] = {  # Ensure correct type hint for _phase_map
            PhaseType.MVT: MovementPhaseStrategy()
            PhaseType.RET: RetreatPhaseStrategy()
            PhaseType.BLD: BuildPhaseStrategy()
        }

    async def run_game_loop(self, game: "Game", game_history: "GameHistory"):
        logger.info(f"Starting game loop for game ID: {self.config.game_id}")
        self.config.game_instance = game

        try:
            while True:
                current_phase_val = getattr(game, "phase", constants.DEFAULT_PHASE_NAME)
                current_year = getattr(game, "year", None)
                if current_year is None:
                    current_year = extract_year_from_phase(current_phase_val)

                if (
                    self.config.max_years
                    and current_year is not None
                    and current_year >= self.config.max_years
                ):
                    logger.info(
                        f"Reached max_year {self.config.max_years}. Ending game."
                    )
                    try:
                        game.draw()
                        logger.info("Game marked as completed via draw.")
                    except Exception as e:
                        logger.warning(
                            f"Could not call game.draw(): {e}. Setting status manually."
                        )
                        if hasattr(game, "set_status"):
                            game.set_status(constants.GAME_STATUS_COMPLETED)
                        if hasattr(game, "phase"):
                            game.phase = constants.GAME_STATUS_COMPLETED
                    break

                if game.is_game_done:
                    logger.info("Game is done. Exiting game loop.")
                    break

                logger.info(f"--- Current Phase: {current_phase_val} ---")
                game_history.add_phase(current_phase_val)

                self.active_powers = [
                    p
                    for p in game.powers
                    if p in self.config.powers_and_models
                    and not game.powers[p].is_eliminated()
                ]
                if not self.active_powers:
                    logger.info(
                        "No active LLM-controlled powers remaining. Ending game."
                    )
                    break
                logger.info(
                    f"Active LLM-controlled powers for this phase: {self.active_powers}"
                )

                all_orders_for_phase: Dict[str, List[str]] = {}
                phase_type_val_str = get_phase_type_from_game(game)

                strategy: Optional[PhaseStrategy] = None
                if phase_type_val_str != "-":
                    try:
                        phase_type_enum_val = PhaseType(phase_type_val_str)
                        strategy = self._phase_map.get(phase_type_enum_val)
                    except ValueError:
                        logger.error(
                            f"Invalid phase type string from get_phase_type_from_game: {phase_type_val_str}"
                        )
                        # Decide how to handle: skip, error, default? For now, process to next.
                        game.process()
                        continue

                if strategy:
                    all_orders_for_phase = await strategy.get_orders(
                        game, self, game_history
                    )
                elif phase_type_val_str == constants.PHASE_TYPE_PROCESS_ONLY:
                    current_phase_str = game.get_current_phase()
                    logger.info(
                        f"Phase is '{current_phase_str}', processing to next phase."
                    )
                    game.process()
                    continue
                else:
                    logger.error(
                        f"No strategy found for phase type value: {phase_type_val_str} from phase {current_phase_val}. Attempting to process."
                    )
                    game.process()
                    continue

                await self._process_phase_results_and_updates(
                    game, game_history, all_orders_for_phase, current_phase_val
                )

                current_year = getattr(game, "year", None)
                if current_year is None:
                    current_year = extract_year_from_phase(current_phase_val)
                if (
                    self.config.max_years
                    and current_year is not None
                    and current_year >= self.config.max_years
                ):
                    current_phase_type_val = get_phase_type_from_game(game)
                    if (
                        current_phase_type_val == PhaseType.BLD.value
                        and constants.PHASE_STRING_WINTER in current_phase_val.upper()
                    ) or (
                        constants.PHASE_STRING_WINTER in current_phase_val.upper()
                        and game.is_game_done
                    ):
                        logger.info(
                            f"Reached max_years ({self.config.max_years}). Ending game after {current_phase_val}."
                        )
                        try:
                            game.draw()
                            logger.info("Game marked as completed via draw.")
                        except Exception as e:
                            logger.warning(
                                f"Could not call game.draw(): {e}. Setting status manually."
                            )
                            if hasattr(game, "set_status"):
                                game.set_status(constants.GAME_STATUS_COMPLETED)
                            if hasattr(game, "phase"):
                                game.phase = constants.GAME_STATUS_COMPLETED
                        break
            logger.info(
                f"Game {self.config.game_id} finished. Final phase: {game.get_current_phase()}"
            )
        except AttributeError as e:
            logger.error(
                f"AttributeError in game loop: {e}. This might indicate an issue with the game object's structure."
                exc_info=True
            )
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during the game loop: {e}", exc_info=True
            )
        finally:
            logger.info(
                "Game loop finished or interrupted. Processing final results..."
            )

    async def _get_orders_for_power(
        self
        game: "Game"
        power_name: str
        agent: "BaseAgent"
        game_history: "GameHistory"
    ) -> List[str]:
        current_phase_state = PhaseState.from_game(game)
        if isinstance(agent, LLMAgent):
            logger.debug(f"Using LLMAgent.decide_orders() for {power_name}")
            try:
                order_objects: List[Order] = await asyncio.wait_for(
                    agent.decide_orders(current_phase_state)
                    timeout=constants.ORDER_DECISION_TIMEOUT_SECONDS
                )
                logger.debug(
                    f"✅ {power_name} (LLMAgent): Generated {len(order_objects)} orders via decide_orders"
                )
                return [str(o) for o in order_objects]
            except asyncio.TimeoutError:
                logger.error(
                    f"❌ Timeout getting orders for {power_name} (LLMAgent) via decide_orders. Defaulting to no orders."
                )
                # Strict mode: re-raise to halt, or raise a specific error
                raise RuntimeError(f"Timeout getting orders for {power_name}")
            except (
                ValueError
            ) as ve:  # Catch specific error from LLMAgent for invalid/missing response
                logger.error(
                    f"❌ Invalid LLM response for orders for {power_name}: {ve}"
                )
                raise  # Re-raise to halt the process for this power/game
            except Exception as e:
                logger.error(
                    f"❌ Error getting orders for {power_name} (LLMAgent) via decide_orders: {e}. Defaulting to no orders."
                    exc_info=True
                )
                # Strict mode: re-raise to halt
                raise RuntimeError(
                    f"General error getting orders for {power_name}: {e}"
                ) from e
        else:
            logger.debug(
                f"Using callback get_valid_orders_func for {power_name} (agent type: {type(agent)})"
            )
            try:
                board_state = game.get_state()
                possible_orders = gather_possible_orders(game, power_name)
                mock_system_prompt = "No system prompt for non-LLMAgent"
                mock_goals: List[str] = []
                mock_relationships: Dict[str, str] = {}
                mock_private_diary = "(No diary for non-LLMAgent)"
                orders = await self.get_valid_orders_func(
                    game
                    getattr(agent, "model_id", "unknown_model")
                    getattr(agent, "system_prompt", mock_system_prompt)
                    board_state
                    power_name
                    possible_orders
                    game_history
                    getattr(agent, "goals", mock_goals)
                    getattr(agent, "relationships", mock_relationships)
                    getattr(
                        agent
                        "format_private_diary_for_prompt"
                        lambda: mock_private_diary
                    )()
                    self.config.llm_log_path
                    game.get_current_phase()
                    self.config
                )
                logger.debug(
                    f"✅ {power_name} (Callback): Generated {len(orders)} orders"
                )
                return orders
            except Exception as e:
                logger.error(
                    f"❌ Error getting orders for {power_name} via callback: {e}. Defaulting to no orders."
                    exc_info=True
                )
                raise RuntimeError(
                    f"Error in callback order generation for {power_name}: {e}"
                ) from e

    async def _process_phase_results_and_updates(
        self
        game: "Game"
        game_history: "GameHistory"
        all_orders_for_phase: Dict[str, List[str]]
        processed_phase_name: str
    ):
        logger.info(f"Processing results for phase: {processed_phase_name}")
        for power_name, orders in all_orders_for_phase.items():
            if power_name in self.active_powers:
                game.set_orders(power_name, orders)
            elif (
                not orders
                and power_name in game.powers
                and not game.powers[power_name].is_eliminated()
            ):
                # Ensure even powers with no orders (e.g. civil disorder or deliberate no moves) are processed
                game.set_orders(power_name, [])
        
        process_return_value = game.process()
        gpd_object: Optional[Any] = None # Using Any if GamePhaseData couldn't be imported
        if GamePhaseData and isinstance(process_return_value, GamePhaseData):
            gpd_object = process_return_value
            logger.debug(f"game.process() returned GamePhaseData object: {gpd_object}")
        elif process_return_value is not None:
            # If GamePhaseData is None (import failed) but we got something back
            gpd_object = process_return_value 
            logger.debug(f"game.process() returned: {type(gpd_object)} - {str(gpd_object)[:500]}. Will check its attributes if GamePhaseData type unknown.")
        else:
            logger.debug("game.process() returned None.")

        logger.info(f"Game processed. New phase: {game.get_current_phase()}")

        power_prefix_map: Dict[str, str] = {}
        if hasattr(game, "powers") and isinstance(game.powers, dict):
            try:
                power_prefix_map = {
                    p_name[:3].upper(): p_name for p_name in game.powers.keys() if len(p_name) >= 3
                }
            except Exception as e:
                logger.warning(f"Could not build power_prefix_map: {e}")

        messages_list_for_parsing: Optional[List[str]] = None
        source_for_message_parsing_str = "game.messages" # default

        # --- MODIFICATION START: Handle SortedDict for messages ---
        raw_messages_source: Optional[Any] = None
        if gpd_object and hasattr(gpd_object, 'messages'):
            raw_messages_source = getattr(gpd_object, 'messages')
            source_for_message_parsing_str = "process_return_value.messages"
        elif hasattr(game, 'messages'):
            raw_messages_source = game.messages
            source_for_message_parsing_str = "game.messages"

        if raw_messages_source is not None:
            if isinstance(raw_messages_source, list) and all(isinstance(s, str) for s in raw_messages_source):
                messages_list_for_parsing = raw_messages_source
                logger.info(f"Using '{source_for_message_parsing_str}' (List[str]) for parsing results.")
            elif hasattr(raw_messages_source, 'values') and callable(getattr(raw_messages_source, 'values')): # Check for dict-like (e.g. SortedDict)
                # Attempt to treat as a dictionary of lists of strings (like SortedDict from diplomacy lib)
                try:
                    aggregated_messages: List[str] = []
                    valid_dict_format = True
                    for item_value in raw_messages_source.values():
                        if isinstance(item_value, list) and all(isinstance(s, str) for s in item_value):
                            aggregated_messages.extend(item_value)
                        else:
                            # If any value is not a list of strings, this format is not what we expect for SortedDict of messages
                            valid_dict_format = False
                            break
                    
                    if valid_dict_format:
                        messages_list_for_parsing = aggregated_messages
                        logger.info(f"Successfully aggregated messages from '{source_for_message_parsing_str}' (dict-like values) for parsing results.")
                    else:
                        logger.warning(
                            f"'{source_for_message_parsing_str}' is dict-like, but its values are not all List[str]. "
                            f"Actual type: {type(raw_messages_source)}. Cannot use for standard message parsing."
                        )
                except Exception as e:
                    logger.warning(
                        f"Error processing '{source_for_message_parsing_str}' as a dict-like object: {e}. "
                        f"Actual type: {type(raw_messages_source)}. Cannot use for message parsing."
                    )
            else:
                logger.warning(
                    f"'{source_for_message_parsing_str}' is not a List[str] or a recognized dict-like structure of messages. "
                    f"Actual type: {type(raw_messages_source)}. Cannot use for message parsing."
                )
        # --- MODIFICATION END: Handle SortedDict for messages ---
        
        parsed_game_messages: Optional[Dict[str, List[str]]] = None

        for power_name_iter in all_orders_for_phase.keys():
            if power_name_iter in game.powers:
                try:
                    adjudicated_order_strings: List[str] = []
                    found_results = False
                    source_of_results = "Unknown"

                    # Attempt 0.1: Direct dictionary attributes from GamePhaseData object (process_return_value)
                    if gpd_object and not found_results:
                        logger.debug(f"Inspecting GamePhaseData attributes for {power_name_iter}...")
                        for attr_name in ["resolved_orders", "results", "adjudicated_orders"]:
                            if hasattr(gpd_object, attr_name):
                                potential_results_dict = getattr(gpd_object, attr_name)
                                if isinstance(potential_results_dict, dict) and power_name_iter in potential_results_dict:
                                    potential_results_list = potential_results_dict[power_name_iter]
                                    if isinstance(potential_results_list, list) and all(isinstance(s, str) for s in potential_results_list):
                                        adjudicated_order_strings = potential_results_list
                                        source_of_results = f"process_return_value.{attr_name}"
                                        found_results = True
                                        logger.info(f"Using results from {source_of_results} for {power_name_iter}")
                                        break 
                        if found_results:
                            pass # Continue to result processing for this power

                    # Attempt 0.5: game.adjudicator.resolved_orders
                    if not found_results and hasattr(game, "adjudicator") and hasattr(game.adjudicator, "resolved_orders"):
                        adj_resolved_orders = getattr(game.adjudicator, "resolved_orders")
                        if isinstance(adj_resolved_orders, dict) and power_name_iter in adj_resolved_orders:
                            potential_results = adj_resolved_orders[power_name_iter]
                            if isinstance(potential_results, list) and all(isinstance(s, str) for s in potential_results):
                                adjudicated_order_strings = potential_results
                                source_of_results = "game.adjudicator.resolved_orders"
                                found_results = True

                    # Attempt 1: game.resolved_orders
                    if not found_results and hasattr(game, "resolved_orders") and isinstance(getattr(game, "resolved_orders"), dict):
                        game_resolved_orders = getattr(game, "resolved_orders")
                        if power_name_iter in game_resolved_orders:
                            adjudicated_order_strings = game_resolved_orders[power_name_iter]
                            source_of_results = "game.resolved_orders"
                            found_results = True
                        elif hasattr(game_resolved_orders, 'keys'): # Attribute exists, power just not in it.
                            # This means game.resolved_orders is a valid source, but no results for this power.
                            # Set found_results = True so we don't fall back to N/A if this power indeed had no orders resolved here.
                            found_results = True 

                    # Attempt 2: game.adjudicated_orders
                    if not found_results and hasattr(game, "adjudicated_orders") and isinstance(getattr(game, "adjudicated_orders"), dict):
                        game_adj_orders = getattr(game, "adjudicated_orders")
                        if power_name_iter in game_adj_orders:
                            adjudicated_order_strings = game_adj_orders[power_name_iter]
                            source_of_results = "game.adjudicated_orders"
                            found_results = True
                        elif hasattr(game_adj_orders, 'keys'):
                            found_results = True

                    # Attempt 3: game.get_results_for_power
                    if not found_results and hasattr(game, "get_results_for_power") and callable(getattr(game, "get_results_for_power")):
                        results_from_method = game.get_results_for_power(power_name_iter)
                        if results_from_method is not None and isinstance(results_from_method, list) and all(isinstance(s, str) for s in results_from_method):
                            adjudicated_order_strings = results_from_method
                            source_of_results = "game.get_results_for_power()"
                            found_results = True 
                        elif results_from_method is not None: 
                             found_results = True # Method exists but returned wrong type or was empty.

                    # Attempt 4: game.results
                    if not found_results and hasattr(game, "results") and isinstance(getattr(game, "results"), dict):
                        game_results_dict = getattr(game, "results")
                        if power_name_iter in game_results_dict:
                            adjudicated_order_strings = game_results_dict[power_name_iter]
                            source_of_results = "game.results"
                            found_results = True
                        elif hasattr(game_results_dict, 'keys'):
                            found_results = True
                    
                    # Attempt 5: Message parsing (using pre-selected messages_list_for_parsing)
                    if not found_results and parsed_game_messages is None and messages_list_for_parsing is not None and power_prefix_map:
                        logger.debug(f"Attempting to parse {source_for_message_parsing_str} for results...")
                        parsed_game_messages = {} 
                        import re 
                        for msg_idx, msg_content in enumerate(messages_list_for_parsing):
                            if isinstance(msg_content, str):
                                match = re.match(r'^\\s*\\(\\(([\\w]{3})\\s+.*?\\)\\s+.*?\\)\\s*->\\s*(.*)', msg_content.strip())
                                if match:
                                    prefix = match.group(1).upper()
                                    full_message_body = match.group(0) 
                                    if prefix in power_prefix_map:
                                        mapped_power_name = power_prefix_map[prefix]
                                        if mapped_power_name not in parsed_game_messages:
                                            parsed_game_messages[mapped_power_name] = []
                                        parsed_game_messages[mapped_power_name].append(full_message_body)
                                    # No debug log here per message to avoid spam, summary log later.
                                # elif msg_idx > 0 or (msg_idx == 0 and not msg_content.lower().startswith("[messages]")): 
                                #    logger.debug(f"Message from {source_for_message_parsing_str} did not match order result pattern: {msg_content}")
                            else:
                                logger.warning(f"Item in {source_for_message_parsing_str} is not a string: {msg_content}")
                        
                        if not parsed_game_messages:
                            logger.info(f"Parsing {source_for_message_parsing_str} did not yield any structured results.")
                            # Ensure it's not None to prevent re-parsing, but an empty dict.
                            parsed_game_messages = {} 
                        else:
                            total_parsed_count = sum(len(v) for v in parsed_game_messages.values())
                            logger.info(f"Successfully parsed {total_parsed_count} messages from {source_for_message_parsing_str} into per-power results.")

                    if not found_results and parsed_game_messages is not None and power_name_iter in parsed_game_messages:
                         adjudicated_order_strings = parsed_game_messages[power_name_iter]
                         source_of_results = source_for_message_parsing_str # Use the string determined earlier
                         found_results = True 

                    order_results_for_power: List[List[str]]

                    if found_results and adjudicated_order_strings:
                        logger.info(f"Fetched {len(adjudicated_order_strings)} result(s) for {power_name_iter} from {source_of_results}.")
                        order_results_for_power = [[res_str] for res_str in adjudicated_order_strings]
                    elif found_results and not adjudicated_order_strings:
                        # This means a valid source was checked (e.g. game.resolved_orders existed, or message parsing ran)
                        # but it was empty for this specific power. This is a valid state (e.g. power had no orders).
                        logger.info(f"No result strings found for {power_name_iter} from {source_of_results} (source was valid but empty for this power, or power had no orders submitted/resolved).")
                        order_results_for_power = []
                    else:
                        # --- MODIFICATION START: Change fallback to error ---
                        # This means no valid source was identified AT ALL for this power after all checks.
                        error_message = f"CRITICAL: Could not find adjudicated results for {power_name_iter} via any known method in phase {processed_phase_name}."
                        logger.error(error_message)
                        logger.debug(f"All orders submitted for phase by all powers: {all_orders_for_phase}")
                        logger.debug(f"Game object state (current_phase): {game.get_current_phase()}")
                        logger.debug(f"Game object state (messages): {getattr(game, 'messages', 'N/A')}")
                        logger.debug(f"Game object state (resolved_orders): {getattr(game, 'resolved_orders', 'N/A')}")
                        logger.debug(f"Game object state (adjudicated_orders): {getattr(game, 'adjudicated_orders', 'N/A')}")
                        logger.debug(f"Game object state (results): {getattr(game, 'results', 'N/A')}")
                        if gpd_object:
                             logger.debug(f"GPD object attributes: {dir(gpd_object)}")
                             logger.debug(f"GPD object messages: {getattr(gpd_object, 'messages', 'N/A')}")
                             logger.debug(f"GPD object resolved_orders: {getattr(gpd_object, 'resolved_orders', 'N/A')}")
                        raise ValueError(error_message)
                        # --- MODIFICATION END: Change fallback to error ---

                except Exception as e:
                    logger.error(f"Error fetching or processing results for {power_name_iter}: {e}", exc_info=True)
                    power_orders_submitted = all_orders_for_phase.get(power_name_iter, [])
                    order_results_for_power = [["Error fetching result"] for _ in power_orders_submitted] if power_orders_submitted else []
                
                if order_results_for_power:
                    game_history.add_results(
                        processed_phase_name, power_name_iter, order_results_for_power
                    )
                else:
                    logger.debug(f"No results or N/A placeholders to add to history for {power_name_iter} in phase {processed_phase_name} (source {source_of_results}).")

        phase_events_summary_text = f"Summary of events for {processed_phase_name}: All orders processed. New SCs: {game.get_state().get('centers', {})}"
        for power_name in self.active_powers:
            agent = self.agent_manager.get_agent(power_name)
            if agent:
                logger.debug(f"Generating phase summary for {power_name}...")
                try:
                    # Create a simple PhaseState for the update method
                    current_phase_state = PhaseState.from_game(
                        game
                    )  # Assuming PhaseState is imported
                    # Pass an empty list for events for now, as phase_events_summary_text is not a structured list of events
                    await agent.update_state(current_phase_state, [])
                except AttributeError as ae:
                    logger.error(
                        f"❌ AttributeError during state update for {power_name} (likely an issue with game/agent state access): {ae}"
                        exc_info=True
                    )
                except Exception as e:
                    logger.error(
                        f"❌ Error during phase summary processing for {power_name}: {e}"
                        exc_info=e
                    )
        current_phase = game.get_current_phase()
        current_year = extract_year_from_phase(current_phase)
        if current_year is not None and current_year > 1902:
            year_to_consolidate = str(current_year - 2)
            logger.info(
                f"Checking for diary consolidation for year {year_to_consolidate}."
            )
            for power_name in self.active_powers:
                agent = self.agent_manager.get_agent(power_name)
                if agent:
                    logger.debug(
                        f"Consolidating diary for {power_name} (year {year_to_consolidate})..."
                    )
                    try:
                        await agent.consolidate_year_diary_entries(
                            year_to_consolidate, game, self.config.llm_log_path
                        )
                        logger.debug(f"✅ {power_name}: Consolidated diary entries")
                    except Exception as e:
                        logger.error(
                            f"❌ Error consolidating diary for {power_name}: {e}"
                            exc_info=e
                        )
