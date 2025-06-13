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
from .. import constants  # Import constants

from ai_diplomacy.domain import game_to_phase, PhaseState, Order

# Relative imports will need to be adjusted based on the new location
from ..agents.base import BaseAgent  # Corrected: Order and Message removed
from ..services.config import GameConfig  # Adjusted import
from ..utils.phase_parsing import (
    get_phase_type_from_game,
    PhaseType,
)  # Adjusted import

# Import actual strategy classes
from .movement import MovementPhaseStrategy, execute_movement_phase
from .retreat import RetreatPhaseStrategy
from .build import BuildPhaseStrategy
from .result_parser import GameResultParser
from .negotiation import conduct_negotiations

try:
    from diplomacy.utils.game_phase_data import GamePhaseData
except ImportError:
    GamePhaseData = None  # type: ignore
    logging.getLogger(__name__).info(
        "Could not import GamePhaseData from diplomacy.utils.game_phase_data. Will rely on hasattr checks."
    )


# Protocol for PhaseStrategy
class PhaseStrategy(Protocol):
    async def get_orders(
        self,
        game: "Game",
        phase: "PhaseState",
        orchestrator: "PhaseOrchestrator",
        game_history: "GameHistory",
    ) -> Dict[str, List[str]]: ...


if TYPE_CHECKING:
    from diplomacy import Game
    from ..game_history import GameHistory  # Adjusted import
    from ..agents.base import BaseAgent  # Corrected: Order and Message removed
    from ..services.config import GameConfig  # Adjusted import

"""
Orchestrates the main game loop and phase transitions in a Diplomacy game.

This module defines the PhaseOrchestrator class, which is responsible for
managing the overall game flow. It coordinates agent actions, negotiations,
order submissions, and game state processing across different game phases
(Movement, Retreat, Build). It utilizes specific strategy classes for each
phase type.
"""

logger = logging.getLogger(__name__)

__all__ = ["PhaseOrchestrator", "PhaseStrategy"]  # Added PhaseStrategy Protocol

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


