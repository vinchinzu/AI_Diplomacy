import os
import logging
import argparse
from datetime import datetime
from typing import Optional, List, Dict, TYPE_CHECKING
import toml

# Import GameHistory and DiplomacyAgent only for type hinting if they are complex
# to avoid circular dependencies at runtime.
if TYPE_CHECKING:
    from diplomacy import Game
    from .game_history import GameHistory
    from .agent import DiplomacyAgent # Assuming DiplomacyAgent is in agent.py

logger = logging.getLogger(__name__)

# Default values that might have been in parse_arguments defaults
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_GAME_ID_PREFIX = "diplomacy_game"
DEFAULT_NUM_PLAYERS = 7
DEFAULT_NUM_NEGOTIATION_ROUNDS = 3
DEFAULT_NEGOTIATION_STYLE = "simultaneous" # or "round-robin"
DEFAULT_GAME_SERVER_URL = "ws://localhost:8080" # Example, not used by lm_game.py directly

class GameConfig:
    """
    Holds game configuration derived from command-line arguments and defaults.
    Also manages derived path configurations for logging and results.
    """
    def __init__(self, args: argparse.Namespace):
        # Store raw arguments
        self.args = args

        # Directly transfer arguments to attributes
        self.power_name: Optional[str] = getattr(args, 'power_name', None)
        self.model_id: Optional[str] = getattr(args, 'model_id', None)
        self.num_players: int = getattr(args, 'num_players', DEFAULT_NUM_PLAYERS)
        self.game_id_prefix: str = getattr(args, 'game_id_prefix', DEFAULT_GAME_ID_PREFIX)
        self.log_level: str = getattr(args, 'log_level', DEFAULT_LOG_LEVEL).upper()
        self.perform_planning_phase: bool = getattr(args, 'perform_planning_phase', False)
        self.num_negotiation_rounds: int = getattr(args, 'num_negotiation_rounds', DEFAULT_NUM_NEGOTIATION_ROUNDS)
        self.negotiation_style: str = getattr(args, 'negotiation_style', DEFAULT_NEGOTIATION_STYLE)
        self.fixed_models: Optional[List[str]] = getattr(args, 'fixed_models', None)
        self.randomize_fixed_models: bool = getattr(args, 'randomize_fixed_models', False)
        self.exclude_powers: Optional[List[str]] = getattr(args, 'exclude_powers', None)
        self.max_years: Optional[int] = getattr(args, 'max_years', None) # Added from lm_game.py logic
        self.log_to_file: bool = getattr(args, 'log_to_file', True) # Assuming default behavior

        # --- Load Model Configuration from TOML ---
        self.models_config_path: Optional[str] = getattr(args, 'models_config_file', "models.toml")
        self.power_model_assignments: Dict[str, str] = {}
        self.default_model_from_config: Optional[str] = None
        self._load_models_config()
        # --- End Model Configuration Loading ---

        # Generate game_id if not provided
        self.current_datetime_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.game_id: str = getattr(args, 'game_id', None)
        if not self.game_id:
            self.game_id = f"{self.game_id_prefix}_{self.current_datetime_str}"

        # Configure paths
        self.base_log_dir: str = os.path.join(os.getcwd(), "logs") # Default base log dir
        # Allow overriding base_log_dir if provided in args (e.g. from network_lm_agent)
        if getattr(args, 'log_dir', None) is not None:
            self.base_log_dir = args.log_dir
        
        # If log_dir in args was a full path for a specific game, adjust base_log_dir
        # This logic assumes log_dir from args might be game-specific or a base.
        # For lm_game.py, we usually construct the game_id_specific_log_dir from a base.
        if getattr(args, 'log_dir', None) and self.game_id in getattr(args, 'log_dir', ""):
             self.game_id_specific_log_dir = getattr(args, 'log_dir')
             self.base_log_dir = os.path.dirname(self.game_id_specific_log_dir)
        else: # Construct game_id_specific_log_dir
            self.game_id_specific_log_dir = os.path.join(self.base_log_dir, self.game_id)

        # Ensure the specific log directory for this game ID exists
        if self.log_to_file:
            os.makedirs(self.game_id_specific_log_dir, exist_ok=True)

        self.llm_log_path: str = os.path.join(self.game_id_specific_log_dir, f"{self.game_id}_llm_interactions.csv")
        self.general_log_path: str = os.path.join(self.game_id_specific_log_dir, f"{self.game_id}_general.log")
        
        self.results_dir: str = os.path.join(self.game_id_specific_log_dir, "results")
        if self.log_to_file: # Only create if logging to file, implies saving results too
            os.makedirs(self.results_dir, exist_ok=True)
            
        self.manifestos_dir: str = os.path.join(self.results_dir, "manifestos")
        if self.log_to_file:
            os.makedirs(self.manifestos_dir, exist_ok=True)

        # Initialize game state placeholders (these will be populated later)
        # Need to import these properly at runtime if used beyond type hints
        from .game_history import GameHistory # Runtime import
        self.game_history: "GameHistory" = GameHistory()
        self.game_instance: Optional["Game"] = None
        self.powers_and_models: Optional[Dict[str, str]] = None
        self.agents: Optional[Dict[str, "DiplomacyAgent"]] = None # Dict mapping power_name to DiplomacyAgent instance

        self.log_configuration()

    def log_configuration(self):
        logger.info("Game Configuration Initialized:")
        logger.info(f"  Game ID: {self.game_id}")
        logger.info(f"  Log Level: {self.log_level}")
        logger.info(f"  Number of Players (LLM-controlled): {self.num_players}")
        logger.info(f"  Log to File: {self.log_to_file}")
        if self.log_to_file:
            logger.info(f"  Base Log Directory: {self.base_log_dir}")
            logger.info(f"  Game-Specific Log Directory: {self.game_id_specific_log_dir}")
            logger.info(f"  LLM Interaction Log: {self.llm_log_path}")
            logger.info(f"  General Log File: {self.general_log_path}")
            logger.info(f"  Results Directory: {self.results_dir}")
            logger.info(f"  Manifestos Directory: {self.manifestos_dir}")
        
        if self.power_name and self.model_id:
            logger.info(f"  Single Power Mode: {self.power_name} controlled by {self.model_id}")
        
        logger.info(f"  Perform Planning Phase: {self.perform_planning_phase}")
        logger.info(f"  Number of Negotiation Rounds: {self.num_negotiation_rounds}")
        logger.info(f"  Negotiation Style: {self.negotiation_style}")
        
        if self.fixed_models:
            logger.info(f"  Fixed Models: {self.fixed_models}")
            logger.info(f"  Randomize Fixed Models: {self.randomize_fixed_models}")
        if self.exclude_powers:
            logger.info(f"  Excluded Powers: {self.exclude_powers}")
        if self.max_years:
            logger.info(f"  Maximum Game Years: {self.max_years}")

    def _load_models_config(self):
        """Loads model assignments from the TOML configuration file."""
        if not self.models_config_path or not os.path.exists(self.models_config_path):
            logger.warning(f"Models configuration file not found at '{self.models_config_path}'. Model assignments will rely on AgentManager defaults or command-line overrides.")
            return

        try:
            config_data = toml.load(self.models_config_path)
            self.default_model_from_config = config_data.get("default_model")
            
            if self.default_model_from_config:
                logger.info(f"Loaded default model from config: {self.default_model_from_config}")

            loaded_assignments = config_data.get("powers", {})
            if isinstance(loaded_assignments, dict):
                self.power_model_assignments = {str(k).upper(): str(v) for k, v in loaded_assignments.items()}
                logger.info(f"Loaded power-specific model assignments from '{self.models_config_path}': {self.power_model_assignments}")
            else:
                logger.warning(f"'powers' section in '{self.models_config_path}' is not a valid dictionary. No power-specific models loaded from file.")

        except toml.TomlDecodeError as e:
            logger.error(f"Error decoding TOML from '{self.models_config_path}': {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading models configuration from '{self.models_config_path}': {e}", exc_info=True)

