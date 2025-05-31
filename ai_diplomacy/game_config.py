"""
Configuration class for AI Diplomacy games.

This module defines the GameConfig class, which consolidates all game-related
settings, command-line arguments, and derived path configurations for logging
and results. It supports loading model assignments from a TOML file.

Key logging behaviors managed by this configuration:
- `log_to_file`: Controls whether logs are written to files.
    - In development mode (`dev_mode=True`), this defaults to `False`.
    - This behavior can be overridden by setting the environment variable
      `LOG_TO_FILE=1` (forces file logging to `True`) or by explicitly
      passing the `--log_to_file` command-line argument.
- Log paths are derived using `logging_setup.get_log_paths`.
"""
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

    # from .agent import DiplomacyAgent # Assuming DiplomacyAgent is in agent.py - REMOVED

logger = logging.getLogger(__name__)

# Default values that might have been in parse_arguments defaults
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_GAME_ID_PREFIX = "diplomacy_game"
DEFAULT_NUM_PLAYERS = 7
DEFAULT_NUM_NEGOTIATION_ROUNDS = 3
DEFAULT_NEGOTIATION_STYLE = "simultaneous"  # or "round-robin"
# DEFAULT_GAME_SERVER_URL = "ws://localhost:8080" # Unused constant

__all__ = ["GameConfig"]

