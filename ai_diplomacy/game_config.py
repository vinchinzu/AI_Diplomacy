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
from typing import Optional, List, Dict, TYPE_CHECKING, Any, Callable  # Added Callable
import toml
import importlib  # Added importlib

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from diplomacy import Game  # Game is already here for type hint
    from .game_history import GameHistory
    from .agents.base import BaseAgent

try:
    from ..scenarios import SCENARIO_REGISTRY
except ImportError:
    logger.warning("Could not import SCENARIO_REGISTRY via 'from ..scenarios'. Trying 'from scenarios'.")
    try:
        from scenarios import SCENARIO_REGISTRY
    except ImportError:
        logger.error("Failed to import SCENARIO_REGISTRY. Registry-based scenario loading will fail.")
        SCENARIO_REGISTRY = {}  # Define as empty to prevent NameError during runtime

# Default values that might be used if not in TOML
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_GAME_ID_PREFIX = "diplomacy_game"
DEFAULT_NEGOTIATION_STYLE = "simultaneous"  # Kept as it's used by wwi_test.toml indirectly via game_settings
DEFAULT_BASE_LOG_DIR = os.path.join(os.getcwd(), "logs")

__all__ = ["GameConfig", "setup_logging"]


def setup_logging(
    level: str = "INFO", log_to_file: bool = False, log_paths: Optional[Dict[str, str]] = None
) -> None:
    """
    Configures application-wide logging.

    Args:
        level: The logging level (e.g., "INFO", "DEBUG").
        log_to_file: If True, logs to files specified in log_paths.
        log_paths: A dictionary containing paths for log files.
    """
    # Guard against re-configuring logging during tests, which interferes with pytest's caplog fixture.
    # PYTEST_CURRENT_TEST is an environment variable set by pytest during test runs.
    if os.getenv("PYTEST_CURRENT_TEST"):
        logger.info("Skipping logging setup during pytest run.")
        return

    log_level = getattr(logging, level.upper(), logging.INFO)

    # Use a basic config that plays nicely with others if they also use basicConfig
    # The `force=True` argument (Python 3.8+) is essential to allow re-configuration.
    # Without it, subsequent calls to basicConfig are ignored if a handler is already set.
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,  # Overwrite existing handlers
    )

    if log_to_file and log_paths and "full_log_path" in log_paths:
        try:
            # Add a file handler for detailed logs
            file_handler = logging.FileHandler(log_paths["full_log_path"], mode="a")
            file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            file_handler.setFormatter(file_formatter)
            logging.getLogger().addHandler(file_handler)

            # If a separate path for errors is provided, add a specific handler for that.
            if "error_log_path" in log_paths:
                error_handler = logging.FileHandler(log_paths["error_log_path"], mode="a")
                error_formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s"
                )
                error_handler.setFormatter(error_formatter)
                error_handler.setLevel(logging.ERROR)
                logging.getLogger().addHandler(error_handler)

            logger.info(f"File logging enabled. Full log at: {log_paths['full_log_path']}")
        except Exception as e:
            # Fallback to console logging if file setup fails
            logging.error(f"Failed to configure file logging: {e}", exc_info=True)
            # Ensure basic config is still in effect
            logging.basicConfig(level=log_level)
    else:
        logger.info("File logging is disabled. Logging to console only.")


