import logging
import asyncio
import random
from typing import Optional, List, Dict, Set, Callable, Coroutine, TYPE_CHECKING, Any
from enum import Enum

from diplomacy import Game  # Removed Phase import
from diplomacy.utils.export import to_saved_game_format
from .phase_summary import PhaseSummaryGenerator

# Add a local Enum for phase types
class PhaseType(Enum):
    MVT = "M"
    RET = "R"
    BLD = "A"

if TYPE_CHECKING:
    from .game_config import GameConfig
    from .agent_manager import AgentManager
    from .game_history import GameHistory, Message as GameHistoryMessage # Phase already imported as DiplomacyPhase
    from .agent import DiplomacyAgent


logger = logging.getLogger(__name__)

# Define a type for the get_valid_orders function that will be passed
GetValidOrdersFuncType = Callable[['Game', str, 'AgentLLMInterface', 'GameHistory', 'GameConfig', int], Coroutine[Any, Any, List[str]]]


class GamePhaseOrchestrator:
    """
    Orchestrates the main game loop, including phase transitions, agent actions,
    negotiations, order submissions, and game processing.
    """

    @staticmethod
    def get_phase_type_from_game(game: 'Game') -> str:
        """Extracts the phase type character from the current phase string (e.g., 'M', 'R', 'A')."""
        phase = game.get_current_phase()
        if not phase or phase in ("FORMING", "COMPLETED"):
            return "-"
        return phase[-1]

    def __init__(
        self, 
        game_config: 'GameConfig', 
        agent_manager: 'AgentManager', 
        phase_summary_generator: 'PhaseSummaryGenerator',
        get_valid_orders_func: GetValidOrdersFuncType # Passed from lm_game.py
    ):
        self.config = game_config
        self.agent_manager = agent_manager
        self.phase_summary_generator = phase_summary_generator
        self.get_valid_orders_func = get_valid_orders_func
        self.active_powers: List[str] = [] # Powers actively playing (not eliminated, not excluded)
        
        if self.config.powers_and_models: # Should be set by AgentManager.assign_models_to_powers
            self.active_powers = list(self.config.powers_and_models.keys())
        else:
            logger.warning("GameConfig.powers_and_models not set when GamePhaseOrchestrator is initialized. Active powers list will be empty initially.")


    async def run_game_loop(self, game: 'Game', game_history: 'GameHistory'):
        """
        Main game loop iterating through years and phases.
        """
        logger.info(f"Starting game loop for game ID: {self.config.game_id}")
        self.config.game_instance = game # Store game instance in config for access by other components

        while not game.is_game_done:
            current_phase_name = game.get_current_phase()
            logger.info(f"--- Current Phase: {current_phase_name} ---")
            game_history.add_phase(current_phase_name)

            # Update active powers based on game state (e.g. eliminated powers)
            self.active_powers = [
                p for p in game.powers if p in self.config.powers_and_models and not game.powers[p].is_eliminated()
            ]
            if not self.active_powers:
                logger.info("No active LLM-controlled powers remaining. Ending game.")
                break
            logger.info(f"Active LLM-controlled powers for this phase: {self.active_powers}")

            all_orders_for_phase: Dict[str, List[str]] = {}

            phase_type = self.get_phase_type_from_game(game)
            if phase_type == PhaseType.MVT.value:
                all_orders_for_phase = await self._execute_movement_phase_actions(game, game_history)
            elif phase_type == PhaseType.RET.value:
                all_orders_for_phase = await self._execute_retreat_phase_actions(game, game_history)
            elif phase_type == PhaseType.BLD.value:
                all_orders_for_phase = await self._execute_build_phase_actions(game, game_history)
            else:
                logger.error(f"Unknown phase type: {game.get_phase_type()}. Skipping.")
                # This case should ideally not be reached in a standard game.
                # Consider how to handle unexpected phase types if they can occur.
                # For now, processing the phase as if it had no orders.
                game.process() # Process to advance the phase
                continue 

            await self._process_phase_results_and_updates(game, game_history, all_orders_for_phase, current_phase_name)

            # Check for max years condition
            if self.config.max_years and game.year >= self.config.max_years :
                current_phase_type = self.get_phase_type_from_game(game)
                # End after the last build phase of the max_year or if it's winter and game is done
                if (current_phase_type == PhaseType.BLD.value and "WINTER" in current_phase_name.upper()) or \
                   ("WINTER" in current_phase_name.upper() and game.is_game_done):
                    logger.info(f"Reached max_years ({self.config.max_years}). Ending game after {current_phase_name}.")
                    break
        
        logger.info(f"Game {self.config.game_id} finished. Final phase: {game.get_current_phase()}")
        # Final state logging or result processing can be triggered here or by the caller of run_game_loop

    async def _execute_movement_phase_actions(self, game: 'Game', game_history: 'GameHistory') -> Dict[str, List[str]]:
        logger.info("Executing Movement Phase actions...")
        current_phase_name = game.get_current_phase()

        if self.config.perform_planning_phase:
            await self._perform_planning_phase(game, game_history)

        await self._perform_negotiation_rounds(game, game_history)

        orders_by_power: Dict[str, List[str]] = {}
        order_tasks = []

        for power_name in self.active_powers:
            agent = self.agent_manager.get_agent(power_name)
            if agent:
                # Pass agent.llm_interface to get_valid_orders_func
                order_tasks.append(
                    self._get_orders_for_power(game, power_name, agent, game_history, self.config.num_negotiation_rounds)
                )
            else: # Should not happen if active_powers is derived from agent_manager.agents
                logger.warning(f"No agent found for active power {power_name} during order generation.")
                orders_by_power[power_name] = [] # Submit no orders

        # Gather all orders concurrently
        results = await asyncio.gather(*order_tasks, return_exceptions=True)
        
        for i, power_name in enumerate(self.active_powers):
            if isinstance(results[i], Exception):
                logger.error(f"Error getting orders for {power_name}: {results[i]}", exc_info=results[i])
                orders_by_power[power_name] = [] # Submit no orders on error
            else:
                orders_by_power[power_name] = results[i]
            
            game_history.add_orders(current_phase_name, power_name, orders_by_power[power_name])
            # Add order diary entry
            agent = self.agent_manager.get_agent(power_name)
            if agent: # Agent should exist if orders were successfully generated
                await agent.generate_order_diary_entry(game, orders_by_power[power_name], self.config.llm_log_path)
        
        return orders_by_power

    async def _execute_retreat_phase_actions(self, game: 'Game', game_history: 'GameHistory') -> Dict[str, List[str]]:
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
                    self._get_orders_for_power(game, power_name, agent, game_history, 0) # num_negotiation_rounds = 0
                )
            else:
                logger.warning(f"No agent found for active power {power_name} during retreat order generation.")
                orders_by_power[power_name] = []
        
        results = await asyncio.gather(*order_tasks, return_exceptions=True)
        active_powers_with_retreats = [p for p in self.active_powers if game.powers[p].must_retreat]

        for i, power_name in enumerate(active_powers_with_retreats):
            if isinstance(results[i], Exception):
                logger.error(f"Error getting retreat orders for {power_name}: {results[i]}", exc_info=results[i])
                orders_by_power[power_name] = []
            else:
                orders_by_power[power_name] = results[i]
            game_history.add_orders(current_phase_name, power_name, orders_by_power[power_name])
            # Order diary for retreats (optional, could be simpler)
            agent = self.agent_manager.get_agent(power_name)
            if agent:
                 await agent.generate_order_diary_entry(game, orders_by_power[power_name], self.config.llm_log_path)

        return orders_by_power

    async def _execute_build_phase_actions(self, game: 'Game', game_history: 'GameHistory') -> Dict[str, List[str]]:
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
                    self._get_orders_for_power(game, power_name, agent, game_history, 0) # num_negotiation_rounds = 0
                )
            else:
                logger.warning(f"No agent found for active power {power_name} during build order generation.")
                orders_by_power[power_name] = []

        results = await asyncio.gather(*order_tasks, return_exceptions=True)
        active_powers_with_builds = [p for p in self.active_powers if game.powers[p].n_builds != 0]

        for i, power_name in enumerate(active_powers_with_builds):
            if isinstance(results[i], Exception):
                logger.error(f"Error getting build orders for {power_name}: {results[i]}", exc_info=results[i])
                orders_by_power[power_name] = []
            else:
                orders_by_power[power_name] = results[i]
            game_history.add_orders(current_phase_name, power_name, orders_by_power[power_name])
            # Order diary for builds
            agent = self.agent_manager.get_agent(power_name)
            if agent:
                await agent.generate_order_diary_entry(game, orders_by_power[power_name], self.config.llm_log_path)
        
        return orders_by_power

    async def _get_orders_for_power(
        self, game: 'Game', power_name: str, agent: 'DiplomacyAgent', game_history: 'GameHistory', num_negotiation_rounds: int
    ) -> List[str]:
        """Helper to call the passed get_valid_orders_func."""
        # The get_valid_orders_func is expected to be the function from lm_game.py (or its refactored equivalent)
        # Its signature is: async def get_valid_orders(game, model_id, agent_system_prompt, board_state, power_name, possible_orders, game_history, model_error_stats, agent_goals, agent_relationships, agent_private_diary_str, log_file_path, phase)
        model_error_stats: dict = {}
        board_state = game.get_state()
        possible_orders = agent.llm_interface.coordinator.gather_possible_orders(game, power_name) if hasattr(agent.llm_interface.coordinator, 'gather_possible_orders') else game.get_all_possible_orders()
        return await self.get_valid_orders_func(
            game,
            agent.model_id,
            agent.system_prompt,
            board_state,
            power_name,
            possible_orders,
            game_history,
            model_error_stats,
            agent.goals,
            agent.relationships,
            agent.format_private_diary_for_prompt(),
            self.config.llm_log_path,
            game.get_current_phase(),
        )

    async def _process_phase_results_and_updates(
        self, game: 'Game', game_history: 'GameHistory', all_orders_for_phase: Dict[str, List[str]], processed_phase_name: str
    ):
        logger.info(f"Processing results for phase: {processed_phase_name}")
        
        # Submit orders to the game engine
        for power_name, orders in all_orders_for_phase.items():
            if power_name in self.active_powers: # Only submit for active LLM powers
                game.set_orders(power_name, orders)
            elif not orders and power_name in game.powers and not game.powers[power_name].is_eliminated():
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
            if power_name_iter in game.powers: # Ensure power is still valid
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
                        results_for_order = ["Result N/A"] # Placeholder
                    except Exception:
                        results_for_order = ["Error fetching result"]
                    order_results_for_power.append(results_for_order)
                
                game_history.add_results(processed_phase_name, power_name_iter, order_results_for_power)


        # Phase summary from an "observer" perspective (textual summary of events)
        # This was phase_summary_text in lm_game.py, derived from game.get_phase_history_log()
        # We need to ensure such a log or summary is available from the game object.
        # For now, let's assume game.get_state() or similar can give us enough.
        # This is a placeholder for a more robust phase event summary.
        phase_events_summary_text = f"Summary of events for {processed_phase_name}: All orders processed. New SCs: {game.get_state()['centers']}"
        # A better summary would come from game.get_phase_history_log() if available and formatted.


        summary_tasks = []
        for power_name in self.active_powers:
            agent = self.agent_manager.get_agent(power_name)
            if agent:
                # The PhaseSummaryGenerator is initialized with the specific agent's llm_interface
                # So, we need one generator per agent, or pass the interface to the generator.
                # The current plan has one PhaseSummaryGenerator passed to orchestrator.
                # This means PhaseSummaryGenerator needs to be flexible.
                # The __init__ of PhaseSummaryGenerator takes an llm_interface.
                # This implies the orchestrator should iterate agents and use *their* llm_interface
                # to initialize a temporary PhaseSummaryGenerator or the generator needs to be power-agnostic
                # and take the interface as a method argument.
                # Let's assume PhaseSummaryGenerator is created *per agent interaction* or takes llm_interface.
                # The current PhaseSummaryGenerator constructor takes ONE llm_interface.
                # This means we should call it using the agent's specific interface.
                
                # Re-instantiate PhaseSummaryGenerator with the current agent's interface
                # This is not ideal. PhaseSummaryGenerator should ideally take llm_interface in its method.
                # Or orchestrator has a way to get a summary_generator for a specific agent.
                # For now, let's follow the current PhaseSummaryGenerator structure.
                # This implies the passed phase_summary_generator is generic or for a specific agent.
                # The plan states "phase_summary_generator: PhaseSummaryGenerator" is passed to __init__.
                # This is problematic if it's tied to one agent's interface.
                # Let's assume the passed phase_summary_generator can handle different powers,
                # perhaps by taking the agent's llm_interface as an argument to its method.
                #
                # Revisiting PhaseSummaryGenerator: it's init with ONE llm_interface.
                # This means the orchestrator would need a dict of these, or create them on the fly.
                # The latter is more flexible.
                current_agent_summary_generator = PhaseSummaryGenerator(agent.llm_interface, self.config)

                summary_tasks.append(
                    current_agent_summary_generator.generate_and_record_phase_summary(
                        game, game_history, processed_phase_name, phase_events_summary_text, all_orders_for_phase
                    )
                )
        
        await asyncio.gather(*summary_tasks, return_exceptions=True) # Wait for all summaries

        # Update agent states (goals, relationships)
        update_tasks = []
        for power_name in self.active_powers:
            agent = self.agent_manager.get_agent(power_name)
            if agent:
                # The phase_summary here is the "observer" summary, not agent's generated one.
                update_tasks.append(
                    agent.analyze_phase_and_update_state(
                        game, game.get_state(), phase_events_summary_text, game_history, self.config.llm_log_path
                    )
                )
        await asyncio.gather(*update_tasks, return_exceptions=True) # Wait for all state updates

        # Consolidate old diary entries (e.g., if a year is 2+ years in the past)
        current_phase = game.get_current_phase()
        current_year = None
        if current_phase and len(current_phase) >= 5 and current_phase[1:5].isdigit():
            current_year = int(current_phase[1:5])
        if current_year is not None and current_year > 1902:
            year_to_consolidate = str(current_year - 2)
            logger.info(f"Checking for diary consolidation for year {year_to_consolidate}.")
            consolidation_tasks = []
            for power_name in self.active_powers:
                agent = self.agent_manager.get_agent(power_name)
                if agent:
                    consolidation_tasks.append(
                        agent.consolidate_year_diary_entries(year_to_consolidate, game, self.config.llm_log_path)
                    )
            await asyncio.gather(*consolidation_tasks, return_exceptions=True)


    async def _perform_planning_phase(self, game: 'Game', game_history: 'GameHistory'):
        logger.info("Performing planning phase...")
        planning_tasks = []
        for power_name in self.active_powers:
            agent = self.agent_manager.get_agent(power_name)
            if agent:
                async def generate_and_store_plan(current_agent, current_game, current_history, current_config):
                    plan = await current_agent.generate_plan(current_game, current_history, current_config.llm_log_path)
                    current_history.add_plan(current_game.get_current_phase(), current_agent.power_name, plan)
                    logger.info(f"Plan for {current_agent.power_name}: {plan[:100]}...")
                
                planning_tasks.append(generate_and_store_plan(agent, game, game_history, self.config))
        
        await asyncio.gather(*planning_tasks, return_exceptions=True)

    async def _perform_negotiation_rounds(self, game: 'Game', game_history: 'GameHistory'):
        current_phase_name = game.get_current_phase()
        logger.info(f"Performing negotiation rounds for phase: {current_phase_name}")

        for round_num in range(1, self.config.num_negotiation_rounds + 1):
            logger.info(f"Negotiation Round {round_num}/{self.config.num_negotiation_rounds}")
            
            all_proposed_messages: Dict[str, List[Dict[str, str]]] = {} # power_name -> list of message dicts
            message_generation_tasks = []

            for power_name in self.active_powers:
                agent = self.agent_manager.get_agent(power_name)
                if agent:
                    # Define a task for each agent to generate messages
                    async def generate_msgs_for_agent(p_name, ag, gm, gh, phase, log_path, active_pws):
                        # Ensure board_state is current for this negotiation round
                        board_state = gm.get_state() 
                        # possible_orders might be too much for negotiation, pass empty or simplified
                        possible_orders_for_negotiation = {} # Or fetch if truly needed by prompt

                        return await ag.generate_messages(
                            game=gm, 
                            board_state=board_state, 
                            possible_orders=possible_orders_for_negotiation,
                            game_history=gh,
                            current_phase=phase, # current_phase_name
                            log_file_path=log_path,
                            active_powers=active_pws # list of other active powers
                        )
                    
                    message_generation_tasks.append(
                        generate_msgs_for_agent(
                            power_name, agent, game, game_history, current_phase_name, 
                            self.config.llm_log_path, 
                            [p for p in self.active_powers if p != power_name]
                        )
                    )
                else: # Should not happen for active powers
                    all_proposed_messages[power_name] = []

            # Gather all generated messages
            results = await asyncio.gather(*message_generation_tasks, return_exceptions=True)
            
            for i, power_name in enumerate(self.active_powers):
                if isinstance(results[i], Exception):
                    logger.error(f"Error generating messages for {power_name}: {results[i]}", exc_info=results[i])
                    all_proposed_messages[power_name] = []
                else:
                    all_proposed_messages[power_name] = results[i]

            # Distribute messages for this round (add to game_history)
            for sender_power, messages_to_send in all_proposed_messages.items():
                for msg_dict in messages_to_send:
                    recipient = msg_dict.get("recipient", "GLOBAL").upper()
                    content = msg_dict.get("content", "")
                    
                    # Validate recipient (must be an active power or GLOBAL)
                    if recipient != "GLOBAL" and recipient not in self.active_powers:
                        logger.warning(f"[{sender_power}] Tried to send message to invalid/inactive recipient '{recipient}'. Skipping.")
                        continue
                        
                    game_history.add_message(current_phase_name, sender_power, recipient, content)
                    logger.info(f"Message from {sender_power} to {recipient}: {content[:75]}...")
            
            # After messages are "sent" (recorded), agents generate negotiation diary entries
            diary_tasks = []
            for power_name in self.active_powers:
                agent = self.agent_manager.get_agent(power_name)
                if agent:
                    diary_tasks.append(
                        agent.generate_negotiation_diary_entry(game, game_history, self.config.llm_log_path)
                    )
            await asyncio.gather(*diary_tasks, return_exceptions=True)

            if round_num < self.config.num_negotiation_rounds:
                 logger.info(f"End of Negotiation Round {round_num}. Next round starting...")
            else:
                 logger.info(f"Final Negotiation Round {round_num} completed.")

if __name__ == '__main__':
    # This is for example usage/testing of GamePhaseOrchestrator
    # Requires mocked or dummy versions of dependencies.
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