# Example of how parse_arguments might look (to be kept in lm_game.py or similar entry point)
# def parse_arguments_example() -> argparse.Namespace:
#     parser = argparse.ArgumentParser(description="AI Diplomacy Game Runner")
#     parser.add_argument("--power_name", type=str, help="Name of the power to control (e.g., FRANCE).")
#     parser.add_argument("--model_id", type=str, help="Model ID for the LLM (e.g., ollama/llama3, gpt-4o).")
#     parser.add_argument("--num_players", type=int, default=DEFAULT_NUM_PLAYERS, help="Number of LLM-controlled players.")
#     # ... other arguments ...
#     return parser.parse_args()

if __name__ == '__main__':
    # This is for example usage/testing of GameConfig
    # In a real scenario, args would come from ArgumentParser in the main script.
    
    # Create a dummy argparse.Namespace for testing
    args_dict = {
        'power_name': None, # 'FRANCE',
        'model_id': None, # 'ollama/llama3',
        'num_players': 3,
        'game_id_prefix': 'test_game',
        'log_level': 'DEBUG',
        'perform_planning_phase': True,
        'num_negotiation_rounds': 2,
        'negotiation_style': 'round-robin',
        'fixed_models': ['ollama/mistral', 'ollama/llama2'],
        'randomize_fixed_models': True,
        'exclude_powers': ['ITALY'],
        'game_id': None, # To test auto-generation
        'max_years': 1,
        'log_to_file': True,
        'log_dir': None, # Test default log directory creation
        'models_config_file': None # Test default models configuration file
    }
    test_args = argparse.Namespace(**args_dict)

    # Setup basic logging for the test output
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    logger.info("--- Testing GameConfig Initialization ---")
    config = GameConfig(test_args)
    
    # Example of accessing attributes
    logger.info(f"Accessing config.game_id: {config.game_id}")
    logger.info(f"Accessing config.llm_log_path: {config.llm_log_path}")
    logger.info(f"Accessing config.game_history (should be empty GameHistory object): {config.game_history}")

    # Test with a specific log_dir (game specific)
    args_dict_log_dir = args_dict.copy()
    args_dict_log_dir['log_dir'] = os.path.join(os.getcwd(), "logs", "my_specific_game_log")
    test_args_log_dir = argparse.Namespace(**args_dict_log_dir)
    logger.info("--- Testing GameConfig with specific log_dir ---")
    config_log_dir = GameConfig(test_args_log_dir)
    logger.info(f"Accessing config_log_dir.game_id_specific_log_dir: {config_log_dir.game_id_specific_log_dir}")
    
    logger.info("--- GameConfig Test Complete ---")