class GameConfig:
    # Class docstring already exists and is good.

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self._raw_toml_config: Dict[str, Any] = {}

        # --- Load Game Configuration TOML ---
        self.game_config_file_path: Optional[str] = getattr(args, "game_config_file", None)

        # In test environments many callers set a `use_mocks=True` flag (via tests/_shared_fixtures.py).
        # When that flag is present we treat the TOML file as optional and fall back to an empty config.
        self._in_mock_mode: bool = bool(getattr(args, "use_mocks", False))

        if self.game_config_file_path:
            try:
                # Attempt to load directly – if the file does not exist `toml.load` will raise FileNotFoundError
                # which we catch below so that tests can still patch toml.load without an actual file on disk.
                self._raw_toml_config = toml.load(self.game_config_file_path)
                logger.info(f"Loaded game configuration from TOML file: {self.game_config_file_path}")
            except FileNotFoundError:
                logger.warning(
                    f"Game configuration TOML file '{self.game_config_file_path}' not found. Proceeding with empty configuration."
                )
                self._raw_toml_config = {}
            except toml.TomlDecodeError as e:
                logger.error(
                    f"Error decoding TOML from game config file '{self.game_config_file_path}': {e}",
                    exc_info=True,
                )
                raise
            except Exception as e:
                logger.error(
                    f"Unexpected error loading game config file '{self.game_config_file_path}': {e}",
                    exc_info=True,
                )
                raise
        else:
            # No file path supplied.
            if self._in_mock_mode:
                logger.info(
                    "No game_config_file provided but 'use_mocks' flag detected – using empty configuration."
                )
                self._raw_toml_config = {}
            else:
                logger.error("No game configuration TOML file provided via --game-config-file argument.")
                raise ValueError("Game configuration TOML file path is required.")

        # --- Determine configuration values: CLI (for overrides) > TOML > Default ---

        # Core settings from TOML, with potential CLI overrides for a few specific ones
        cli_log_level_override = getattr(args, "log_level", None)
        self.log_level: str = (
            cli_log_level_override or self.get_toml_value("logging.log_level", DEFAULT_LOG_LEVEL)
        ).upper()

        self.game_id_prefix: str = self.get_toml_value("game_settings.game_id_prefix", DEFAULT_GAME_ID_PREFIX)
        self.max_phases: Optional[int] = self.get_toml_value("game_settings.max_phases", None)
        # negotiation_style is kept as it's used by wwi_test.toml indirectly via game_settings in the original code
        self.negotiation_style: str = self.get_toml_value(
            "game_settings.negotiation_style", DEFAULT_NEGOTIATION_STYLE
        )

        self.dev_mode: bool = self.get_toml_value("dev_settings.dev_mode", False)
        self.verbose_llm_debug: bool = self.get_toml_value("dev_settings.verbose_llm_debug", False)

        # Log to file logic: TOML > dev_mode consideration > Default
        log_to_file_toml = self.get_toml_value("logging.log_to_file", None)

        if log_to_file_toml is not None:
            self.log_to_file: bool = bool(log_to_file_toml)
        elif self.dev_mode:  # If dev_mode is true (from TOML) and no other setting, log to file is off
            self.log_to_file: bool = False
        else:  # Default if not dev_mode and no other specifier
            self.log_to_file: bool = True # This is the case for wwi_test.toml

        # --- Agent and Player Configuration (from TOML only) ---
        self.players_list: List[str] = []
        self.agent_types_list: List[str] = []
        self.bloc_definitions_list: List[str] = []
        self.llm_models_list: List[str] = []
        self.agent_countries_list: List[Optional[str]] = []  # For llm, neutral, null agents

        agent_entries_from_toml: Optional[List[Dict[str, Any]]] = None
        toml_config_source_for_agents: Optional[str] = None

        potential_dev_agents = self.get_toml_value("dev_settings.agents")
        if isinstance(potential_dev_agents, list) and potential_dev_agents:
            agent_entries_from_toml = potential_dev_agents
            toml_config_source_for_agents = "dev_settings.agents"
        else:
            potential_top_level_agents = self.get_toml_value("agents")
            if isinstance(potential_top_level_agents, list) and potential_top_level_agents:
                agent_entries_from_toml = potential_top_level_agents
                toml_config_source_for_agents = "agents"

        if agent_entries_from_toml and toml_config_source_for_agents:
            logger.info(
                f"Using agent configurations from TOML file (source: '{toml_config_source_for_agents}')."
            )
            self._parse_agent_data_from_toml(agent_entries_from_toml)
        else:
            logger.warning(
                "No agent configurations found in TOML (checked 'dev_settings.agents' and 'agents'). Game might not function correctly without agent definitions."
            )
            # Depending on game logic, this might be a fatal error.
            # For now, lists will remain empty.

        # Game factory path: TOML only (must be present for wwi_two_player)
        self.game_factory_path: Optional[str] = self.get_toml_value("scenario.game_factory", None)
        self.game_factory: Optional[Callable[..., "Game"]] = None

        if self.game_factory_path:
            if self.game_factory_path in SCENARIO_REGISTRY:
                self.game_factory = SCENARIO_REGISTRY[self.game_factory_path]
                logger.info(f"Loaded scenario factory '{self.game_factory_path}' from SCENARIO_REGISTRY.")
            else:
                # Error if the specified factory path is not in the registry
                available_scenarios = list(SCENARIO_REGISTRY.keys())
                err_msg = (
                    f"Scenario factory '{self.game_factory_path}' (from TOML 'scenario.game_factory') "
                    f"not found in SCENARIO_REGISTRY. Available registered scenarios: {available_scenarios}."
                )
                logger.error(err_msg)
                raise ValueError(err_msg)
        else:
            # Error if no game_factory_path is provided in TOML (unless in mock mode)
            if self._in_mock_mode:
                logger.warning(
                    "No 'scenario.game_factory' provided in TOML, but running in mock/test mode – proceeding without a game factory."
                )
                self.game_factory = None
            else:
                logger.error("Missing 'scenario.game_factory' in TOML configuration. This is required.")
                raise ValueError("Missing 'scenario.game_factory' in TOML configuration.")

        # scenario_name_from_toml is not used anymore for factory loading, but can be logged.
        self.scenario_name_from_toml: Optional[str] = self.get_toml_value("scenario.name", None)

        # --- Model configuration is now part of agent definitions in the main TOML ---
        # self.llm_models_list is populated by _parse_agent_data_from_toml

        # Generate game_id: auto-generated from prefix in TOML and current time
        self.current_datetime_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.game_id: str = f"{self.game_id_prefix}_{self.current_datetime_str}"

        # Configure paths
        # base_log_dir: Default value
        self.base_log_dir = DEFAULT_BASE_LOG_DIR

        from .logging_setup import get_log_paths  # Local import

        # log_paths are now generated by self.get_log_paths() which uses self.base_log_dir and self.game_id
        # self.log_paths is assigned later, before calling setup_logging.
        # The direct call to get_log_paths here is for intermediate path attributes.
        # This will be streamlined. For now, let's ensure these attributes are set using the instance's state.
        temp_log_paths = get_log_paths(self.game_id, self.base_log_dir)
        self.game_id_specific_log_dir: str = temp_log_paths["game_id_specific_log_dir"]
        self.llm_log_path: str = temp_log_paths["llm_log_path"]
        self.general_log_path: str = temp_log_paths["general_log_path"]
        self.results_dir: str = temp_log_paths["results_dir"]
        self.manifestos_dir: str = temp_log_paths["manifestos_dir"]

        if self.log_to_file:
            os.makedirs(self.game_id_specific_log_dir, exist_ok=True)
            os.makedirs(self.results_dir, exist_ok=True)
            # manifestos_dir is part of results_dir, so this line is not strictly needed if results_dir is created.
            # However, explicit creation doesn't hurt.
            os.makedirs(self.manifestos_dir, exist_ok=True)

        from .game_history import GameHistory

        self.game_history: "GameHistory" = GameHistory()
        self.game_instance: Optional["Game"] = None

        self.power_to_agent_id_map: Dict[str, str] = {}
        self.agent_to_powers_map: Dict[str, List[str]] = {}

        # --- Setup Logging and Paths ---
        # The logging setup needs to happen after we've determined the log_level and log_to_file status.
        # game_id is already generated.
        # base_log_dir is already set.

        # Get log paths *before* setting up logging
        # self.log_paths will store the dictionary returned by get_log_paths()
        # self.get_log_paths() now uses the instance's self.base_log_dir and self.game_id
        self.log_paths: Dict[str, str] = self.get_log_paths()

        # Call the standalone logging setup function
        setup_logging(self.log_level, self.log_to_file, self.log_paths)

        self.log_configuration()

    def log_configuration(self):
        logger.info("Game Configuration Initialized (TOML-driven):")
        logger.info(f"  Game Config File: {self.game_config_file_path}")
        logger.info(f"  Game ID: {self.game_id}") # Already logged by __init__ calling this
        logger.info(f"  Log Level: {self.log_level}")
        logger.info(f"  Log to File: {self.log_to_file}")
        if self.log_to_file:
            logger.info(f"  Base Log Directory: {self.base_log_dir}") # This is now DEFAULT_BASE_LOG_DIR
            logger.info(f"  Game-Specific Log Directory: {self.game_id_specific_log_dir}")
            logger.info(f"  LLM Interaction Log: {self.llm_log_path}")
            logger.info(f"  General Log File: {self.general_log_path}")
            logger.info(f"  Results Directory: {self.results_dir}")
            logger.info(f"  Manifestos Directory: {self.manifestos_dir}")

        logger.info(f"  Negotiation Style: {self.negotiation_style}")
        if self.max_phases:
            logger.info(f"  Maximum Game Phases: {self.max_phases}")
        logger.info(f"  Development Mode: {self.dev_mode}")
        logger.info(f"  Verbose LLM Debug Logging: {self.verbose_llm_debug}")

        if self.players_list:
            logger.info(f"  TOML Parsed Agent IDs (Players List): {self.players_list}")
        if self.agent_types_list:
            logger.info(f"  TOML Parsed Agent Types: {self.agent_types_list}")
        if self.llm_models_list:
            logger.info(f"  TOML Parsed Agent LLM Models: {self.llm_models_list}")
        if self.agent_countries_list:
            logger.info(f"  TOML Parsed Agent Countries: {self.agent_countries_list}")
        if self.bloc_definitions_list:
            logger.info(f"  TOML Parsed Bloc Definitions: {self.bloc_definitions_list}")

        # Logging for scenario/factory information
        # self.game_factory_path is what was read from TOML "scenario.game_factory"
        if self.game_factory_path:
            logger.info(
                f"  Game Factory Path (from TOML 'scenario.game_factory'): {self.game_factory_path}"
            )
        # self.scenario_name_from_toml is what was read from TOML "scenario.name" (for informational purposes)
        if self.scenario_name_from_toml: # Log if present
            logger.info(f"  Scenario Name (from TOML 'scenario.name'): {self.scenario_name_from_toml}")

        if self.game_factory:
            factory_module = getattr(self.game_factory, "__module__", "N/A")
            factory_name = getattr(self.game_factory, "__name__", "N/A")
            # Source is always SCENARIO_REGISTRY now with the simplified logic
            source_info = "from SCENARIO_REGISTRY"
            logger.info(f"  Resolved Game Factory: {factory_module}.{factory_name} ({source_info})")
        else:
            # This case should ideally be prevented by the error checks in __init__ (e.g. if _in_mock_mode)
            logger.warning(
                "  Game Factory: NOT RESOLVED (This might be expected in mock/test mode, or indicates an issue)"
            )

    def _parse_agent_data_from_toml(self, agent_entries: List[Dict[str, Any]]) -> None:
        """Parses the 'agents' list from pre-fetched TOML configuration data."""
        if not isinstance(agent_entries, list):
            logger.warning(
                "'agents' data provided to _parse_agent_data_from_toml is not a list. Skipping agent parsing."
            )
            return

        temp_players_list: List[str] = []
        temp_agent_types_list: List[str] = []
        temp_llm_models_list: List[str] = []
        temp_agent_countries_list: List[Optional[str]] = []  # To store country for llm, neutral, null agents
        temp_bloc_definitions_map: Dict[str, List[str]] = {}

        for agent_entry in agent_entries:
            if not isinstance(agent_entry, dict):
                logger.warning(f"Invalid agent entry in TOML (not a dict): {agent_entry}")
                continue

            agent_id = agent_entry.get("id")
            agent_type = agent_entry.get("type")
            model = agent_entry.get("model")
            country = agent_entry.get("country")  # Get country field

            if not agent_id or not agent_type:
                logger.warning(f"Agent entry in TOML missing 'id' or 'type': {agent_entry}")
                continue

            temp_players_list.append(agent_id)
            agent_type_lower = agent_type.lower()
            temp_agent_types_list.append(agent_type_lower)

            if agent_type_lower in ["llm", "bloc_llm"]:
                temp_llm_models_list.append(model if model else "")
            else:
                temp_llm_models_list.append("")

            if agent_type_lower in ["llm", "neutral", "null"]:
                temp_agent_countries_list.append(country if country else None)
            else:
                temp_agent_countries_list.append(None)  # No specific country for bloc_llm itself

            if agent_type_lower == "bloc_llm":
                powers = agent_entry.get("powers")
                if isinstance(powers, list) and all(isinstance(p, str) for p in powers):
                    temp_bloc_definitions_map[agent_id] = powers
                else:
                    logger.warning(
                        f"Bloc agent '{agent_id}' in TOML missing valid 'powers' list. This bloc might not be correctly configured."
                    )

        temp_bloc_definitions_list = []
        for bloc_name, bloc_powers in temp_bloc_definitions_map.items():
            temp_bloc_definitions_list.append(f"{bloc_name}:{';'.join(bloc_powers)}")

        # Assign to self if parsing was successful
        self.players_list = temp_players_list
        self.agent_types_list = temp_agent_types_list
        self.llm_models_list = temp_llm_models_list
        self.agent_countries_list = temp_agent_countries_list  # Store the parsed countries
        self.bloc_definitions_list = temp_bloc_definitions_list

        # Log what was parsed
        logger.info(f"Parsed from TOML - Players: {self.players_list}")
        logger.info(f"Parsed from TOML - Agent Types: {self.agent_types_list}")
        logger.info(f"Parsed from TOML - LLM Models: {self.llm_models_list}")
        logger.info(f"Parsed from TOML - Agent Countries: {self.agent_countries_list}")
        logger.info(f"Parsed from TOML - Bloc Definitions: {self.bloc_definitions_list}")

    def get_toml_value(self, key_path: str, default: Optional[Any] = None) -> Any:
        """Safely retrieve a value from the loaded TOML data using a dot-separated path."""
        keys = key_path.split(".")
        value = self._raw_toml_config
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def get_log_paths(self) -> Dict[str, str]:
        """
        Generates and returns a dictionary of required log paths using instance attributes
        self.base_log_dir and self.game_id.
        """
        # self.base_log_dir is now set to DEFAULT_BASE_LOG_DIR in __init__
        # self.game_id is also set in __init__

        # Ensure the base directory exists (though get_log_paths in logging_setup also does this)
        os.makedirs(self.base_log_dir, exist_ok=True)

        # Define paths for the full log and a separate error log.
        # These filenames are based on the structure expected by the original logging_setup.get_log_paths
        log_filename = f"{self.game_id}_full.log"
        error_log_filename = f"{self.game_id}_error.log"

        # game_id_specific_log_dir is where all logs for a game_id go.
        # In the original logging_setup.get_log_paths, this was os.path.join(base_log_dir, game_id)
        # However, the setup_logging function expects 'full_log_path' and 'error_log_path' to be top-level
        # in the base_log_dir, not inside a game_id subdirectory created by *this* function.
        # The GameConfig class itself later creates game_id_specific_log_dir for results, manifestos etc.
        # For now, to match the simplified setup_logging which takes full paths:
        paths = {
            "base_log_dir": self.base_log_dir, # For reference
            "game_id_specific_log_dir": os.path.join(self.base_log_dir, self.game_id), # For results/manifestos
            "full_log_path": os.path.join(self.base_log_dir, log_filename), # For setup_logging
            "error_log_path": os.path.join(self.base_log_dir, error_log_filename), # For setup_logging
            # The following are derived based on the original logging_setup.get_log_paths structure
            "llm_log_path": os.path.join(self.base_log_dir, self.game_id, f"{self.game_id}_llm.log"),
            "general_log_path": os.path.join(self.base_log_dir, self.game_id, f"{self.game_id}_general.log"),
            "results_dir": os.path.join(self.base_log_dir, self.game_id, "results"),
            "manifestos_dir": os.path.join(self.base_log_dir, self.game_id, "results", "manifestos"),

        }
        return paths

    def build_and_validate_agent_maps(
        self,
        game_instance: "Game",
        agent_configurations: Dict[str, Dict[str, Any]],
        initialized_agents: Dict[str, "BaseAgent"],  # type: ignore # BaseAgent might not be defined if imports are minimal
    ) -> None:
        """
        Validates the agent configuration from the TOML file and CLI against the actual game powers.
        """
        if not game_instance:
            logger.error(
                "Game instance is required for building and validating agent maps."
            )
            raise ValueError("Game instance not provided.")

        game_powers = list(game_instance.powers.keys())
        num_game_powers = len(game_powers)
        num_agents_defined = len(self.players_list)

        logger.info(f"Validating {num_agents_defined} agent definitions against {num_game_powers} powers in the game: {game_powers}")

        # Special handling for WWI two-player scenario where players are blocs
        is_wwi_scenario = self.game_factory_path and "wwi_two_player" in self.game_factory_path
        if is_wwi_scenario:
            # Check if we have bloc definitions that cover all powers
            bloc_powers = set()
            power_to_model_map = {}  # Map from power name to model ID
            agent_to_powers_map = {}  # Map from agent ID to list of powers
            power_to_agent_id_map = {}  # Map from power name to agent ID
            
            # This local map is not assigned to any instance variable anymore.
            # It was previously assigned to self.powers_and_models.
            # For now, its calculation is kept, but it might be removable if not used by other logic.
            power_to_model_map_local = {}

            for agent_id, config in agent_configurations.items():
                if config.get("type") == "bloc_llm" and "controlled_powers" in config:
                    controlled_powers = config["controlled_powers"]
                    bloc_powers.update(controlled_powers)
                    agent_to_powers_map[agent_id] = controlled_powers
                    
                    model_id = config.get("model_id")
                    if model_id:
                        for power in controlled_powers:
                            power_to_model_map_local[power] = model_id # Populate local map
                            power_to_agent_id_map[power] = agent_id
                            
                elif config.get("type") == "null" and "country" in config:
                    country = config["country"]
                    bloc_powers.add(country)
                    agent_to_powers_map[agent_id] = [country]
                    power_to_agent_id_map[country] = agent_id
            
            missing_powers = set(game_powers) - bloc_powers
            if missing_powers:
                logger.warning(f"WWI Scenario: Some game powers are not covered by any bloc or null agent: {missing_powers}")
            
            # Set the instance maps for the WWI scenario
            self.agent_to_powers_map = agent_to_powers_map
            self.power_to_agent_id_map = power_to_agent_id_map
            
            # Log the populated maps
            # logger.info(f"WWI two-player scenario: Local powers to models map: {power_to_model_map_local}") # Optional: log local map if needed for debugging
            logger.info(f"WWI two-player scenario: Agent to powers map set: {self.agent_to_powers_map}")
            logger.info(f"WWI two-player scenario: Power to agent ID map set: {self.power_to_agent_id_map}")
            
            logger.info("WWI two-player scenario detected. Agent maps populated based on bloc and null agent definitions.")
            return # Skip standard validation for WWI scenario
        else:
            # This part should not be reached if only wwi_two_player is supported.
            # If other scenarios were to be supported, they would need their own validation or this would need to be more generic.
            logger.warning(
                f"Non-WWI two-player scenario ('{self.game_factory_path}') detected. "
                "Standard agent map validation and building is currently removed. "
                "Ensure this scenario doesn't require these maps or add specific handling."
            )
            # Clear any potentially stale maps from previous runs or if class is reused (though typically not)
            self.agent_to_powers_map = {}
            self.power_to_agent_id_map = {}
            # Other maps like self.agent_power_map, self.power_agent_map, self.agent_type_map, self.power_model_map
            # were part of the removed standard validation and are not set here.


