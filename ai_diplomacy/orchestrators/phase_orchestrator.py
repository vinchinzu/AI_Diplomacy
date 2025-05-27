import logging
import asyncio
from typing import Optional, List, Dict, Callable, Coroutine, TYPE_CHECKING, Any, Protocol
from diplomacy import Game
# Relative imports will need to be adjusted based on the new location
from ..utils import gather_possible_orders # Adjusted import
from ..agents.llm_agent import LLMAgent # Adjusted import
from ..core.state import PhaseState # Adjusted import
from ..agents.base import BaseAgent, Order, Message # Adjusted import
from ..services.config import GameConfig # Adjusted import
from ..utils.phase_parsing import get_phase_type_from_game, _extract_year_from_phase, PhaseType # Adjusted import

# Import actual strategy classes
from .movement import MovementPhaseStrategy
from .retreat import RetreatPhaseStrategy
from .build import BuildPhaseStrategy

# Protocol for PhaseStrategy
class PhaseStrategy(Protocol):
    async def get_orders(
        self, game: "Game", orchestrator: "PhaseOrchestrator", game_history: "GameHistory"
    ) -> Dict[str, List[str]]: ...

if TYPE_CHECKING:
    from diplomacy import Game
    from ..agent_manager import AgentManager # Adjusted import
    from ..game_history import GameHistory # Adjusted import
    from ..agents.base import BaseAgent, Message # Adjusted import
    from ..services.config import GameConfig # Adjusted import

logger = logging.getLogger(__name__)

GetValidOrdersFuncType = Callable[
    [
        "Game",
        str,
        str,
        Any,
        str,
        Dict[str, List[str]],
        "GameHistory",
        str,
        "GameConfig",
        Optional[List[str]],
        Optional[Dict[str, str]],
        Optional[str],
        str,
        str,
    ],
    Coroutine[Any, Any, List[str]],
]

