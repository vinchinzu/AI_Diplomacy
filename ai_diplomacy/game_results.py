import logging
import os
import json
from datetime import datetime
from typing import Dict, TYPE_CHECKING

# Import usage tracking functions
from .services.usage_tracker import get_usage_stats_by_country, get_total_usage_stats

# Use try-except for diplomacy import for environments where it might not be immediately available
# or to handle different import styles if necessary, though direct import is usually fine.
try:
    from diplomacy import Game
    from diplomacy.utils.export import to_saved_game_format
except ImportError:
    logging.error("Diplomacy library not found. GameResultsProcessor might not function correctly for 'Game' objects.")
    # Define Game as a placeholder if not found, to allow type hinting to work somewhat
    if 'Game' not in globals(): # Check if already defined by a previous attempt or TYPE_CHECKING block
        Game = type('Game', (object,), {})


if TYPE_CHECKING:
    from .game_config import GameConfig
    from .game_history import GameHistory # Assuming GameHistory can be pickled or has a to_dict method
    from .agents.base import BaseAgent

logger = logging.getLogger(__name__)

class GameResultsProcessor:
    """
    Handles the saving of game results, including final game state,
    game history, and agent manifestos.
    """

    def __init__(self, game_config: 'GameConfig'):
        """
        Initializes the GameResultsProcessor.

        Args:
            game_config: The game configuration object, providing paths for saving results.
        """
        self.config = game_config
        logger.info("GameResultsProcessor initialized.")

    def save_game_state(self, game_instance: 'Game', game_history: 'GameHistory'):
        """
        Saves the final game state and the detailed game history.

        Args:
            game_instance: The final diplomacy.Game object.
            game_history: The GameHistory object containing records of all phases.
        """
        if not self.config.log_to_file:
            logger.info("File logging disabled, skipping saving game state and history.")
            return

        # 1. Save the final game state (e.g., .json, .svg)
        try:
            # Ensure results_dir exists (GameConfig should create it, but double-check)
            os.makedirs(self.config.results_dir, exist_ok=True)
            
            final_state_path_json = os.path.join(self.config.results_dir, f"{self.config.game_id}_final_state.json")
            # The to_saved_game_format function typically returns a string (JSON).
            # It might require a Game object that has been fully processed.
            if hasattr(game_instance, 'is_game_done') and game_instance.is_game_done: # Check if it's a real Game obj
                game_state_json_str = to_saved_game_format(game_instance)
                # Ensure it's a string - to_saved_game_format might return a dict
                if isinstance(game_state_json_str, dict):
                    game_state_json_str = json.dumps(game_state_json_str, indent=2, default=str)
                with open(final_state_path_json, 'w', encoding='utf-8') as f:
                    f.write(game_state_json_str)
                logger.info(f"Final game state (JSON) saved to: {final_state_path_json}")

                # Optionally, save an SVG of the final board if possible and desired
                # This depends on the capabilities of the 'diplomacy' library version
                if hasattr(game_instance, 'render_negotiation_messages_html'): # A guess for a render method
                    # final_state_path_svg = os.path.join(self.config.results_dir, f"{self.config.game_id}_final_board.svg") # Unused variable as SVG saving is commented
                    try:
                        # Example: game_instance.render().save_svg(final_state_path_svg)
                        # This is highly dependent on the library; adjust as needed.
                        # For now, we'll skip if no obvious method.
                        # svg_data = game_instance.render_to_svg_bytes() # if such a method exists
                        # with open(final_state_path_svg, 'wb') as f:
                        #     f.write(svg_data)
                        # logger.info(f"Final board SVG saved to: {final_state_path_svg}")
                        pass # Placeholder for SVG saving
                    except Exception as e_svg:
                        logger.warning(f"Could not save final board SVG: {e_svg}")
            else:
                logger.warning("Game instance is not a valid Diplomacy Game object or game is not done. Skipping JSON state save.")

        except Exception as e:
            logger.error(f"Error saving final game state: {e}", exc_info=True)

        # 2. Save the game history
        # GameHistory might be complex. Consider serializing to JSON via a custom method
        # or pickling if appropriate. For simplicity, a JSON representation is preferred.
        try:
            history_path_json = os.path.join(self.config.results_dir, f"{self.config.game_id}_game_history.json")
            
            # If GameHistory has a to_dict method:
            if hasattr(game_history, 'to_dict'):
                history_dict = game_history.to_dict() # Requires implementing to_dict in GameHistory
            else:
                # Basic serialization using dataclasses.asdict if GameHistory and Phase are dataclasses
                # This is a fallback and might need refinement for complex objects like Message.
                # For now, let's assume GameHistory might need a dedicated method.
                # Placeholder: just try to dump what we have, might fail for complex types.
                # A proper solution would be game_history.export_to_json_serializable_dict()
                # For now, we'll just log a warning if no to_dict() method.
                logger.warning("GameHistory does not have a 'to_dict' method. Saving history might be incomplete or fail.")
                # Attempting a shallow conversion for demonstration. This will likely miss nested custom objects.
                history_dict = {
                    "phases": [vars(phase) for phase in game_history.phases]
                }
                # A more robust way for dataclasses:
                # from dataclasses import asdict
                # history_dict = {"phases": [asdict(phase) for phase in game_history.phases]}
                # This still needs Message to be serializable.

            with open(history_path_json, 'w', encoding='utf-8') as f:
                json.dump(history_dict, f, indent=2, default=str) # default=str for non-serializable
            logger.info(f"Game history saved to: {history_path_json}")
        except Exception as e:
            logger.error(f"Error saving game history: {e}", exc_info=True)


    def save_agent_manifestos(self, agents: Dict[str, 'BaseAgent']):
        """
        Saves the final state (goals, relationships, journal/diary) of each agent.

        Args:
            agents: A dictionary mapping power names to their DiplomacyAgent instances.
        """
        if not self.config.log_to_file:
            logger.info("File logging disabled, skipping saving agent manifestos.")
            return
            
        if not agents:
            logger.warning("No agents provided to save_agent_manifestos.")
            return

        logger.info(f"Saving agent manifestos to directory: {self.config.manifestos_dir}")
        os.makedirs(self.config.manifestos_dir, exist_ok=True) # Ensure it exists

        for power_name, agent in agents.items():
            manifesto_path = os.path.join(self.config.manifestos_dir, f"{self.config.game_id}_{power_name}_manifesto.txt")
            try:
                with open(manifesto_path, 'w', encoding='utf-8') as f:
                    # Get agent info - works with both old and new agent types
                    agent_info = agent.get_agent_info() if hasattr(agent, 'get_agent_info') else {}
                    model_id = getattr(agent, 'model_id', agent_info.get('model_id', 'unknown'))
                    
                    f.write(f"Manifesto for {power_name} (Model: {model_id})\n")
                    f.write(f"Game ID: {self.config.game_id}\n")
                    f.write(f"Timestamp: {self.config.current_datetime_str}\n")
                    f.write(f"Agent Type: {agent_info.get('type', type(agent).__name__)}\n")
                    
                    # Handle goals - may not exist in new agent types
                    f.write("\n--- Final Goals ---\n")
                    if hasattr(agent, 'goals') and agent.goals:
                        for goal in agent.goals:
                            f.write(f"- {goal}\n")
                    else:
                        f.write("(No specific goals listed or not supported by this agent type)\n")

                    # Handle relationships - may not exist in new agent types
                    f.write("\n--- Final Relationships ---\n")
                    if hasattr(agent, 'relationships') and agent.relationships:
                        for p, status in agent.relationships.items():
                            f.write(f"- {p}: {status}\n")
                    else:
                        f.write("(No specific relationships listed or not supported by this agent type)\n")

                    # Handle private journal - may not exist in new agent types
                    f.write("\n--- Private Journal (Last 20 entries) ---\n")
                    if hasattr(agent, 'private_journal') and agent.private_journal:
                        for entry in agent.private_journal[-20:]: # Show last few entries
                            f.write(f"{entry}\n")
                    else:
                        f.write("(Journal is empty or not supported by this agent type)\n")
                        
                    # Handle private diary - may not exist in new agent types
                    f.write("\n--- Private Diary (Last 50 entries) ---\n")
                    if hasattr(agent, 'private_diary') and agent.private_diary:
                        for entry in agent.private_diary[-50:]: # Show last few entries
                            f.write(f"{entry}\n")
                    else:
                        f.write("(Diary is empty or not supported by this agent type)\n")
                
                logger.info(f"Manifesto for {power_name} saved to: {manifesto_path}")
            except Exception as e:
                logger.error(f"Error saving manifesto for {power_name}: {e}", exc_info=True)

    def log_final_results(self, game_instance: 'Game'):
        """
        Logs the final results of the game, including supply center counts and winner.

        Args:
            game_instance: The completed Diplomacy game instance.
        """
        logger.info("--- FINAL GAME RESULTS ---")
        logger.info(f"Game ID: {self.config.game_id}")
        
        # Check if game is properly completed
        if hasattr(game_instance, 'is_game_done') and game_instance.is_game_done:
            logger.info("Game completed successfully.")
        elif hasattr(game_instance, 'status') and game_instance.status == 'COMPLETED':
            logger.info("Game marked as completed.")
        else:
            logger.warning("Game is not marked as done, or not a valid Game object. Final results might be incomplete.")

        # Log supply center counts
        if hasattr(game_instance, 'powers') and game_instance.powers:
            logger.info("Final Supply Center Counts:")
            # Sort powers by supply center count (descending)
            power_centers = []
            for power_name, power in game_instance.powers.items():
                if hasattr(power, 'centers'):
                    center_count = len(power.centers)
                    centers_list = sorted(power.centers) if power.centers else []
                    power_centers.append((power_name, center_count, centers_list))
            
            # Sort by center count (descending)
            power_centers.sort(key=lambda x: x[1], reverse=True)
            
            for power_name, center_count, centers_list in power_centers:
                centers_str = ", ".join(centers_list) if centers_list else "None"
                logger.info(f"  {power_name:<8}: {center_count:2d} SCs ({centers_str})")

            # Determine winner(s)
            if power_centers:
                max_centers = power_centers[0][1]
                winners = [power for power, count, _ in power_centers if count == max_centers]
                if len(winners) == 1:
                    logger.info(f"Winner: {winners[0]} with {max_centers} supply centers")
                else:
                    logger.info(f"Draw between: {', '.join(winners)} with {max_centers} supply centers each")
        else:
            logger.warning("No power information available for final results.")

        # Try to get winner information from game object
        if hasattr(game_instance, 'get_winners'):
            try:
                winners = game_instance.get_winners()
                if winners:
                    logger.info(f"Game winners: {', '.join(winners)}")
            except Exception as e:
                logger.warning(f"Could not determine winners: {e}")
        else:
            logger.warning("Game object does not have 'get_winners' method to determine winner.")

        logger.info("-" * 26)

        # Display API usage statistics
        self.log_api_usage_stats()

    def log_api_usage_stats(self):
        """Log comprehensive API usage statistics by country."""
        logger.info("--- API USAGE STATISTICS ---")
        
        try:
            # Get usage stats by country
            country_stats = get_usage_stats_by_country(self.config.game_id)
            total_stats = get_total_usage_stats(self.config.game_id)
            
            if not country_stats:
                logger.info("No API usage data recorded for this game.")
                return
            
            logger.info("Usage by Country:")
            logger.info(f"{'Country':<8} {'API Calls':<10} {'Input Tokens':<13} {'Output Tokens':<14} {'Models'}")
            logger.info("-" * 70)
            
            for country, stats in sorted(country_stats.items()):
                models_str = ", ".join(stats['models'])
                logger.info(f"{country:<8} {stats['api_calls']:<10} {stats['input_tokens']:<13} {stats['output_tokens']:<14} {models_str}")
            
            logger.info("-" * 70)
            logger.info(f"{'TOTAL':<8} {total_stats['total_api_calls']:<10} {total_stats['total_input_tokens']:<13} {total_stats['total_output_tokens']:<14}")
            
            # Calculate costs (rough estimates)
            total_input = total_stats['total_input_tokens']
            total_output = total_stats['total_output_tokens']
            
            # Rough cost estimates (these are approximate and may vary)
            # GPT-4o: $5/1M input, $15/1M output
            # GPT-4o-mini: $0.15/1M input, $0.60/1M output  
            # GPT-3.5-turbo: $0.50/1M input, $1.50/1M output
            estimated_cost_gpt4o = (total_input * 5 + total_output * 15) / 1_000_000
            estimated_cost_gpt4o_mini = (total_input * 0.15 + total_output * 0.60) / 1_000_000
            estimated_cost_gpt35 = (total_input * 0.50 + total_output * 1.50) / 1_000_000
            
            logger.info("")
            logger.info("Estimated Costs (if all tokens were from):")
            logger.info(f"  GPT-4o:      ${estimated_cost_gpt4o:.4f}")
            logger.info(f"  GPT-4o-mini: ${estimated_cost_gpt4o_mini:.4f}")
            logger.info(f"  GPT-3.5:     ${estimated_cost_gpt35:.4f}")
            logger.info("  (Ollama models: Free)")
            
        except Exception as e:
            logger.error(f"Error displaying API usage statistics: {e}", exc_info=True)
        
        logger.info("-" * 30)