class PhaseOrchestrator:  # Renamed from GamePhaseOrchestrator
    # Class docstring already exists and is good.

    def __init__(self, game_config: "GameConfig", get_valid_orders_func: GetValidOrdersFuncType):
        self.game_config = game_config
        self.get_valid_orders_func = get_valid_orders_func
        self.active_powers: List[str] = []
        self.result_parser = GameResultParser()
        self.phase_counter = 0

        if self.game_config.powers_and_models:
            self.active_powers = list(self.game_config.powers_and_models.keys())
        else:
            logger.warning(
                "GameConfig.powers_and_models not set when PhaseOrchestrator is initialized. Active powers list will be empty initially."
            )

        self._phase_map: Dict[PhaseType, PhaseStrategy] = {  # Ensure correct type hint for _phase_map
            PhaseType.MVT: MovementPhaseStrategy(),
            PhaseType.RET: RetreatPhaseStrategy(),
            PhaseType.BLD: BuildPhaseStrategy(),
        }

        logger.info("PhaseOrchestrator initialized.")

    async def run_game_loop(self, game: "GameState", game_history: "GameHistory"):
        logger.info(f"Starting game loop for game ID: {self.game_config.game_id}")
        self.game_config.game_instance = game

        try:
            while True:
                if self.game_config.max_phases and self.phase_counter >= self.game_config.max_phases:
                    logger.info(f"Reached max_phases {self.game_config.max_phases}. Ending game.")
                    break
                
                phase = game_to_phase(game)
                current_phase_val = phase.name
                current_year = phase.key.year

                if (
                    self.game_config.max_years
                    and current_year is not None
                    and current_year >= self.game_config.max_years
                ):
                    logger.info(f"Reached max_year {self.game_config.max_years}. Ending game.")
                    try:
                        game.draw()
                        logger.info("Game marked as completed via draw.")
                    except Exception as e:
                        logger.warning(f"Could not call game.draw(): {e}. Setting status manually.")
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
                    if p in self.game_config.powers_and_models and not game.powers[p].is_eliminated()
                ]
                if not self.active_powers:
                    logger.info("No active LLM-controlled powers remaining. Ending game.")
                    break
                logger.info(f"Active LLM-controlled powers for this phase: {self.active_powers}")

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
                    all_orders_for_phase = await strategy.get_orders(game, phase, self, game_history)
                    # ---- MODIFICATION START: Set orders and process ----
                    logger.info("Submitting all collected orders to the game engine.")
                    for power_name, orders in all_orders_for_phase.items():
                        if power_name in game.powers and not game.powers[power_name].is_eliminated():
                            game.set_orders(power_name, orders)
                            logger.debug(f"Orders set for {power_name}: {orders}")
                        else:
                            logger.warning(
                                f"Power {power_name} from order list not in active game powers. Orders not set."
                            )

                    logger.info("Processing game state with submitted orders...")
                    game.process()
                    logger.info(f"Game processed. New phase: {game.get_current_phase()}")
                    # ---- MODIFICATION END: Set orders and process ----

                elif phase_type_val_str == constants.PHASE_TYPE_PROCESS_ONLY:
                    current_phase_str = game.get_current_phase()
                    logger.info(f"Phase is '{current_phase_str}', processing to next phase.")
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

                self.phase_counter += 1
                
                phase = game_to_phase(game)
                current_year = phase.key.year
                current_phase_val = phase.name
                
                if (
                    self.game_config.max_years
                    and current_year is not None
                    and current_year >= self.game_config.max_years
                ):
                    current_phase_type_val = get_phase_type_from_game(game)
                    if (
                        current_phase_type_val == PhaseType.BLD.value
                        and constants.PHASE_STRING_WINTER in current_phase_val.upper()
                    ) or (constants.PHASE_STRING_WINTER in current_phase_val.upper() and game.is_game_done):
                        logger.info(
                            f"Reached max_years ({self.game_config.max_years}). Ending game after {current_phase_val}."
                        )
                        try:
                            game.draw()
                            logger.info("Game marked as completed via draw.")
                        except Exception as e:
                            logger.warning(f"Could not call game.draw(): {e}. Setting status manually.")
                            if hasattr(game, "set_status"):
                                game.set_status(constants.GAME_STATUS_COMPLETED)
                            if hasattr(game, "phase"):
                                game.phase = constants.GAME_STATUS_COMPLETED
                        break
            logger.info(f"Game {self.game_config.game_id} finished. Final phase: {game.get_current_phase()}")
        except AttributeError as e:
            logger.error(
                f"AttributeError in game loop: {e}. This might indicate an issue with the game object's structure.",
                exc_info=True,
            )
        except Exception as e:
            logger.error(f"An unexpected error occurred during the game loop: {e}", exc_info=True)
        finally:
            logger.info("Game loop finished or interrupted. Processing final results...")

    async def _get_orders_for_power(
        self,
        game: "Game",
        power_name: str,
        agent: "BaseAgent",
        game_history: "GameHistory",  # may not be needed here anymore
    ) -> List[str]:
        """Gets orders for a single power from its assigned agent."""
        phase = game_to_phase(game)
        try:
            logger.debug(f"Calling agent.decide_orders() for {power_name} (type: {type(agent).__name__})")
            order_objects: List[Order] = await asyncio.wait_for(
                agent.decide_orders(phase),
                timeout=constants.ORDER_DECISION_TIMEOUT_SECONDS,
            )
            logger.debug(f"✅ {power_name}: Generated {len(order_objects)} orders")
            return [str(o.value) for o in order_objects]
        except asyncio.TimeoutError:
            logger.error(f"❌ Timeout getting orders for {power_name}.")
            raise RuntimeError(f"Timeout getting orders for {power_name}")
        except Exception as e:
            logger.error(f"❌ Error getting orders for {power_name}: {e}", exc_info=True)
            raise RuntimeError(f"Error getting orders for {power_name}: {e}") from e

    async def _process_phase_results_and_updates(
        self,
        game: "Game",
        game_history: "GameHistory",
        all_orders_for_phase: Dict[str, List[str]],
        processed_phase_name: str,
    ):
        """Processes and logs the results of a game phase."""
        phase = game_to_phase(game)
        logger.info(f"Processing results for phase: {processed_phase_name}")

        # Log results using GameResultParser
        phase_results = self.result_parser.parse(game, processed_phase_name)
        game_history.add_phase_results(processed_phase_name, phase_results)
        logger.info(f"Phase results for {processed_phase_name} logged.")

        # Update agents with the new state
        update_tasks = [
            agent.update_state(phase, phase_results.get(power, []))
            for power, agent in self.agent_manager.get_agents_for_powers(self.active_powers).items()
        ]
        if update_tasks:
            await asyncio.gather(*update_tasks)
            logger.info("All agents have been updated with the new phase state.")