class PhaseOrchestrator: # Renamed from GamePhaseOrchestrator
    """
    Orchestrates the main game loop, including phase transitions, agent actions,
    negotiations, order submissions, and game processing.
    """
    def __init__(
        self,
        game_config: "GameConfig",
        agent_manager: "AgentManager",
        get_valid_orders_func: GetValidOrdersFuncType, # This might be removed if all agents use the new API
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
        
        self._phase_map: Dict[PhaseType, PhaseStrategy] = { # Ensure correct type hint for _phase_map
            PhaseType.MVT: MovementPhaseStrategy(),
            PhaseType.RET: RetreatPhaseStrategy(),
            PhaseType.BLD: BuildPhaseStrategy(),
        }

    async def run_game_loop(self, game: "Game", game_history: "GameHistory"):
        logger.info(f"Starting game loop for game ID: {self.config.game_id}")
        self.config.game_instance = game

        try:
            while True:
                current_phase_val = getattr(game, "phase", "Unknown")
                current_year = getattr(game, "year", None)
                if current_year is None:
                    current_year = _extract_year_from_phase(current_phase_val)

                if (
                    self.config.max_years
                    and current_year is not None
                    and current_year >= self.config.max_years
                ):
                    logger.info(f"Reached max_year {self.config.max_years}. Ending game.")
                    try:
                        game.draw()
                        logger.info("Game marked as completed via draw.")
                    except Exception as e:
                        logger.warning(f"Could not call game.draw(): {e}. Setting status manually.")
                        if hasattr(game, "set_status"): game.set_status("COMPLETED")
                        if hasattr(game, "phase"): game.phase = "COMPLETED"
                    break

                if game.is_game_done:
                    logger.info("Game is done. Exiting game loop.")
                    break

                logger.info(f"--- Current Phase: {current_phase_val} ---")
                game_history.add_phase(current_phase_val)

                self.active_powers = [
                    p for p in game.powers 
                    if p in self.config.powers_and_models and not game.powers[p].is_eliminated()
                ]
                if not self.active_powers:
                    logger.info("No active LLM-controlled powers remaining. Ending game.")
                    break
                logger.info(f"Active LLM-controlled powers for this phase: {self.active_powers}")

                all_orders_for_phase: Dict[str, List[str]] = {}
                phase_type_val_str = get_phase_type_from_game(game)
                
                strategy: Optional[PhaseStrategy] = None
                if phase_type_val_str != '-':
                    try:
                        phase_type_enum_val = PhaseType(phase_type_val_str)
                        strategy = self._phase_map.get(phase_type_enum_val)
                    except ValueError:
                        logger.error(f"Invalid phase type string from get_phase_type_from_game: {phase_type_val_str}")
                        # Decide how to handle: skip, error, default? For now, process to next.
                        game.process()
                        continue
                
                if strategy:
                    all_orders_for_phase = await strategy.get_orders(game, self, game_history)
                elif phase_type_val_str == "-":
                    current_phase_str = game.get_current_phase()
                    logger.info(f"Phase is '{current_phase_str}', processing to next phase.")
                    game.process()
                    continue
                else: 
                    logger.error(f"No strategy found for phase type value: {phase_type_val_str} from phase {current_phase_val}. Attempting to process.")
                    game.process() 
                    continue
                
                await self._process_phase_results_and_updates(
                    game, game_history, all_orders_for_phase, current_phase_val
                )

                current_year = getattr(game, "year", None)
                if current_year is None:
                    current_year = _extract_year_from_phase(current_phase_val)
                if (
                    self.config.max_years
                    and current_year is not None
                    and current_year >= self.config.max_years
                ):
                    current_phase_type_val = get_phase_type_from_game(game)
                    if (current_phase_type_val == PhaseType.BLD.value and "WINTER" in current_phase_val.upper()) \
                         or ("WINTER" in current_phase_val.upper() and game.is_game_done):
                        logger.info(f"Reached max_years ({self.config.max_years}). Ending game after {current_phase_val}.")
                        try:
                            game.draw()
                            logger.info("Game marked as completed via draw.")
                        except Exception as e:
                            logger.warning(f"Could not call game.draw(): {e}. Setting status manually.")
                            if hasattr(game, "set_status"): game.set_status("COMPLETED")
                            if hasattr(game, "phase"): game.phase = "COMPLETED"
                        break
            logger.info(f"Game {self.config.game_id} finished. Final phase: {game.get_current_phase()}")
        except AttributeError as e:
            logger.error(f"AttributeError in game loop: {e}. This might indicate an issue with the game object's structure.", exc_info=True)
        except Exception as e:
            logger.error(f"An unexpected error occurred during the game loop: {e}", exc_info=True)
        finally:
            logger.info("Game loop finished or interrupted. Processing final results...")

    async def _get_orders_for_power(self, game: "Game", power_name: str, agent: "BaseAgent", game_history: "GameHistory") -> List[str]:
        current_phase_state = PhaseState.from_game(game)
        if isinstance(agent, LLMAgent):
            logger.debug(f"Using LLMAgent.decide_orders() for {power_name}")
            try:
                order_objects: List[Order] = await asyncio.wait_for(agent.decide_orders(current_phase_state), timeout=180.0)
                logger.debug(f"✅ {power_name} (LLMAgent): Generated {len(order_objects)} orders via decide_orders")
                return [str(o) for o in order_objects]
            except asyncio.TimeoutError:
                logger.error(f"❌ Timeout getting orders for {power_name} (LLMAgent) via decide_orders. Defaulting to no orders.")
                return []
            except Exception as e:
                logger.error(f"❌ Error getting orders for {power_name} (LLMAgent) via decide_orders: {e}. Defaulting to no orders.", exc_info=True)
                return []
        else:
            logger.debug(f"Using callback get_valid_orders_func for {power_name} (agent type: {type(agent)})")
            try:
                board_state = game.get_state()
                possible_orders = gather_possible_orders(game, power_name)
                mock_system_prompt = "No system prompt for non-LLMAgent"
                mock_goals: List[str] = []
                mock_relationships: Dict[str, str] = {}
                mock_private_diary = "(No diary for non-LLMAgent)"
                orders = await self.get_valid_orders_func(
                    game, getattr(agent, "model_id", "unknown_model"), getattr(agent, "system_prompt", mock_system_prompt),
                    board_state, power_name, possible_orders, game_history, getattr(agent, "goals", mock_goals),
                    getattr(agent, "relationships", mock_relationships), getattr(agent, "format_private_diary_for_prompt", lambda: mock_private_diary)(),
                    self.config.llm_log_path, game.get_current_phase(), self.config)
                logger.debug(f"✅ {power_name} (Callback): Generated {len(orders)} orders")
                return orders
            except Exception as e:
                logger.error(f"❌ Error getting orders for {power_name} via callback: {e}. Defaulting to no orders.", exc_info=True)
                return []

    async def _process_phase_results_and_updates(self, game: "Game", game_history: "GameHistory", all_orders_for_phase: Dict[str, List[str]], processed_phase_name: str):
        logger.info(f"Processing results for phase: {processed_phase_name}")
        for power_name, orders in all_orders_for_phase.items():
            if power_name in self.active_powers:
                game.set_orders(power_name, orders)
            elif not orders and power_name in game.powers and not game.powers[power_name].is_eliminated():
                game.set_orders(power_name, [])
        game.process()
        logger.info(f"Game processed. New phase: {game.get_current_phase()}")
        for power_name_iter, power_orders_submitted in all_orders_for_phase.items():
            if power_name_iter in game.powers:
                order_results_for_power = []
                for order_str in power_orders_submitted:
                    try:
                        results_for_order = ["Result N/A"] 
                    except Exception:
                        results_for_order = ["Error fetching result"]
                    order_results_for_power.append(results_for_order)
                game_history.add_results(processed_phase_name, power_name_iter, order_results_for_power)
        phase_events_summary_text = f"Summary of events for {processed_phase_name}: All orders processed. New SCs: {game.get_state().get('centers', {})}" # Added .get for safety
        for power_name in self.active_powers:
            agent = self.agent_manager.get_agent(power_name)
            if agent:
                logger.debug(f"Generating phase summary for {power_name}...")
                try:
                    logger.debug(f"✅ {power_name}: Phase summary processing placeholder (actual call handled by agent.update_state or internally)")
                except Exception as e:
                    logger.error(f"❌ Error during phase summary processing for {power_name}: {e}", exc_info=e)
        for power_name in self.active_powers:
            agent = self.agent_manager.get_agent(power_name)
            if agent and isinstance(agent, LLMAgent):
                logger.debug(f"Updating state for {power_name}...")
                try:
                    current_phase_state = PhaseState.from_game(game)
                    await agent.update_state(current_phase_state, phase_events_summary_text)
                except Exception as e:
                    logger.error(f"❌ Error updating state for {power_name}: {e}", exc_info=True)
            elif agent:
                logger.debug(f"Skipping state update for non-LLMAgent {power_name}")
        current_phase = game.get_current_phase()
        current_year = _extract_year_from_phase(current_phase)
        if current_year is not None and current_year > 1902:
            year_to_consolidate = str(current_year - 2)
            logger.info(f"Checking for diary consolidation for year {year_to_consolidate}.")
            for power_name in self.active_powers:
                agent = self.agent_manager.get_agent(power_name)
                if agent:
                    logger.debug(f"Consolidating diary for {power_name} (year {year_to_consolidate})...")
                    try:
                        await agent.consolidate_year_diary_entries(year_to_consolidate, game, self.config.llm_log_path)
                        logger.debug(f"✅ {power_name}: Consolidated diary entries")
                    except Exception as e:
                        logger.error(f"❌ Error consolidating diary for {power_name}: {e}", exc_info=e) 