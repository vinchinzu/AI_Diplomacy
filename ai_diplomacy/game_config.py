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
DEFAULT_NUM_PLAYERS = 7
DEFAULT_NUM_NEGOTIATION_ROUNDS = 3
DEFAULT_NEGOTIATION_STYLE = "simultaneous"
DEFAULT_MAX_DIARY_TOKENS = 6500
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

        self.power_name: Optional[str] = getattr(args, "power_name", None) or self.get_toml_value(
            "scenario.power_name", None
        )
        self.model_id: Optional[str] = getattr(args, "model_id", None) or self.get_toml_value(
            "scenario.model_id", None
        )

        self.num_players: int = getattr(args, "num_players", None) or self.get_toml_value(
            "game_settings.num_players", DEFAULT_NUM_PLAYERS
        )
        self.game_id_prefix: str = self.get_toml_value("game_settings.game_id_prefix", DEFAULT_GAME_ID_PREFIX)
        self.perform_planning_phase: bool = self.get_toml_value("game_settings.perform_planning_phase", False)
        self.num_negotiation_rounds: int = self.get_toml_value(
            "game_settings.num_negotiation_rounds", DEFAULT_NUM_NEGOTIATION_ROUNDS
        )
        self.negotiation_style: str = self.get_toml_value(
            "game_settings.negotiation_style", DEFAULT_NEGOTIATION_STYLE
        )
        self.max_years: Optional[int] = self.get_toml_value("game_settings.max_years", None)
        self.max_phases: Optional[int] = self.get_toml_value("game_settings.max_phases", None)
        self.max_diary_tokens: int = self.get_toml_value(
            "game_settings.max_diary_tokens", DEFAULT_MAX_DIARY_TOKENS
        )
        self.perform_diary_generation: bool = self.get_toml_value(
            "game_settings.perform_diary_generation", True
        )
        self.perform_goal_analysis: bool = self.get_toml_value("game_settings.perform_goal_analysis", True)

        self.dev_mode: bool = self.get_toml_value("dev_settings.dev_mode", False)
        self.verbose_llm_debug: bool = self.get_toml_value("dev_settings.verbose_llm_debug", False)

        # Log to file logic: ENV > TOML > dev_mode consideration > Default
        log_to_file_env = os.getenv("LOG_TO_FILE")
        log_to_file_toml = self.get_toml_value("logging.log_to_file", None)

        if log_to_file_env == "1":
            self.log_to_file: bool = True
        elif log_to_file_toml is not None:
            self.log_to_file: bool = bool(log_to_file_toml)
        elif self.dev_mode:  # If dev_mode is true (from TOML) and no other setting, log to file is off
            self.log_to_file: bool = False
        else:  # Default if not dev_mode and no other specifier
            self.log_to_file: bool = True

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

        # Game factory path: CLI (via args from lm_game.py) > TOML > Default (None)
        cli_game_factory_path_override = getattr(args, "game_factory_path", None)
        if cli_game_factory_path_override:
            self.game_factory_path: Optional[str] = cli_game_factory_path_override
            logger.info(f"Using game_factory_path from CLI override: {self.game_factory_path}")
        else:
            self.game_factory_path: Optional[str] = self.get_toml_value("scenario.game_factory", None)
            if self.game_factory_path:
                logger.info(f"Using game_factory_path from TOML: {self.game_factory_path}")
            else:
                logger.info("No game_factory_path specified in CLI or TOML.")

        self.scenario_name_from_toml: Optional[str] = self.get_toml_value("scenario.name", None)
        self.game_factory: Optional[Callable[..., "Game"]] = None  # Initialized attribute

        if self.game_factory_path:
            if self.game_factory_path in SCENARIO_REGISTRY:
                self.game_factory = SCENARIO_REGISTRY[self.game_factory_path]
                logger.info(f"Loaded scenario factory '{self.game_factory_path}' from SCENARIO_REGISTRY.")
            else:
                logger.warning(
                    f"Scenario factory '{self.game_factory_path}' not found in SCENARIO_REGISTRY. "
                    "Attempting dynamic import as a fallback."
                )
                try:
                    # Try splitting by '.' first, then by ':' if needed
                    if "." in self.game_factory_path:
                        parts = self.game_factory_path.rsplit(".", 1)
                        if len(parts) == 2:
                            module_str, func_str = parts
                        else:  # Fallback or handle error if '.' is present but not as a separator
                            logger.warning(
                                f"Path '{self.game_factory_path}' contains '.' but not in a module.function format. Trying ':' next."
                            )
                            if ":" in self.game_factory_path:
                                module_str, func_str = self.game_factory_path.rsplit(":", 1)
                            else:
                                raise ValueError("Path does not contain a valid separator ('.' or ':')")
                    elif ":" in self.game_factory_path:
                        module_str, func_str = self.game_factory_path.rsplit(":", 1)
                    else:
                        raise ValueError(
                            f"Scenario factory path '{self.game_factory_path}' does not contain '.' or ':' to separate module and function."
                        )

                    module = importlib.import_module(module_str)
                    self.game_factory = getattr(module, func_str)
                    logger.info(
                        f"Successfully dynamically imported scenario factory: {self.game_factory_path}"
                    )
                except (ImportError, AttributeError, ValueError) as e:
                    logger.error(
                        f"Failed to dynamically import scenario factory '{self.game_factory_path}'. "
                        f"It was not in the registry either. Error: {e}"
                    )
                    available_scenarios = list(SCENARIO_REGISTRY.keys())
                    raise ValueError(
                        f"Scenario factory '{self.game_factory_path}' not found in SCENARIO_REGISTRY "
                        f"and could not be dynamically imported. "
                        f"Available registered scenarios: {available_scenarios}. Import error: {e}"
                    ) from e
        elif self.scenario_name_from_toml and self.scenario_name_from_toml in SCENARIO_REGISTRY:
            # Fallback to scenario.name if game_factory_path is not provided but name is, and it's in registry
            self.game_factory_path = self.scenario_name_from_toml  # Update path for consistency
            self.game_factory = SCENARIO_REGISTRY[self.scenario_name_from_toml]
            logger.info(
                f"Used 'scenario.name' ('{self.scenario_name_from_toml}') to load factory "
                "from SCENARIO_REGISTRY as 'scenario.game_factory' was not set."
            )
        else:
            # Error if no factory could be resolved based on the inputs
            if (
                self.game_factory_path or self.scenario_name_from_toml
            ):  # If either was specified but resolution failed
                available_scenarios = list(SCENARIO_REGISTRY.keys())
                err_msg = (
                    f"A scenario was specified ('{self.game_factory_path or self.scenario_name_from_toml}') "
                    f"but could not be resolved from the SCENARIO_REGISTRY or via dynamic import. "
                    f"Available registered scenarios: {available_scenarios}."
                )
                logger.error(err_msg)
                raise ValueError(err_msg)
            else:  # Neither game_factory_path nor scenario_name_from_toml was specified
                if self._in_mock_mode:
                    logger.warning(
                        "No scenario factory information found, but running in mock/test mode – proceeding without a game factory."
                    )
                    self.game_factory = None  # Explicitly set to None for clarity
                else:
                    logger.error(
                        "No 'scenario.game_factory' or 'scenario.name' (pointing to a registered scenario) "
                        "provided in the TOML configuration. Cannot determine game factory."
                    )
                    raise ValueError(
                        "A game factory (via 'scenario.game_factory' or 'scenario.name' in TOML) is required."
                    )

        # --- Model configuration is now part of agent definitions in the main TOML ---
        # Removed self.models_config_path, self.power_model_assignments, self.default_model_from_config
        # self.llm_models_list is populated by _parse_agent_data_from_toml

        # Generate game_id: CLI override > TOML > auto-generated
        self.current_datetime_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        cli_game_id_override = getattr(args, "game_id", None)
        toml_game_id = self.get_toml_value("game_settings.game_id", None)

        if cli_game_id_override:
            self.game_id: str = cli_game_id_override
        elif toml_game_id:
            self.game_id: str = toml_game_id
        else:
            self.game_id: str = f"{self.game_id_prefix}_{self.current_datetime_str}"

        # Configure paths
        # base_log_dir: CLI override > TOML > Default
        cli_log_dir_override = getattr(args, "log_dir", None)
        toml_base_log_dir = self.get_toml_value("logging.base_log_dir", None)

        if cli_log_dir_override:
            self.base_log_dir = cli_log_dir_override
            # If cli_log_dir_override already contains the game_id, adjust base_log_dir
            if (
                self.game_id in cli_log_dir_override
                and os.path.basename(cli_log_dir_override) == self.game_id
            ):
                self.base_log_dir = os.path.dirname(cli_log_dir_override)
        elif toml_base_log_dir:
            self.base_log_dir = toml_base_log_dir
        else:
            self.base_log_dir = DEFAULT_BASE_LOG_DIR

        from .logging_setup import get_log_paths  # Local import

        log_paths = get_log_paths(self.game_id, self.base_log_dir)
        self.game_id_specific_log_dir: str = log_paths["game_id_specific_log_dir"]
        self.llm_log_path: str = log_paths["llm_log_path"]
        self.general_log_path: str = log_paths["general_log_path"]
        self.results_dir: str = log_paths["results_dir"]
        self.manifestos_dir: str = log_paths["manifestos_dir"]

        if self.log_to_file:
            os.makedirs(self.game_id_specific_log_dir, exist_ok=True)
            os.makedirs(self.results_dir, exist_ok=True)
            os.makedirs(self.manifestos_dir, exist_ok=True)

        from .game_history import GameHistory

        self.game_history: "GameHistory" = GameHistory()
        self.game_instance: Optional["Game"] = None
        # Removed self.powers_and_models - model info is now tied to agents via llm_models_list
        # Removed self.agents

        self.power_to_agent_id_map: Dict[str, str] = {}
        self.agent_to_powers_map: Dict[str, List[str]] = {}

        # --- Additional convenience attributes (primarily used in unit tests & model utils) ---
        # These may be provided via CLI args in tests even when absent from TOML.
        self.exclude_powers: Optional[List[str]] = getattr(args, "exclude_powers", None)
        self.fixed_models: Optional[List[str]] = getattr(args, "fixed_models", None)
        self.randomize_fixed_models: bool = bool(getattr(args, "randomize_fixed_models", False))
        # Mapping of power -> model from an optional models.toml file (used by model_utils tests).
        # Populated later if a models file is loaded; default to empty dict to prevent AttributeError.
        self.power_model_assignments: Dict[str, str] = {}
        self.default_model_from_config: Optional[str] = None

        # Attempt to load an optional models configuration file if provided via CLI args.
        models_config_file_cli: Optional[str] = getattr(args, "models_config_file", None)
        if models_config_file_cli:
            try:
                models_cfg_data = toml.load(models_config_file_cli)
                if isinstance(models_cfg_data, dict):
                    self.power_model_assignments = models_cfg_data.get("powers", {})
                    self.default_model_from_config = models_cfg_data.get("default_model", None)
                logger.info(
                    f"Loaded {len(self.power_model_assignments)} power model assignments from '{models_config_file_cli}'."
                )
            except FileNotFoundError:
                logger.warning(
                    f"models_config_file '{models_config_file_cli}' not found – proceeding without explicit power model assignments."
                )
            except toml.TomlDecodeError as e:
                logger.error(
                    f"Error parsing TOML models config '{models_config_file_cli}': {e}",
                    exc_info=True,
                )
            except Exception as e:
                logger.error(
                    f"Unexpected error reading models config '{models_config_file_cli}': {e}",
                    exc_info=True,
                )

        # --- Setup Logging and Paths ---
        # The logging setup needs to happen after we've determined the log_level and log_to_file status.
        # It also needs a game_id, which we will generate now.
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.game_id: str = f"{self.game_id_prefix}_{timestamp}"

        # Get log paths *before* setting up logging
        self.log_paths: Dict[str, str] = self.get_log_paths()

        # Call the standalone logging setup function
        setup_logging(self.log_level, self.log_to_file, self.log_paths)

        self.log_configuration()

    def log_configuration(self):
        logger.info("Game Configuration Initialized (TOML-driven):")
        logger.info(f"  Game Config File: {self.game_config_file_path}")
        logger.info(f"  Game ID: {self.game_id}")
        logger.info(f"  Log Level: {self.log_level}")
        # num_players is now what's set in TOML, or default. Actual player count from agent defs.
        logger.info(f"  Configured Number of Players (game_settings.num_players): {self.num_players}")
        logger.info(f"  Log to File: {self.log_to_file}")
        if self.log_to_file:
            logger.info(f"  Base Log Directory: {self.base_log_dir}")
            logger.info(f"  Game-Specific Log Directory: {self.game_id_specific_log_dir}")
            logger.info(f"  LLM Interaction Log: {self.llm_log_path}")
            logger.info(f"  General Log File: {self.general_log_path}")
            logger.info(f"  Results Directory: {self.results_dir}")
            logger.info(f"  Manifestos Directory: {self.manifestos_dir}")

        if self.power_name and self.model_id:  # For single agent test scenarios
            logger.info(f"  Single Power Mode Target: {self.power_name} with model {self.model_id}")

        logger.info(f"  Perform Planning Phase: {self.perform_planning_phase}")
        logger.info(f"  Number of Negotiation Rounds: {self.num_negotiation_rounds}")
        logger.info(f"  Negotiation Style: {self.negotiation_style}")
        # Removed fixed_models, randomize_fixed_models, exclude_powers logging
        if self.max_years:
            logger.info(f"  Maximum Game Years: {self.max_years}")
        if self.max_phases:
            logger.info(f"  Maximum Game Phases: {self.max_phases}")
        logger.info(f"  Development Mode: {self.dev_mode}")
        logger.info(f"  Verbose LLM Debug Logging: {self.verbose_llm_debug}")
        logger.info(f"  Max Diary Tokens: {self.max_diary_tokens}")

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
        original_factory_path_from_toml = self.get_toml_value("scenario.game_factory", None)
        original_scenario_name_from_toml = self.get_toml_value("scenario.name", None)

        if original_factory_path_from_toml:
            logger.info(
                f"  Game Factory Path (from TOML 'scenario.game_factory'): {original_factory_path_from_toml}"
            )
        if original_scenario_name_from_toml:
            logger.info(f"  Scenario Name (from TOML 'scenario.name'): {original_scenario_name_from_toml}")

        if self.game_factory:
            factory_module = getattr(self.game_factory, "__module__", "N/A")
            factory_name = getattr(self.game_factory, "__name__", "N/A")

            source_info = "unknown source"
            if (
                self.game_factory_path
            ):  # self.game_factory_path is now the key/path that successfully resolved
                if (
                    self.game_factory_path in SCENARIO_REGISTRY
                    and SCENARIO_REGISTRY[self.game_factory_path] == self.game_factory
                ):
                    source_info = "from SCENARIO_REGISTRY"
                    if (
                        original_factory_path_from_toml != self.game_factory_path
                        and original_scenario_name_from_toml == self.game_factory_path
                    ):
                        source_info += " (using 'scenario.name')"
                else:  # Must have been dynamically imported
                    source_info = "dynamically imported"
            logger.info(f"  Resolved Game Factory: {factory_module}.{factory_name} ({source_info})")
        else:
            # This case should ideally be prevented by the error checks in __init__
            logger.error(
                "  Game Factory: NOT RESOLVED (This indicates an issue with initialization logic if reached)"
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
        Generates and returns a dictionary of required log paths.
        """
        base_log_dir = self.get_toml_value("logging.base_log_dir", DEFAULT_BASE_LOG_DIR)

        # Ensure the base directory exists
        os.makedirs(base_log_dir, exist_ok=True)

        # Define paths for the full log and a separate error log.
        log_filename = f"{self.game_id}_full.log"
        error_log_filename = f"{self.game_id}_error.log"

        paths = {
            "base_log_dir": base_log_dir,
            "full_log_path": os.path.join(base_log_dir, log_filename),
            "error_log_path": os.path.join(base_log_dir, error_log_filename),
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
            
            for agent_id, config in agent_configurations.items():
                if config.get("type") == "bloc_llm" and "controlled_powers" in config:
                    controlled_powers = config["controlled_powers"]
                    bloc_powers.update(controlled_powers)
                    agent_to_powers_map[agent_id] = controlled_powers
                    
                    # Map each power to its model and agent ID
                    model_id = config.get("model_id")
                    if model_id:
                        for power in controlled_powers:
                            power_to_model_map[power] = model_id
                            power_to_agent_id_map[power] = agent_id
                            
                elif config.get("type") == "null" and "country" in config:
                    country = config["country"]
                    bloc_powers.add(country)
                    agent_to_powers_map[agent_id] = [country]
                    power_to_agent_id_map[country] = agent_id
            
            missing_powers = set(game_powers) - bloc_powers
            if missing_powers:
                logger.warning(f"Some powers are not covered by any bloc: {missing_powers}")
            
            # Set the maps for the WWI scenario
            self.powers_and_models = power_to_model_map
            self.agent_to_powers_map = agent_to_powers_map
            self.power_to_agent_id_map = power_to_agent_id_map
            
            logger.info(f"WWI two-player scenario: Powers to models map: {self.powers_and_models}")
            logger.info(f"WWI two-player scenario: Agent to powers map: {self.agent_to_powers_map}")
            logger.info(f"WWI two-player scenario: Power to agent ID map: {self.power_to_agent_id_map}")
            
            # Skip the standard validation for bloc-based scenarios
            logger.info("WWI two-player scenario detected. Skipping standard power validation.")
            return

        # Standard validation for non-bloc scenarios
        # Validation 1: Match between number of agents and game powers
        if num_agents_defined != num_game_powers:
            logger.warning(
                f"Mismatch: The number of agents defined ({num_agents_defined}) does not match the number of powers in the game ({num_game_powers}). "
                f"Agents: {self.players_list}, Powers: {game_powers}. "
                "This may lead to unassigned powers or unused agent configurations."
            )
            # Depending on strictness, could raise an error here.

        # Validation 2: Ensure all defined player names are valid powers in the game
        invalid_players = [p for p in self.players_list if p not in game_powers]
        if invalid_players:
            logger.error(
                f"Configuration Error: The following players defined in the config do not exist as powers in the game: {invalid_players}. Valid powers are: {game_powers}."
            )
            raise ValueError("Invalid player names found in agent configuration.")

        # Build the maps
        self.agent_power_map = {
            agent_id: power_name
            for agent_id, power_name in zip(
                initialized_agents.keys(), self.agent_countries_list
            )
            if power_name and power_name in game_powers
        }

        self.power_agent_map = {v: k for k, v in self.agent_power_map.items()}

        self.agent_type_map = {
            power: agent_type
            for power, agent_type in zip(self.players_list, self.agent_types_list)
        }

        # Create a map from power to its assigned LLM model
        self.power_model_map = {
            player: model
            for player, model in zip(self.players_list, self.llm_models_list)
            if model and player in game_powers
        }

        unassigned_powers = [p for p in game_powers if p not in self.power_agent_map]
        if unassigned_powers:
            logger.warning(
                f"The following powers do not have an agent assigned: {unassigned_powers}. "
                "They will be controlled by a default or Null agent if not handled."
            )

        logger.info(f"Agent-Power mapping created: {self.agent_power_map}")
        logger.info(f"Power-Agent mapping created: {self.power_agent_map}")
        logger.info(f"Power-AgentType mapping created: {self.agent_type_map}")
        logger.info(f"Power-Model mapping created: {self.power_model_map}")


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