if __name__ == '__main__':
    # Example Usage for testing GameResultsProcessor
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # --- Mocking dependencies ---
    from .game_config import GameConfig
    
    class MockGameConfigResults(GameConfig):
        def __init__(self, game_id="results_test_game", log_to_file=True):
            # Create minimal mock args for parent constructor
            class MockArgs:
                def __init__(self):
                    self.game_id = game_id
                    self.game_id_prefix = "test"
                    self.log_level = "INFO"
                    self.log_to_file = log_to_file
                    self.log_dir = None
                    self.power_name = None
                    self.model_id = None
                    self.num_players = 7
                    self.perform_planning_phase = False
                    self.num_negotiation_rounds = 1
                    self.negotiation_style = "simultaneous"
                    self.fixed_models = None
                    self.randomize_fixed_models = False
                    self.exclude_powers = None
                    self.max_years = None
                    self.dev_mode = False
                    self.verbose_llm_debug = False
                    self.max_diary_tokens = 6500
                    self.models_config_file = "models.toml"
            
            # Call parent constructor
            super().__init__(MockArgs())
            
            # Override for testing
            self.current_datetime_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    class MockDiplomacyAgent:
        def __init__(self, power_name, model_id="mock_model"):
            self.power_name = power_name
            self.model_id = model_id
            self.goals = [f"Take over the world ({power_name})", "Make friends"]
            self.relationships = {"OTHER_POWER": "Neutral"}
            self.private_journal = [f"Journal Entry 1 for {power_name}", f"Journal Entry 2 for {power_name}"]
            self.private_diary = [f"[S1901M] Diary entry for {power_name}"]

    class MockGameHistoryResults:
        def __init__(self):
            self.phases = [ # Simplified phase objects for testing to_dict fallback
                {"name": "SPRING 1901M", "orders_by_power": {"FRANCE": ["A PAR H"]}},
                {"name": "AUTUMN 1901M", "orders_by_power": {"FRANCE": ["A PAR - BUR"]}}
            ]
        # Add a to_dict if you want to test that path
        # def to_dict(self): return {"phases": self.phases}


    # Mock diplomacy.Game object (very basic)
    class MockDiplomacyGame:
        def __init__(self):
            self.is_game_done = True # Mark as done for saving state
            self._current_phase = "WINTER 1905" # Example
            self._centers = { # Example SC map
                "FRANCE": ["PAR", "MAR", "BRE", "SPA", "POR", "BEL", "HOL"],
                "ENGLAND": ["LON", "LVP", "EDI", "NWY", "SWE"],
                "GERMANY": ["BER", "MUN", "KIE", "DEN", "RUH", "WAR", "MOS"],
            }
            self._winners = ["GERMANY"] # Example winner

        def get_current_phase(self): return self._current_phase
        def get_state(self): return {"centers": self._centers}
        def get_winners(self): return self._winners
        # Add a dummy to_saved_game_format method if the real one is not available during test
        # This is usually part of the diplomacy library.
        # For testing, we can mock it if `to_saved_game_format` itself is not being tested here.
        # to_saved_game_format = staticmethod(lambda game_obj: json.dumps({"mock_game_state": game_obj._current_phase}))


    logger.info("--- Testing GameResultsProcessor ---")
    
    test_config = MockGameConfigResults()
    results_processor = GameResultsProcessor(test_config)
    
    mock_game_instance = MockDiplomacyGame()
    mock_game_history = MockGameHistoryResults()
    
    # Test saving game state and history
    logger.info("\n--- Testing save_game_state ---")
    results_processor.save_game_state(mock_game_instance, mock_game_history)
    
    # Test saving agent manifestos
    logger.info("\n--- Testing save_agent_manifestos ---")
    mock_agents = {
        "FRANCE": MockDiplomacyAgent("FRANCE", "ollama/test-fr"),
        "GERMANY": MockDiplomacyAgent("GERMANY", "gpt-4-mini")
    }
    results_processor.save_agent_manifestos(mock_agents)
    
    # Test logging final results
    logger.info("\n--- Testing log_final_results ---")
    results_processor.log_final_results(mock_game_instance)

    logger.info(f"\nCheck the directory '{test_config.game_id_specific_log_dir}' for output files.")
    logger.info("--- GameResultsProcessor Test Complete ---")

    # Basic cleanup for test files (optional)
    # import shutil
    # if os.path.exists(test_config.base_log_dir):
    #     logger.info(f"Cleaning up test log directory: {test_config.base_log_dir}")
    #     shutil.rmtree(test_config.base_log_dir)