class GameConfig:
    # Class docstring already exists and is good.

    def __init__(self, args: argparse.Namespace):
        self.args = args

        self.power_name: Optional[str] = getattr(args, "power_name", None)
        self.model_id: Optional[str] = getattr(args, "model_id", None)
        self.num_players: int = getattr(args, "num_players", DEFAULT_NUM_PLAYERS)
        self.game_id_prefix: str = getattr(
            args, "game_id_prefix", DEFAULT_GAME_ID_PREFIX
        )
        self.log_level: str = getattr(args, "log_level", DEFAULT_LOG_LEVEL).upper()
        self.perform_planning_phase: bool = getattr(
            args, "perform_planning_phase", False
        )
        self.num_negotiation_rounds: int = getattr(
            args, "num_negotiation_rounds", DEFAULT_NUM_NEGOTIATION_ROUNDS
        )
        self.negotiation_style: str = getattr(
            args, "negotiation_style", DEFAULT_NEGOTIATION_STYLE
        )
        self.fixed_models: Optional[List[str]] = getattr(args, "fixed_models", None)
        self.randomize_fixed_models: bool = getattr(
            args, "randomize_fixed_models", False
        )
        self.exclude_powers: Optional[List[str]] = getattr(args, "exclude_powers", None)
        self.max_years: Optional[int] = getattr(
            args, "max_years", None
        )  # Added from lm_game.py logic
        
        # Initialize dev_mode first as it's used in log_to_file logic
        self.dev_mode: bool = getattr(args, "dev_mode", False)  # Added dev_mode

        # New attributes for agent definitions
        self.players_list: Optional[List[str]] = getattr(args, "players_list", None)
        self.agent_types_list: Optional[List[str]] = getattr(args, "agent_types_list", None)
        self.bloc_definitions_list: Optional[List[str]] = getattr(args, "bloc_definitions_list", None)

        # Determine log_to_file based on environment variable, args, and dev_mode
        log_to_file_env = os.getenv("LOG_TO_FILE")
        log_to_file_arg = getattr(args, "log_to_file", None) # Check if arg was explicitly passed

        if log_to_file_env == "1":
            self.log_to_file: bool = True
        elif log_to_file_arg is not None:
            self.log_to_file: bool = log_to_file_arg
        elif self.dev_mode:
            self.log_to_file: bool = False  # Default to False in dev_mode
        else:
            self.log_to_file: bool = True   # Default to True if not dev_mode and no arg

        self.verbose_llm_debug: bool = getattr(
            args, "verbose_llm_debug", False
        )  # New attribute
        self.max_diary_tokens: int = getattr(
            args, "max_diary_tokens", 6500
        )  # New attribute

        # --- Load Model Configuration from TOML ---
        self.models_config_path: Optional[str] = getattr(
            args, "models_config_file", "models.toml"
        )
        self.power_model_assignments: Dict[str, str] = {}
        self.default_model_from_config: Optional[str] = None
        self._load_models_config()
        # --- End Model Configuration Loading ---

        # Generate game_id if not provided
        self.current_datetime_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.game_id: str = getattr(args, "game_id", None)
        if not self.game_id:
            self.game_id = f"{self.game_id_prefix}_{self.current_datetime_str}"

        # Configure paths
        # Determine base_log_dir
        # Default base log dir is os.path.join(os.getcwd(), "logs")
        # It can be overridden by args.log_dir
        # If args.log_dir is provided AND it already contains the game_id,
        # then base_log_dir becomes the parent of args.log_dir.
        # Otherwise, args.log_dir (if provided) or the default becomes base_log_dir.

        default_base_log_dir = os.path.join(os.getcwd(), "logs")
        provided_log_dir = getattr(args, "log_dir", None)

        if provided_log_dir:
            if self.game_id in provided_log_dir and os.path.basename(provided_log_dir) == self.game_id:
                # log_dir from args is already game-specific
                self.base_log_dir = os.path.dirname(provided_log_dir)
                # game_id_specific_log_dir will be set by get_log_paths using this base
            else:
                # log_dir from args is a new base
                self.base_log_dir = provided_log_dir
        else:
            # No log_dir from args, use default
            self.base_log_dir = default_base_log_dir

        # Use the new helper function to get all paths
        from .logging_setup import get_log_paths  # Local import to avoid circularity if moved

        log_paths = get_log_paths(self.game_id, self.base_log_dir)
        self.game_id_specific_log_dir: str = log_paths["game_id_specific_log_dir"]
        self.llm_log_path: str = log_paths["llm_log_path"]
        self.general_log_path: str = log_paths["general_log_path"]
        self.results_dir: str = log_paths["results_dir"]
        self.manifestos_dir: str = log_paths["manifestos_dir"]

        # Ensure the directories exist if logging to file
        if self.log_to_file:
            os.makedirs(self.game_id_specific_log_dir, exist_ok=True)
            os.makedirs(self.results_dir, exist_ok=True)
            os.makedirs(self.manifestos_dir, exist_ok=True)

        # Initialize game state placeholders (these will be populated later)
        # Need to import these properly at runtime if used beyond type hints
        from .game_history import GameHistory  # Runtime import

        self.game_history: "GameHistory" = GameHistory()
        self.game_instance: Optional["Game"] = None
        self.powers_and_models: Optional[Dict[str, str]] = None
        self.agents: Optional[Dict[str, "BaseAgent"]] = (
            None  # Dict mapping power_name to BaseAgent instance
        )

        self.log_configuration()

    def log_configuration(self):
        logger.info("Game Configuration Initialized:")
        logger.info(f"  Game ID: {self.game_id}")
        logger.info(f"  Log Level: {self.log_level}")
        logger.info(f"  Number of Players (LLM-controlled): {self.num_players}")
        logger.info(f"  Log to File: {self.log_to_file}")
        if self.log_to_file:
            logger.info(f"  Base Log Directory: {self.base_log_dir}")
            logger.info(
                f"  Game-Specific Log Directory: {self.game_id_specific_log_dir}"
            )
            logger.info(f"  LLM Interaction Log: {self.llm_log_path}")
            logger.info(f"  General Log File: {self.general_log_path}")
            logger.info(f"  Results Directory: {self.results_dir}")
            logger.info(f"  Manifestos Directory: {self.manifestos_dir}")

        if self.power_name and self.model_id:
            logger.info(
                f"  Single Power Mode: {self.power_name} controlled by {self.model_id}"
            )

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
        logger.info(f"  Development Mode: {self.dev_mode}")
        logger.info(f"  Verbose LLM Debug Logging: {self.verbose_llm_debug}")
        logger.info(f"  Max Diary Tokens: {self.max_diary_tokens}")

        if self.players_list:
            logger.info(f"  Players List: {self.players_list}")
        if self.agent_types_list:
            logger.info(f"  Agent Types List: {self.agent_types_list}")
        if self.bloc_definitions_list:
            logger.info(f"  Bloc Definitions List: {self.bloc_definitions_list}")

    def _load_models_config(self):
        """Loads model assignments from the TOML configuration file."""
        if not self.models_config_path or not os.path.exists(self.models_config_path):
            logger.warning(
                f"Models configuration file not found at '{self.models_config_path}'. Model assignments will rely on AgentManager defaults or command-line overrides."
            )
            return

        try:
            config_data = toml.load(self.models_config_path)
            self.default_model_from_config = config_data.get("default_model")

            if self.default_model_from_config:
                logger.info(
                    f"Loaded default model from config: {self.default_model_from_config}"
                )

            loaded_assignments = config_data.get("powers", {})
            if isinstance(loaded_assignments, dict):
                self.power_model_assignments = {
                    str(k).upper(): str(v) for k, v in loaded_assignments.items()
                }
                logger.info(
                    f"Loaded power-specific model assignments from '{self.models_config_path}': {self.power_model_assignments}"
                )
            else:
                logger.warning(
                    f"'powers' section in '{self.models_config_path}' is not a valid dictionary. No power-specific models loaded from file."
                )

        except toml.TomlDecodeError as e:
            logger.error(f"Error decoding TOML from '{self.models_config_path}': {e}")
        except Exception as e:
            logger.error(
                f"Unexpected error loading models configuration from '{self.models_config_path}': {e}",
                exc_info=True,
            )


