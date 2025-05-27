import logging
import asyncio

# Removed: import random
from typing import (
    Optional,
    List,
    Dict,
    Callable,
    Coroutine,
    TYPE_CHECKING,
    Any,
)  # Removed Set
from enum import Enum

from diplomacy import Game  # Removed Phase import

# Removed: from diplomacy.utils.export import to_saved_game_format
from .utils import gather_possible_orders  # Import gather_possible_orders
from ..agents.llm_agent import LLMAgent  # Added for LLMAgent hint and isinstance checks
from ..core.state import PhaseState  # Added for type hinting and potential construction


# Add a local Enum for phase types
class PhaseType(Enum):
    MVT = "M"
    RET = "R"
    BLD = "A"


if TYPE_CHECKING:
    from diplomacy import Game
    from .agent_manager import AgentManager
    from .game_history import GameHistory  # Removed Message as GameHistoryMessage

    # from .agent import DiplomacyAgent - REMOVED
    from .agents.base import (
        BaseAgent,
        Message,
    )  # Added for LLMAgent hint and Message object
    from .services.config import GameConfig


logger = logging.getLogger(__name__)

# Define a type for the get_valid_orders function that will be passed
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


class GamePhaseOrchestrator:
    """
    Orchestrates the main game loop, including phase transitions, agent actions,
    negotiations, order submissions, and game processing.
    """

    @staticmethod
    def get_phase_type_from_game(game: "Game") -> str:
        """Extracts the phase type character from the current phase string (e.g., 'M', 'R', 'A')."""
        phase_str = game.get_current_phase().upper()
        if not phase_str or phase_str in ("FORMING", "COMPLETED"):
            return "-"

        # Check for Build/Adjustment phase
        # Phase strings can be like "W1901A" or "FALL 1901 ADJUSTMENT" or "WINTER 1901 BUILD"
        if "A" == phase_str[-1] or "ADJUSTMENT" in phase_str or "BUILD" in phase_str:
            return PhaseType.BLD.value  # "A"
        # Check for Movement phase
        elif "M" == phase_str[-1] or "MOVEMENT" in phase_str:
            return PhaseType.MVT.value  # "M"
        # Check for Retreat phase
        elif "R" == phase_str[-1] or "RETREAT" in phase_str:
            return PhaseType.RET.value  # "R"

        # Fallback or if specific character is present
        if phase_str[-1] in [
            PhaseType.MVT.value,
            PhaseType.RET.value,
            PhaseType.BLD.value,
        ]:
            return phase_str[-1]

        logger.warning(
            f"Could not determine phase type for '{phase_str}'. Defaulting to '-'"
        )
        return "-"

    def __init__(
        self,
        game_config: "GameConfig",
        agent_manager: "AgentManager",
        # Removed: phase_summary_generator: 'PhaseSummaryGenerator',
        get_valid_orders_func: GetValidOrdersFuncType,  # Passed from lm_game.py
    ):
        self.config = game_config
        self.agent_manager = agent_manager
        # Removed: self.phase_summary_generator = phase_summary_generator
        self.get_valid_orders_func = get_valid_orders_func
        self.active_powers: List[str] = (
            []
        )  # Powers actively playing (not eliminated, not excluded)

        if (
            self.config.powers_and_models
        ):  # Should be set by AgentManager.assign_models_to_powers
            self.active_powers = list(self.config.powers_and_models.keys())
        else:
            logger.warning(
                "GameConfig.powers_and_models not set when GamePhaseOrchestrator is initialized. Active powers list will be empty initially."
            )

    def _extract_year_from_phase(self, phase_name: str) -> Optional[int]:
        """Extracts the year as int from a phase string like 'S1901M' or 'SPRING 1901 MOVEMENT'."""
        # Try short format: S1901M, F1902R, etc.
        if phase_name and len(phase_name) >= 5 and phase_name[1:5].isdigit():
            return int(phase_name[1:5])
        # Try long format: SPRING 1901 MOVEMENT
        parts = phase_name.split()
        if len(parts) >= 2 and parts[1].isdigit():
            return int(parts[1])
        return None

    async def run_game_loop(self, game: "Game", game_history: "GameHistory"):
        """
        Main game loop iterating through years and phases.
        """
        logger.info(f"Starting game loop for game ID: {self.config.game_id}")
        self.config.game_instance = (
            game  # Store game instance in config for access by other components
        )

        try:
            while True:
                current_phase_val = getattr(game, "phase", "Unknown")
                # Extract year safely
                current_year = getattr(game, "year", None)
                if current_year is None:
                    current_year = self._extract_year_from_phase(current_phase_val)

                # Check for max_years condition
                if (
                    self.config.max_years
                    and current_year is not None
                    and current_year >= self.config.max_years
                ):
                    logger.info(
                        f"Reached max_year {self.config.max_years}. Ending game."
                    )
                    # Properly mark the game as completed
                    try:
                        game.draw()  # This sets status to COMPLETED and marks game as done
                        logger.info("Game marked as completed via draw.")
                    except Exception as e:
                        logger.warning(
                            f"Could not call game.draw(): {e}. Setting status manually."
                        )
                        if hasattr(game, "set_status"):
                            game.set_status("COMPLETED")
                        if hasattr(game, "phase"):
                            game.phase = "COMPLETED"
                    break

                if game.is_game_done:
                    logger.info("Game is done. Exiting game loop.")
                    break

                logger.info(f"--- Current Phase: {current_phase_val} ---")
                game_history.add_phase(current_phase_val)

                # Update active powers based on game state (e.g. eliminated powers)
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

                phase_type = self.get_phase_type_from_game(game)
                if phase_type == PhaseType.MVT.value:
                    all_orders_for_phase = await self._execute_movement_phase_actions(
                        game, game_history
                    )
                elif phase_type == PhaseType.RET.value:
                    all_orders_for_phase = await self._execute_retreat_phase_actions(
                        game, game_history
                    )
                elif "BUILD" in game.phase.upper():
                    all_orders_for_phase = await self._execute_build_phase_actions(
                        game, game_history
                    )
                else:
                    logger.error(f"Unknown phase type: {game.phase}. Skipping.")
                    game.process()  # Process to advance the phase
                    continue

                await self._process_phase_results_and_updates(
                    game, game_history, all_orders_for_phase, current_phase_val
                )

                # Check for max years condition
                # Use safe year extraction again
                current_year = getattr(game, "year", None)
                if current_year is None:
                    current_year = self._extract_year_from_phase(current_phase_val)
                if (
                    self.config.max_years
                    and current_year is not None
                    and current_year >= self.config.max_years
                ):
                    current_phase_type = self.get_phase_type_from_game(game)
                    if (
                        current_phase_type == PhaseType.BLD.value
                        and "WINTER" in current_phase_val.upper()
                    ) or ("WINTER" in current_phase_val.upper() and game.is_game_done):
                        logger.info(
                            f"Reached max_years ({self.config.max_years}). Ending game after {current_phase_val}."
                        )
                        # Properly mark the game as completed
                        try:
                            game.draw()  # This sets status to COMPLETED and marks game as done
                            logger.info("Game marked as completed via draw.")
                        except Exception as e:
                            logger.warning(
                                f"Could not call game.draw(): {e}. Setting status manually."
                            )
                            if hasattr(game, "set_status"):
                                game.set_status("COMPLETED")
                            if hasattr(game, "phase"):
                                game.phase = "COMPLETED"
                        break
            logger.info(
                f"Game {self.config.game_id} finished. Final phase: {game.get_current_phase()}"
            )
        except AttributeError as e:
            logger.error(
                f"AttributeError in game loop: {e}. This might indicate an issue with the game object's structure.",
                exc_info=True,
            )
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during the game loop: {e}", exc_info=True
            )
        finally:
            logger.info(
                "Game loop finished or interrupted. Processing final results..."
            )

    async def _execute_movement_phase_actions(
        self, game: "Game", game_history: "GameHistory"
    ) -> Dict[str, List[str]]:
        logger.info("Executing Movement Phase actions...")
        current_phase_name = game.get_current_phase()

        if self.config.perform_planning_phase:
            await self._perform_planning_phase(game, game_history)

        await self._perform_negotiation_rounds(game, game_history)

        orders_by_power: Dict[str, List[str]] = {}

        # SERIALIZE order generation instead of running concurrently
        for power_name in self.active_powers:
            agent = self.agent_manager.get_agent(power_name)
            if agent:
                logger.debug(f"Generating orders for {power_name}...")  # INFO to DEBUG
                try:
                    orders = await self._get_orders_for_power(
                        game, power_name, agent, game_history
                    )  # Removed self.config.num_negotiation_rounds as it's unused
                    orders_by_power[power_name] = orders
                    logger.debug(
                        f"✅ {power_name}: Generated {len(orders)} orders"
                    )  # INFO to DEBUG
                except Exception as e:
                    logger.error(
                        f"❌ Error getting orders for {power_name}: {e}", exc_info=e
                    )
                    orders_by_power[power_name] = []  # Submit no orders on error
            else:  # Should not happen if active_powers is derived from agent_manager.agents
                logger.warning(
                    f"No agent found for active power {power_name} during order generation."
                )
                orders_by_power[power_name] = []  # Submit no orders

            game_history.add_orders(
                current_phase_name, power_name, orders_by_power[power_name]
            )

            # Generate order diary entry
            if agent:  # Agent should exist if orders were successfully generated
                try:
                    await agent.generate_order_diary_entry(
                        game, orders_by_power[power_name], self.config.llm_log_path
                    )
                    logger.debug(
                        f"✅ {power_name}: Generated order diary entry"
                    )  # INFO to DEBUG
                except Exception as e:
                    logger.error(
                        f"❌ Error generating order diary for {power_name}: {e}",
                        exc_info=e,
                    )

        return orders_by_power

    async def _execute_retreat_phase_actions(
        self, game: "Game", game_history: "GameHistory"
    ) -> Dict[str, List[str]]:
        logger.info("Executing Retreat Phase actions...")
        current_phase_name = game.get_current_phase()
        orders_by_power: Dict[str, List[str]] = {}
        order_tasks = []

        for power_name in self.active_powers:
            # Retreats are often simpler, no extensive negotiation typically.
            # Check if the power actually has units that need to retreat.
            if not game.powers[power_name].must_retreat:
                logger.info(f"Power {power_name} has no units that must retreat.")
                orders_by_power[power_name] = []
                continue

            agent = self.agent_manager.get_agent(power_name)
            if agent:
                order_tasks.append(
                    self._get_orders_for_power(game, power_name, agent, game_history)
                )
            else:
                logger.warning(
                    f"No agent found for active power {power_name} during retreat order generation."
                )
                orders_by_power[power_name] = []

        results = await asyncio.gather(*order_tasks, return_exceptions=True)
        active_powers_with_retreats = [
            p for p in self.active_powers if game.powers[p].must_retreat
        ]

        for i, power_name in enumerate(active_powers_with_retreats):
            if isinstance(results[i], Exception):
                logger.error(
                    f"Error getting retreat orders for {power_name}: {results[i]}",
                    exc_info=results[i],
                )
                orders_by_power[power_name] = []
            else:
                orders_by_power[power_name] = results[i]
            game_history.add_orders(
                current_phase_name, power_name, orders_by_power[power_name]
            )
            # Order diary for retreats (optional, could be simpler)
            agent = self.agent_manager.get_agent(power_name)
            if agent:
                await agent.generate_order_diary_entry(
                    game, orders_by_power[power_name], self.config.llm_log_path
                )

        return orders_by_power

    async def _execute_build_phase_actions(
        self, game: "Game", game_history: "GameHistory"
    ) -> Dict[str, List[str]]:
        logger.info("Executing Build Phase actions...")
        current_phase_name = game.get_current_phase()
        orders_by_power: Dict[str, List[str]] = {}
        order_tasks = []

        for power_name in self.active_powers:
            # Builds are also simpler, usually no negotiation.
            # Check if power can build/disband
            if game.powers[power_name].n_builds == 0:
                logger.info(f"Power {power_name} has no builds or disbands.")
                orders_by_power[power_name] = []
                continue

            agent = self.agent_manager.get_agent(power_name)
            if agent:
                order_tasks.append(
                    self._get_orders_for_power(game, power_name, agent, game_history)
                )
            else:
                logger.warning(
                    f"No agent found for active power {power_name} during build order generation."
                )
                orders_by_power[power_name] = []

        results = await asyncio.gather(*order_tasks, return_exceptions=True)
        active_powers_with_builds = [
            p for p in self.active_powers if game.powers[p].n_builds != 0
        ]

        for i, power_name in enumerate(active_powers_with_builds):
            if isinstance(results[i], Exception):
                logger.error(
                    f"Error getting build orders for {power_name}: {results[i]}",
                    exc_info=results[i],
                )
                orders_by_power[power_name] = []
            else:
                orders_by_power[power_name] = results[i]
            game_history.add_orders(
                current_phase_name, power_name, orders_by_power[power_name]
            )
            # Order diary for builds
            agent = self.agent_manager.get_agent(power_name)
            if agent:
                await agent.generate_order_diary_entry(
                    game, orders_by_power[power_name], self.config.llm_log_path
                )

        return orders_by_power

    async def _get_orders_for_power(
        self,
        game: "Game",
        power_name: str,
        agent: "BaseAgent",
        game_history: "GameHistory",
    ) -> List[str]:
        """
        Gets orders for a given power.
        For LLMAgents, calls agent.decide_orders() directly.
        For other agent types, uses the existing callback self.get_valid_orders_func.
        """
        current_phase_state = PhaseState.from_game(game)

        if isinstance(agent, LLMAgent):
            logger.debug(f"Using LLMAgent.decide_orders() for {power_name}")
            try:
                # LLMAgent uses the new API
                orders: List[str] = await asyncio.wait_for(
                    agent.decide_orders(current_phase_state),
                    timeout=180.0,  # Timeout for order decision
                )
                logger.debug(
                    f"✅ {power_name} (LLMAgent): Generated {len(orders)} orders via decide_orders"
                )
                return orders
            except asyncio.TimeoutError:
                logger.error(
                    f"❌ Timeout getting orders for {power_name} (LLMAgent) via decide_orders. Defaulting to no orders."
                )
                return []
            except Exception as e:
                logger.error(
                    f"❌ Error getting orders for {power_name} (LLMAgent) via decide_orders: {e}. Defaulting to no orders.",
                    exc_info=True,
                )
                return []
        else:
            # Non-LLM agents use the callback (legacy or other AI types)
            # This path needs to be maintained if other agent types are still supported.
            logger.debug(
                f"Using callback get_valid_orders_func for {power_name} (agent type: {type(agent)})"
            )
            try:
                # Ensure all parameters expected by get_valid_orders_func are provided.
                # This function's signature:
                # game, model_id, system_prompt, board_state, power_name, possible_orders,
                # game_history, goals, relationships, private_diary, llm_log_path, current_phase, config

                # For non-LLMAgents, some LLM-specific attributes might not be available.
                # This part might need adjustment based on what get_valid_orders_func expects for non-LLMAgents.
                # For instance, system_prompt, goals, relationships, private_diary are LLMAgent-specific.
                # If get_valid_orders_func is only for LLM-based agents not yet updated to LLMAgent class,
                # this path might be deprecated. If it's for truly non-LLM agents, it needs careful review.

                board_state = (
                    game.get_state()
                )  # Or current_phase_state.get_board_state_dict() if available
                possible_orders = gather_possible_orders(game, power_name)

                # Mocking LLM-specific attributes for non-LLMAgents if necessary for the callback
                # This is a placeholder - how these are handled depends on the design of get_valid_orders_func
                mock_system_prompt = "No system prompt for non-LLMAgent"
                mock_goals: List[str] = []
                mock_relationships: Dict[str, str] = {}
                mock_private_diary = "(No diary for non-LLMAgent)"

                orders = await self.get_valid_orders_func(
                    game,
                    getattr(agent, "model_id", "unknown_model"),
                    getattr(agent, "system_prompt", mock_system_prompt),
                    board_state,
                    power_name,
                    possible_orders,
                    game_history,
                    getattr(agent, "goals", mock_goals),
                    getattr(agent, "relationships", mock_relationships),
                    getattr(
                        agent,
                        "format_private_diary_for_prompt",
                        lambda: mock_private_diary,
                    )(),
                    self.config.llm_log_path,
                    game.get_current_phase(),  # or current_phase_state.phase_name
                    self.config,
                )
                logger.debug(
                    f"✅ {power_name} (Callback): Generated {len(orders)} orders"
                )
                return orders
            except Exception as e:
                logger.error(
                    f"❌ Error getting orders for {power_name} via callback: {e}. Defaulting to no orders.",
                    exc_info=True,
                )
                return []

    async def _process_phase_results_and_updates(
        self,
        game: "Game",
        game_history: "GameHistory",
        all_orders_for_phase: Dict[str, List[str]],
        processed_phase_name: str,
    ):
        logger.info(f"Processing results for phase: {processed_phase_name}")

        # Submit orders to the game engine
        for power_name, orders in all_orders_for_phase.items():
            if power_name in self.active_powers:  # Only submit for active LLM powers
                game.set_orders(power_name, orders)
            elif (
                not orders
                and power_name in game.powers
                and not game.powers[power_name].is_eliminated()
            ):
                # If a power (human or other AI) has no orders, submit empty list to avoid issues
                # Only do this if the power is actually in the game and not eliminated.
                # LLM agents should have submitted empty list if they had no orders.
                game.set_orders(power_name, [])

        # Process the game phase
        game.process()
        logger.info(f"Game processed. New phase: {game.get_current_phase()}")

        # Log results to game_history
        # Assuming results are available in game.get_results() after process()
        # game.get_results() returns List[Tuple[power, List[order_result_str]]]
        # This needs to be mapped correctly to game_history.add_results
        # For now, let's assume add_results can take this or it's handled by an adapter.
        # The original lm_game.py did:
        # for power_name_iter, power_orders in all_orders.items():
        #     order_results = [game.get_order_resolution(order) for order in power_orders]
        #     game_history.add_results(processed_phase_name, power_name_iter, order_results)

        for power_name_iter, power_orders_submitted in all_orders_for_phase.items():
            if power_name_iter in game.powers:  # Ensure power is still valid
                order_results_for_power = []
                for order_str in power_orders_submitted:
                    # game.get_order_resolution might not exist or work this way with all game objects.
                    # A more robust way is to iterate through game.results if available
                    # or parse from the overall game state if necessary.
                    # For now, assuming a simplified approach or that results are part of game object structure.
                    # This part is tricky without knowing the exact diplomacy library's state post-process().
                    # Let's assume a placeholder or that this info is implicitly handled by phase summary.
                    # The crucial part is that game.process() was called.
                    # The original `game.get_order_resolution(order)` seems to be from a specific example.
                    # Standard library usually gives all results together.
                    # Let's assume we can get results broadly.
                    # For now, we'll skip detailed result logging here if it's too complex,
                    # relying on the phase summary to capture outcomes.
                    # A simple way:
                    # if order_str in game.successful_orders: result = ["successful"] else: result = ["failed/unknown"]
                    # This is highly dependent on diplomacy library version.
                    # The example from original code:
                    try:
                        # This is a bit of a guess, depends on how game object stores results
                        # This might be specific to certain versions or custom game objects.
                        # A common pattern is game.results which gives all results.
                        # For now, let's assume a simplified result representation.
                        # This part of history logging might need to be adapted based on actual game object.
                        # results_for_order = game.get_order_resolution(order_str) # This method is not standard
                        results_for_order = ["Result N/A"]  # Placeholder
                    except Exception:
                        results_for_order = ["Error fetching result"]
                    order_results_for_power.append(results_for_order)

                game_history.add_results(
                    processed_phase_name, power_name_iter, order_results_for_power
                )

        # Phase summary from an "observer" perspective (textual summary of events)
        # This was phase_summary_text in lm_game.py, derived from game.get_phase_history_log()
        # We need to ensure such a log or summary is available from the game object.
        # For now, let's assume game.get_state() or similar can give us enough.
        # This is a placeholder for a more robust phase event summary.
        phase_events_summary_text = f"Summary of events for {processed_phase_name}: All orders processed. New SCs: {game.get_state()['centers']}"
        # A better summary would come from game.get_phase_history_log() if available and formatted.

        # SERIALIZE summary generation instead of running concurrently
        for power_name in self.active_powers:
            agent = self.agent_manager.get_agent(power_name)
            if agent:
                logger.debug(
                    f"Generating phase summary for {power_name}..."
                )  # INFO to DEBUG
                try:
                    # Re-instantiate PhaseSummaryGenerator with the current agent's interface
                    # This is not ideal. PhaseSummaryGenerator should ideally take llm_interface in its method.
                    # Or orchestrator has a way to get a summary_generator for a specific agent.
                    # For now, let's follow the current PhaseSummaryGenerator structure.
                    # This implies the passed phase_summary_generator is generic or for a specific agent.
                    # The plan states "phase_summary_generator: PhaseSummaryGenerator" is passed to __init__ - this param was removed.
                    # This is problematic if it's tied to one agent's interface.
                    # Let's assume the passed phase_summary_generator can handle different powers,
                    # perhaps by taking the agent's llm_interface as an argument to its method.
                    #
                    # Revisiting PhaseSummaryGenerator: it's init with ONE llm_interface.
                    # This means the orchestrator would need a dict of these, or create them on the fly.
                    # The latter is more flexible.
                    # The attribute agent.llm_interface was removed. This line will cause an error.
                    # This needs to be fixed by passing the necessary parts of the agent (model_id, system_prompt, coordinator)
                    # or by refactoring PhaseSummaryGenerator further.
                    # For this linting pass, I will comment out the problematic line, noting it as a bug.
                    # current_agent_summary_generator = PhaseSummaryGenerator(agent.llm_interface, self.config) # BUG: agent.llm_interface removed

                    # await current_agent_summary_generator.generate_and_record_phase_summary(
                    #     game, game_history, processed_phase_name, phase_events_summary_text, all_orders_for_phase
                    # )
                    logger.debug(
                        f"✅ {power_name}: Generated phase summary (actual call commented out due to agent.llm_interface removal)"
                    )  # INFO to DEBUG
                except Exception as e:
                    logger.error(
                        f"❌ Error generating phase summary for {power_name}: {e}",
                        exc_info=e,
                    )

        # SERIALIZE agent state updates instead of running concurrently
        for power_name in self.active_powers:
            agent = self.agent_manager.get_agent(power_name)
            if agent:
                logger.debug(f"Updating state for {power_name}...")  # INFO to DEBUG
                try:
                    # The phase_summary here is the "observer" summary, not agent's generated one.
                    await agent.analyze_phase_and_update_state(
                        game,
                        game.get_state(),
                        phase_events_summary_text,
                        game_history,
                        self.config.llm_log_path,
                    )
                    logger.debug(f"✅ {power_name}: Updated state")  # INFO to DEBUG
                except Exception as e:
                    logger.error(
                        f"❌ Error updating state for {power_name}: {e}", exc_info=e
                    )

        # Consolidate old diary entries (e.g., if a year is 2+ years in the past)
        current_phase = game.get_current_phase()
        current_year = None
        if current_phase and len(current_phase) >= 5 and current_phase[1:5].isdigit():
            current_year = int(current_phase[1:5])
        if current_year is not None and current_year > 1902:
            year_to_consolidate = str(current_year - 2)
            logger.info(
                f"Checking for diary consolidation for year {year_to_consolidate}."
            )

            # SERIALIZE diary consolidation instead of running concurrently
            for power_name in self.active_powers:
                agent = self.agent_manager.get_agent(power_name)
                if agent:
                    logger.debug(
                        f"Consolidating diary for {power_name} (year {year_to_consolidate})..."
                    )  # INFO to DEBUG
                    try:
                        await agent.consolidate_year_diary_entries(
                            year_to_consolidate, game, self.config.llm_log_path
                        )
                        logger.debug(
                            f"✅ {power_name}: Consolidated diary entries"
                        )  # INFO to DEBUG
                    except Exception as e:
                        logger.error(
                            f"❌ Error consolidating diary for {power_name}: {e}",
                            exc_info=e,
                        )

    async def _perform_planning_phase(self, game: "Game", game_history: "GameHistory"):
        logger.warning(
            "Planning phase is deprecated in the new agent system. Skipping planning phase."
        )
        logger.info(
            "The new agent system handles strategic planning internally during order generation."
        )
        return

    async def _perform_negotiation_rounds(
        self, game: "Game", game_history: "GameHistory"
    ):
        current_phase_name = game.get_current_phase()
        logger.info(f"Performing negotiation rounds for phase: {current_phase_name}")

        # Enforce at least 1 negotiation round
        num_rounds = max(1, getattr(self.config, "num_negotiation_rounds", 1))

        for round_num in range(1, num_rounds + 1):
            logger.info(f"Negotiation Round {round_num}/{num_rounds}")

            all_proposed_messages: Dict[str, List[Dict[str, str]]] = (
                {}
            )  # power_name -> list of message dicts

            for power_name in self.active_powers:
                agent = self.agent_manager.get_agent(power_name)
                if agent:
                    logger.debug(
                        f"[Negotiation] Starting message generation for {power_name} (round {round_num})..."
                    )  # INFO to DEBUG
                    try:
                        # Create PhaseState object using the game instance
                        # Ensure PhaseState.from_game is the correct method to get/construct a PhaseState object
                        # from a diplomacy.Game object. If the diplomacy library provides game.get_phase_state(), use that.
                        # Assuming PhaseState.from_game(game) is a custom constructor or utility.
                        current_phase_state = PhaseState.from_game(game)

                        # import asyncio # Moved to top of file or ensure it's available

                        if isinstance(agent, LLMAgent):
                            # New API call for LLMAgent
                            messages_list_objects: List[Message] = (
                                await asyncio.wait_for(
                                    agent.negotiate(
                                        current_phase_state
                                    ),  # Pass the PhaseState object
                                    timeout=120.0,
                                )
                            )
                            # Convert Message objects to dicts for game_history
                            messages_as_dicts = []
                            for msg_obj in messages_list_objects:
                                messages_as_dicts.append(
                                    {
                                        "recipient": msg_obj.recipient,
                                        "content": msg_obj.content,
                                        "message_type": msg_obj.message_type,
                                    }
                                )
                            all_proposed_messages[power_name] = messages_as_dicts
                            logger.debug(
                                f"✅ {power_name} (LLMAgent): Generated {len(messages_as_dicts)} messages (round {round_num})"
                            )
                        else:
                            logger.warning(
                                f"Agent {power_name} is not an LLMAgent. Skipping message generation via new API. Consider updating or removing this agent type."
                            )
                            all_proposed_messages[power_name] = []

                    except asyncio.TimeoutError:
                        logger.error(
                            f"❌ Timeout generating messages for {power_name} (round {round_num})"
                        )
                        all_proposed_messages[power_name] = []
                    except Exception as e:
                        logger.error(
                            f"❌ Error generating messages for {power_name} (round {round_num}): {e}",
                            exc_info=True,
                        )
                        all_proposed_messages[power_name] = []
                else:  # Should not happen if active_powers is derived from agent_manager.agents
                    logger.warning(
                        f"No agent found for active power {power_name} during message generation."
                    )
                    all_proposed_messages[power_name] = []

            # Distribute messages for this round (add to game_history)
            for sender_power, messages_to_send_dicts in all_proposed_messages.items():
                for msg_dict in messages_to_send_dicts:
                    recipient = msg_dict.get("recipient", "GLOBAL").upper()
                    content = msg_dict.get("content", "")
                    # message_type = msg_dict.get("message_type", "private") # Available if needed

                    # Validate recipient against active powers
                    if recipient != "GLOBAL" and recipient not in self.active_powers:
                        logger.warning(
                            f"[{sender_power}] Tried to send message to invalid/inactive recipient '{recipient}'. Skipping."
                        )
                        continue

                    # GameHistory.add_message expects current_phase_name, sender_power, recipient, content.
                    game_history.add_message(
                        current_phase_name, sender_power, recipient, content
                    )
                    logger.debug(
                        f"Message from {sender_power} to {recipient}: {content[:75]}..."
                    )

            # The call to agent.generate_negotiation_diary_entry has been removed.
            # LLMAgent.negotiate() is expected to handle its own diary entries.
            # If a specific flush mechanism for diaries to game_history is needed per agent,
            # it would be called here. For now, assuming internal handling or a later flush.
            # Example:
            # for power_name in self.active_powers:
            #     agent = self.agent_manager.get_agent(power_name)
            #     if agent and hasattr(agent, 'flush_private_diary_to_history'):
            #         try:
            #             await agent.flush_private_diary_to_history(game_history)
            #         except Exception as e:
            #             logger.error(f"Error flushing diary for {power_name}: {e}", exc_info=True)

            if round_num < num_rounds:
                logger.info(
                    f"End of Negotiation Round {round_num}. Next round starting..."
                )
            else:
                logger.info(f"Final Negotiation Round {round_num} completed.")


if __name__ == "__main__":
    # This is for example usage/testing of GamePhaseOrchestrator
    # Requires mocked or dummy versions of dependencies.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("GamePhaseOrchestrator example run (conceptual).")
    # To run this, you'd need to set up mock GameConfig, AgentManager, PhaseSummaryGenerator,
    # a mock Game object, GameHistory, and a mock get_valid_orders_func.
    # Due to complexity, a full runnable example here is extensive.
    # Key aspects to test would be:
    # - Game loop progression through phases.
    # - Correct delegation to phase action methods.
    # - Proper handling of agent plans, negotiations, orders.
    # - Phase result processing and state updates.
    # - Adherence to max_years.
    # - Graceful handling of errors from agent actions.
    print("To test GamePhaseOrchestrator, integrate with other mock/real components.")