def dummy_factory_for_test():
    """Dummy factory for testing purposes."""
    pass


if __name__ == "__main__":
    dummy_toml_content_main = """
[scenario]
# game_factory = "wwi_two_player" # Assuming SCENARIO_REGISTRY is populated by scenarios.py
# For a simple test that doesn't rely on scenarios.py being found by THIS script's execution path:
game_factory = "ai_diplomacy.game_config.dummy_factory_for_test" # A known local path

[game_settings]
num_players = 7
game_id_prefix = "main_test"

[logging]
log_level = "INFO"
log_to_file = false # Don't create files for simple test

[dev_settings]
dev_mode = true

agents = [
    { id = "AGENT_ONE", type = "llm", model = "model_alpha" }
]
"""
    from diplomacy import Game  # Ensure Game is imported for the dummy factory

    def dummy_factory_for_test():
        logger.info("Dummy factory for test called!")
        return Game()

    if "SCENARIO_REGISTRY" in globals():
        SCENARIO_REGISTRY["ai_diplomacy.game_config.dummy_factory_for_test"] = dummy_factory_for_test
    else:  # If SCENARIO_REGISTRY wasn't imported (e.g. file run directly)
        SCENARIO_REGISTRY = {"ai_diplomacy.game_config.dummy_factory_for_test": dummy_factory_for_test}

    dummy_toml_path_main = "temp_main_test_config.toml"
    with open(dummy_toml_path_main, "w") as f:
        f.write(dummy_toml_content_main)

    args_dict_main = {
        "game_config_file": dummy_toml_path_main,
        "log_level": None,
        "log_dir": None,
        "game_id": None,
    }
    test_args_main = argparse.Namespace(**args_dict_main)

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)",
    )

    logger.info("--- Testing GameConfig Instantiation with dummy factory ---")
    try:
        config = GameConfig(test_args_main)
        logger.info(f"GameConfig instantiated successfully. Game ID: {config.game_id}")
        assert config.game_factory is not None, "Game factory should be loaded"
        if config.game_factory is not None:  # mypy guard
            assert config.game_factory.__name__ == "dummy_factory_for_test", "Incorrect factory loaded"
            logger.info(f"Successfully loaded game factory: {config.game_factory.__name__}")

        # Test a case where factory is expected to fail
        error_toml_content = """
[scenario]
game_factory = "this.does.not.exist"
agents = []
        """
        error_toml_path = "temp_error_test_config.toml"
        with open(error_toml_path, "w") as f:
            f.write(error_toml_content)
        error_args = argparse.Namespace(
            game_config_file=error_toml_path, log_level=None, log_dir=None, game_id=None
        )
        logger.info("--- Testing GameConfig with non-existent factory (expect ValueError) ---")
        try:
            GameConfig(error_args)
            logger.error("Error test FAILED: ValueError not raised for non-existent factory.")
        except ValueError:
            logger.info("Error test PASSED: ValueError raised as expected.")
        finally:
            if os.path.exists(error_toml_path):
                os.remove(error_toml_path)

    except Exception as e:
        logger.error(f"Error during GameConfig __main__ test: {e}", exc_info=True)
    finally:
        if os.path.exists(dummy_toml_path_main):
            os.remove(dummy_toml_path_main)
        # Clean up the dummy factory from SCENARIO_REGISTRY if it was added for the test
        if "ai_diplomacy.game_config.dummy_factory_for_test" in SCENARIO_REGISTRY:
            del SCENARIO_REGISTRY["ai_diplomacy.game_config.dummy_factory_for_test"]

    logger.info("--- GameConfig __main__ Test Complete ---")