# Example of how parse_arguments might look (to be kept in lm_game.py or similar entry point)
# def parse_arguments_example() -> argparse.Namespace:
#     parser = argparse.ArgumentParser(description="AI Diplomacy Game Runner")
#     parser.add_argument("--power_name", type=str, help="Name of the power to control (e.g., FRANCE).")
#     parser.add_argument("--model_id", type=str, help="Model ID for the LLM (e.g., ollama/llama3, gpt-4o).")
#     parser.add_argument("--num_players", type=int, default=DEFAULT_NUM_PLAYERS, help="Number of LLM-controlled players.")
#     # ... other arguments ...
#     return parser.parse_args()

if __name__ == "__main__":
    # This is for example usage/testing of GameConfig
    # In a real scenario, args would come from ArgumentParser in the main script.

    # Create a dummy argparse.Namespace for testing
    args_dict = {
        "power_name": None,  # 'FRANCE',
        "model_id": None,  # 'ollama/llama3',
        "num_players": 3,
        "game_id_prefix": "test_game",
        "log_level": "DEBUG",
        "perform_planning_phase": True,
        "num_negotiation_rounds": 2,
        "negotiation_style": "round-robin",
        "fixed_models": ["ollama/mistral", "ollama/llama2"],
        "randomize_fixed_models": True,
        "exclude_powers": ["ITALY"],
        "game_id": None,  # To test auto-generation
        "max_years": 1,
        "log_to_file": True,
        "log_dir": None,  # Test default log directory creation
        "models_config_file": None,  # Test default models configuration file
        "dev_mode": True,  # For testing
        "verbose_llm_debug": False,  # For testing
        "max_diary_tokens": 6500,  # For testing
    }
    test_args = argparse.Namespace(**args_dict)

    # Setup basic logging for the test output
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("--- Testing GameConfig Initialization ---")
    config = GameConfig(test_args)

    # Example of accessing attributes
    logger.info(f"Accessing config.game_id: {config.game_id}")
    logger.info(f"Accessing config.llm_log_path: {config.llm_log_path}")
    logger.info(
        f"Accessing config.game_history (should be empty GameHistory object): {config.game_history}"
    )

    # Test with a specific log_dir (game specific)
    args_dict_log_dir = args_dict.copy()
    args_dict_log_dir["log_dir"] = os.path.join(
        os.getcwd(), "logs", "my_specific_game_log"
    )
    test_args_log_dir = argparse.Namespace(**args_dict_log_dir)
    logger.info("--- Testing GameConfig with specific log_dir ---")
    config_log_dir = GameConfig(test_args_log_dir)
    logger.info(
        f"Accessing config_log_dir.game_id_specific_log_dir: {config_log_dir.game_id_specific_log_dir}"
    )

    logger.info("--- GameConfig Test Complete ---")
