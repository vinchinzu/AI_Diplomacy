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
from typing import Optional, List, Dict, TYPE_CHECKING, Any, Callable # Added Callable
import toml
import importlib # Added importlib

logger = logging.getLogger(__name__)

# Import GameHistory and DiplomacyAgent only for type hinting if they are complex
# to avoid circular dependencies at runtime.
if TYPE_CHECKING:
    from diplomacy import Game # Game is already here for type hint
    from .game_history import GameHistory
    from .agents.base import BaseAgent

# Attempt to import SCENARIO_REGISTRY
try:
    from ..scenarios import SCENARIO_REGISTRY
except ImportError:
    logger.warning("Could not import SCENARIO_REGISTRY via 'from ..scenarios'. Trying 'from scenarios'.")
    try:
        from scenarios import SCENARIO_REGISTRY
    except ImportError:
        logger.error("Failed to import SCENARIO_REGISTRY. Registry-based scenario loading will fail.")
        SCENARIO_REGISTRY = {} # Define as empty to prevent NameError during runtime

# Default values that might be used if not in TOML
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_GAME_ID_PREFIX = "diplomacy_game"
DEFAULT_NUM_PLAYERS = 7
DEFAULT_NUM_NEGOTIATION_ROUNDS = 3
DEFAULT_NEGOTIATION_STYLE = "simultaneous"
DEFAULT_MAX_DIARY_TOKENS = 6500
DEFAULT_BASE_LOG_DIR = os.path.join(os.getcwd(), "logs")

__all__ = ["GameConfig"]


class GameConfig:
    # Class docstring already exists and is good.

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self._raw_toml_config: Dict[str, Any] = {}

        # --- Load Game Configuration TOML ---
        self.game_config_file_path: Optional[str] = getattr(args, "game_config_file", None)
        if self.game_config_file_path and os.path.exists(self.game_config_file_path):
            try:
                self._raw_toml_config = toml.load(self.game_config_file_path)
                logger.info(f"Loaded game configuration from TOML file: {self.game_config_file_path}")
            except toml.TomlDecodeError as e:
                logger.error(f"Error decoding TOML from game config file '{self.game_config_file_path}': {e}", exc_info=True)
                # Consider if this should be a fatal error, perhaps raise it
                raise
            except Exception as e:
                logger.error(f"Unexpected error loading game config file '{self.game_config_file_path}': {e}", exc_info=True)
                raise
        elif self.game_config_file_path:
            logger.error(f"Game configuration TOML file not found at '{self.game_config_file_path}'. This is required.")
            raise FileNotFoundError(f"Game configuration TOML file not found: {self.game_config_file_path}")
        else:
            logger.error("No game configuration TOML file provided via --game-config-file argument.")
            raise ValueError("Game configuration TOML file path is required.")

        # --- Determine configuration values: CLI (for overrides) > TOML > Default ---

        # Core settings from TOML, with potential CLI overrides for a few specific ones
        cli_log_level_override = getattr(args, "log_level", None)
        self.log_level: str = (cli_log_level_override or self.get_toml_value("logging.log_level", DEFAULT_LOG_LEVEL)).upper()

        self.power_name: Optional[str] = self.get_toml_value("scenario.power_name", None) # For single power scenarios
        self.model_id: Optional[str] = self.get_toml_value("scenario.model_id", None) # For single power scenarios

        self.num_players: int = self.get_toml_value("game_settings.num_players", DEFAULT_NUM_PLAYERS)
        self.game_id_prefix: str = self.get_toml_value("game_settings.game_id_prefix", DEFAULT_GAME_ID_PREFIX)
        self.perform_planning_phase: bool = self.get_toml_value("game_settings.perform_planning_phase", False)
        self.num_negotiation_rounds: int = self.get_toml_value("game_settings.num_negotiation_rounds", DEFAULT_NUM_NEGOTIATION_ROUNDS)
        self.negotiation_style: str = self.get_toml_value("game_settings.negotiation_style", DEFAULT_NEGOTIATION_STYLE)
        self.max_years: Optional[int] = self.get_toml_value("game_settings.max_years", None)
        self.max_diary_tokens: int = self.get_toml_value("game_settings.max_diary_tokens", DEFAULT_MAX_DIARY_TOKENS)

        self.dev_mode: bool = self.get_toml_value("dev_settings.dev_mode", False)
        self.verbose_llm_debug: bool = self.get_toml_value("dev_settings.verbose_llm_debug", False)


        # Log to file logic: ENV > TOML > dev_mode consideration > Default
        log_to_file_env = os.getenv("LOG_TO_FILE")
        log_to_file_toml = self.get_toml_value("logging.log_to_file", None)

        if log_to_file_env == "1":
            self.log_to_file: bool = True
        elif log_to_file_toml is not None:
            self.log_to_file: bool = bool(log_to_file_toml)
        elif self.dev_mode: # If dev_mode is true (from TOML) and no other setting, log to file is off
            self.log_to_file: bool = False
        else: # Default if not dev_mode and no other specifier
            self.log_to_file: bool = True


        # --- Agent and Player Configuration (from TOML only) ---
        self.players_list: List[str] = []
        self.agent_types_list: List[str] = []
        self.bloc_definitions_list: List[str] = []
        self.llm_models_list: List[str] = []
        self.agent_countries_list: List[Optional[str]] = [] # For llm, neutral, null agents

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
            logger.info(f"Using agent configurations from TOML file (source: '{toml_config_source_for_agents}').")
            self._parse_agent_data_from_toml(agent_entries_from_toml)
        else:
            logger.warning("No agent configurations found in TOML (checked 'dev_settings.agents' and 'agents'). Game might not function correctly without agent definitions.")
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
        self.game_factory: Optional[Callable[..., "Game"]] = None # Initialized attribute

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
                    if '.' in self.game_factory_path:
                        parts = self.game_factory_path.rsplit('.', 1)
                        if len(parts) == 2:
                            module_str, func_str = parts
                        else: # Fallback or handle error if '.' is present but not as a separator
                            logger.warning(f"Path '{self.game_factory_path}' contains '.' but not in a module.function format. Trying ':' next.")
                            if ':' in self.game_factory_path:
                                module_str, func_str = self.game_factory_path.rsplit(':', 1)
                            else:
                                raise ValueError("Path does not contain a valid separator ('.' or ':')")
                    elif ':' in self.game_factory_path:
                        module_str, func_str = self.game_factory_path.rsplit(':', 1)
                    else:
                        raise ValueError(f"Scenario factory path '{self.game_factory_path}' does not contain '.' or ':' to separate module and function.")
                    
                    module = importlib.import_module(module_str)
                    self.game_factory = getattr(module, func_str)
                    logger.info(f"Successfully dynamically imported scenario factory: {self.game_factory_path}")
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
            self.game_factory_path = self.scenario_name_from_toml # Update path for consistency
            self.game_factory = SCENARIO_REGISTRY[self.scenario_name_from_toml]
            logger.info(
                f"Used 'scenario.name' ('{self.scenario_name_from_toml}') to load factory "
                "from SCENARIO_REGISTRY as 'scenario.game_factory' was not set."
            )
        else:
            # Error if no factory could be resolved based on the inputs
            if self.game_factory_path or self.scenario_name_from_toml: # If either was specified but resolution failed
                available_scenarios = list(SCENARIO_REGISTRY.keys())
                err_msg = (
                    f"A scenario was specified ('{self.game_factory_path or self.scenario_name_from_toml}') "
                    f"but could not be resolved from the SCENARIO_REGISTRY or via dynamic import. "
                    f"Available registered scenarios: {available_scenarios}."
                )
                logger.error(err_msg)
                raise ValueError(err_msg)
            else: # Neither game_factory_path nor scenario_name_from_toml was specified
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
            if self.game_id in cli_log_dir_override and os.path.basename(cli_log_dir_override) == self.game_id:
                 self.base_log_dir = os.path.dirname(cli_log_dir_override)
        elif toml_base_log_dir:
            self.base_log_dir = toml_base_log_dir
        else:
            self.base_log_dir = DEFAULT_BASE_LOG_DIR
        
        from .logging_setup import get_log_paths # Local import

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

        if self.power_name and self.model_id: # For single agent test scenarios
            logger.info(
                f"  Single Power Mode Target: {self.power_name} with model {self.model_id}"
            )

        logger.info(f"  Perform Planning Phase: {self.perform_planning_phase}")
        logger.info(f"  Number of Negotiation Rounds: {self.num_negotiation_rounds}")
        logger.info(f"  Negotiation Style: {self.negotiation_style}")
        # Removed fixed_models, randomize_fixed_models, exclude_powers logging
        if self.max_years:
            logger.info(f"  Maximum Game Years: {self.max_years}")
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
        original_factory_path_from_toml = self.get_toml_value('scenario.game_factory', None)
        original_scenario_name_from_toml = self.get_toml_value('scenario.name', None)

        if original_factory_path_from_toml:
            logger.info(f"  Game Factory Path (from TOML 'scenario.game_factory'): {original_factory_path_from_toml}")
        if original_scenario_name_from_toml:
            logger.info(f"  Scenario Name (from TOML 'scenario.name'): {original_scenario_name_from_toml}")

        if self.game_factory:
            factory_module = getattr(self.game_factory, '__module__', 'N/A')
            factory_name = getattr(self.game_factory, '__name__', 'N/A')
            
            source_info = "unknown source"
            if self.game_factory_path: # self.game_factory_path is now the key/path that successfully resolved
                if self.game_factory_path in SCENARIO_REGISTRY and SCENARIO_REGISTRY[self.game_factory_path] == self.game_factory:
                     source_info = "from SCENARIO_REGISTRY"
                     if original_factory_path_from_toml != self.game_factory_path and original_scenario_name_from_toml == self.game_factory_path:
                         source_info += " (using 'scenario.name')"
                else: # Must have been dynamically imported
                    source_info = "dynamically imported"
            logger.info(f"  Resolved Game Factory: {factory_module}.{factory_name} ({source_info})")
        else:
            # This case should ideally be prevented by the error checks in __init__
            logger.error("  Game Factory: NOT RESOLVED (This indicates an issue with initialization logic if reached)")

    def _parse_agent_data_from_toml(self, agent_entries: List[Dict[str, Any]]) -> None:
        """Parses the 'agents' list from pre-fetched TOML configuration data."""
        if not isinstance(agent_entries, list):
            logger.warning("'agents' data provided to _parse_agent_data_from_toml is not a list. Skipping agent parsing.")
            return

        temp_players_list: List[str] = []
        temp_agent_types_list: List[str] = []
        temp_llm_models_list: List[str] = []
        temp_agent_countries_list: List[Optional[str]] = [] # To store country for llm, neutral, null agents
        temp_bloc_definitions_map: Dict[str, List[str]] = {}

        for agent_entry in agent_entries:
            if not isinstance(agent_entry, dict):
                logger.warning(f"Invalid agent entry in TOML (not a dict): {agent_entry}")
                continue

            agent_id = agent_entry.get("id")
            agent_type = agent_entry.get("type")
            model = agent_entry.get("model")
            country = agent_entry.get("country") # Get country field

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
                temp_agent_countries_list.append(None) # No specific country for bloc_llm itself

            if agent_type_lower == "bloc_llm":
                powers = agent_entry.get("powers")
                if isinstance(powers, list) and all(isinstance(p, str) for p in powers):
                    temp_bloc_definitions_map[agent_id] = powers
                else:
                    logger.warning(f"Bloc agent '{agent_id}' in TOML missing valid 'powers' list. This bloc might not be correctly configured.")
        
        # Convert bloc definitions map to the string list format if needed by other parts of the code
        # Or adjust AgentManager to directly use the map.
        # For now, reconstruct bloc_definitions_list if it was sourced from TOML.
        temp_bloc_definitions_list = []
        for bloc_name, bloc_powers in temp_bloc_definitions_map.items():
            temp_bloc_definitions_list.append(f"{bloc_name}:{';'.join(bloc_powers)}")

        # Assign to self if parsing was successful
        self.players_list = temp_players_list
        self.agent_types_list = temp_agent_types_list
        self.llm_models_list = temp_llm_models_list
        self.agent_countries_list = temp_agent_countries_list # Store the parsed countries
        self.bloc_definitions_list = temp_bloc_definitions_list
        
        # Log what was parsed
        logger.info(f"Parsed from TOML - Players: {self.players_list}")
        logger.info(f"Parsed from TOML - Agent Types: {self.agent_types_list}")
        logger.info(f"Parsed from TOML - LLM Models: {self.llm_models_list}")
        logger.info(f"Parsed from TOML - Agent Countries: {self.agent_countries_list}")
        logger.info(f"Parsed from TOML - Bloc Definitions: {self.bloc_definitions_list}")

    def get_toml_value(self, key_path: str, default: Optional[Any] = None) -> Any:
        """Safely retrieve a value from the loaded TOML data using a dot-separated path."""
        keys = key_path.split('.')
        value = self._raw_toml_config
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def build_and_validate_agent_maps(
        self,
        game_instance: "Game",
        agent_configurations: Dict[str, Dict[str, Any]],
        initialized_agents: Dict[str, "BaseAgent"], # type: ignore # BaseAgent might not be defined if imports are minimal
    ) -> None:
        """
        Builds and validates agent-power mappings based on agent_configurations
        and the current game instance.

        Populates `power_to_agent_id_map` and `agent_to_powers_map` on self.
        Validates that:
        - Every power in the game (from game_instance.powers) is mapped to an agent.
        - Every agent ID derived from agent_configurations that controls powers
          (excluding 'human' type not in initialized_agents) exists in initialized_agents.
        - No two agents claim the same power.

        Args:
            game_instance: The initialized diplomacy.Game object.
            agent_configurations: A dictionary where keys are agent IDs and values are
                                  their configuration details (like type, country, controlled_powers).
            initialized_agents: A dictionary of already initialized agent instances (excluding humans typically)
                                managed by an AgentManager, mapping agent_id to agent object.

        Raises:
            ValueError: If any validation fails (e.g., unmapped power, agent claiming non-existent power,
                        power claimed by multiple agents, agent in map not in initialized_agents).
        """
        logger.info("Building and validating agent-power mappings...")
        self.power_to_agent_id_map.clear()
        self.agent_to_powers_map.clear()

        all_game_power_keys_upper = {p.upper() for p in game_instance.powers.keys()}

        for agent_id, config_details in agent_configurations.items():
            agent_type = config_details.get("type", "").lower()
            controlled_powers_from_config: List[str] = []

            if agent_type == "bloc_llm":
                # 'powers' for bloc_llm, 'controlled_powers' might be post-parsing name
                controlled_powers_from_config = config_details.get("powers", config_details.get("controlled_powers", []))
            elif agent_type in ["llm", "neutral", "human", "null"]:
                power = config_details.get("country") # 'country' is typical for single-power agents
                if power and isinstance(power, str):
                    controlled_powers_from_config = [power]
            else:
                logger.warning(f"Unknown or unhandled agent type '{agent_type}' for agent_id '{agent_id}' during map building. Skipping.")
                continue

            if not controlled_powers_from_config:
                if agent_type not in ["human", "neutral"]: # Humans/Neutrals might legitimately have no powers assigned initially by some configs
                    logger.warning(f"Agent '{agent_id}' of type '{agent_type}' has no controlled powers defined in configuration. Skipping power mapping for this agent.")
                elif agent_type == "human" and not config_details.get("country"):
                    logger.info(f"Human agent '{agent_id}' has no country/power assigned in configuration.")
                # Allow agents (especially human/neutral) to exist without powers, but log it.
                # They won't be in power_to_agent_id_map if they don't control powers.
                self.agent_to_powers_map[agent_id] = [] # Still record the agent as existing
                continue

            current_agent_controlled_powers: List[str] = []
            for power_name in controlled_powers_from_config:
                power_name_upper = power_name.upper()
                if power_name_upper not in all_game_power_keys_upper:
                    err_msg = (
                        f"Configuration error: Agent '{agent_id}' (type: '{agent_type}') claims power '{power_name_upper}' "
                        f"which is not in the game instance's powers: {all_game_power_keys_upper}."
                    )
                    logger.error(err_msg)
                    raise ValueError(err_msg)

                if power_name_upper in self.power_to_agent_id_map:
                    existing_agent_id = self.power_to_agent_id_map[power_name_upper]
                    err_msg = (
                        f"Configuration error: Power '{power_name_upper}' is claimed by multiple agents: "
                        f"'{existing_agent_id}' and '{agent_id}'."
                    )
                    logger.error(err_msg)
                    raise ValueError(err_msg)
                
                self.power_to_agent_id_map[power_name_upper] = agent_id
                current_agent_controlled_powers.append(power_name_upper)
            
            if current_agent_controlled_powers: # Only add to agent_to_powers_map if they actually control powers
                 self.agent_to_powers_map[agent_id] = current_agent_controlled_powers
            elif agent_id not in self.agent_to_powers_map: # Ensure agent is listed even if it ended up with no valid powers
                 self.agent_to_powers_map[agent_id] = []

        # Validation 1: Every power in Game.powers has an entry in power_to_agent_id_map
        mapped_powers = set(self.power_to_agent_id_map.keys())
        unmapped_powers = all_game_power_keys_upper - mapped_powers
        if unmapped_powers:
            # This might be acceptable if some powers are meant to be passive/uncontrolled initially.
            # However, for a fully specified game, this would be an error.
            # Depending on strictness, this could be a warning or an error.
            logger.warning(f"Validation Warning: The following game powers are not mapped to any agent: {unmapped_powers}. This may be intentional for uncontrolled powers.")
            # If it must be an error: 
            # err_msg = f"Validation failed: The following game powers are not mapped to any agent: {unmapped_powers}"
            # logger.error(err_msg)
            # raise ValueError(err_msg)

        # Validation 2: Every agent_id in agent_to_powers_map (that is not human and controls powers)
        # must exist in initialized_agents keys.
        for agent_id_in_map, controlled_pws in self.agent_to_powers_map.items():
            # Agent might be in agent_to_powers_map but control no powers (e.g. human observer)
            if not controlled_pws:
                continue # No powers to validate against initialized agents for this one
            
            agent_config = agent_configurations.get(agent_id_in_map, {})
            agent_type = agent_config.get("type", "").lower()

            if agent_type == "human":
                # Human agents are often configured but not present in `initialized_agents` (which holds AI/bot instances).
                logger.debug(f"Agent '{agent_id_in_map}' is human, skipping check against initialized AI agents.")
                continue
            
            # NullAgents are also not AI agents in the typical sense, but they are initialized and present.
            # The existing check for agent_id_in_map in initialized_agents is sufficient.
            # if agent_type == "null":
            #     logger.debug(f"Agent '{agent_id_in_map}' is null, skipping check against initialized agents for AI-specific properties.")
            #     continue

            if agent_id_in_map not in initialized_agents:
                # This is a critical error if a non-human agent is supposed to control powers but isn't initialized.
                err_msg = (
                    f"Validation failed: Agent ID '{agent_id_in_map}' (type: '{agent_type}') controls powers {controlled_pws} "
                    f"but is not found in initialized agents ({list(initialized_agents.keys())})."
                )
                logger.error(err_msg)
                raise ValueError(err_msg)

        logger.info("Agent-power mappings built and validated.")
        logger.info(f"  power_to_agent_id_map: {self.power_to_agent_id_map}")
        logger.info(f"  agent_to_powers_map: {self.agent_to_powers_map}")

# Example of how parse_arguments might look (to be kept in lm_game.py or similar entry point)
# def parse_arguments_example() -> argparse.Namespace:
#     parser = argparse.ArgumentParser(description="AI Diplomacy Game Runner")
#     parser.add_argument("--game-config-file", type=str, required=True, help="Path to the game configuration TOML file.")
#     parser.add_argument("--log-level", type=str, help="Override log level (e.g., DEBUG, INFO, WARNING). Overrides TOML.")
#     parser.add_argument("--log-dir", type=str, help="Override base log directory. Overrides TOML.")
#     parser.add_argument("--game-id", type=str, help="Override game ID. Overrides TOML and auto-generation.")
#     # Removed other game-specific arguments as they should be in TOML
#     return parser.parse_args()

if __name__ == "__main__":
    # This is for example usage/testing of GameConfig
    # Create a dummy argparse.Namespace for testing
    # It should now primarily contain 'game_config_file' and optional overrides

    # Create a dummy TOML file for testing
    # Simplified __main__ for brevity, focusing on ensuring GameConfig can be instantiated
    # The more complex test cases from previous attempt are good but make the diff very large.
    # For this tool call, let's ensure basic instantiation with a valid config path works.
    # Full testing of registry/dynamic import would be separate.

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
    # Define the dummy factory function within the scope of the __main__ block or globally if needed
    # This is needed for the game_factory line above to resolve dynamically
    from diplomacy import Game # Ensure Game is imported for the dummy factory
    def dummy_factory_for_test():
        logger.info("Dummy factory for test called!")
        return Game()

    # Make it discoverable for dynamic import if needed, by placing it where the path points
    # For "ai_diplomacy.game_config.dummy_factory_for_test", it needs to be accessible here.
    # setattr(GameConfig, 'dummy_factory_for_test', dummy_factory_for_test) # Not quite how importlib works
    # Instead, this __main__ block itself acts as a test script.
    # The dynamic import will look for GameConfig.dummy_factory_for_test if SCENARIO_REGISTRY is empty or key not found.
    # Let's ensure SCENARIO_REGISTRY has this key for the test to pass cleanly via registry.
    if 'SCENARIO_REGISTRY' in globals():
        SCENARIO_REGISTRY["ai_diplomacy.game_config.dummy_factory_for_test"] = dummy_factory_for_test
    else: # If SCENARIO_REGISTRY wasn't imported (e.g. file run directly)
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
        if config.game_factory is not None: # mypy guard
           assert config.game_factory.__name__ == "dummy_factory_for_test", "Incorrect factory loaded"
           logger.info(f"Successfully loaded game factory: {config.game_factory.__name__}")

        # Test a case where factory is expected to fail
        error_toml_content = """
[scenario]
game_factory = "this.does.not.exist"
agents = []
        """
        error_toml_path = "temp_error_test_config.toml"
        with open(error_toml_path, "w") as f: f.write(error_toml_content)
        error_args = argparse.Namespace(game_config_file=error_toml_path, log_level=None, log_dir=None, game_id=None)
        logger.info("--- Testing GameConfig with non-existent factory (expect ValueError) ---")
        try:
            GameConfig(error_args)
            logger.error("Error test FAILED: ValueError not raised for non-existent factory.")
        except ValueError:
            logger.info("Error test PASSED: ValueError raised as expected.")
        finally:
            if os.path.exists(error_toml_path): os.remove(error_toml_path)


    except Exception as e:
        logger.error(f"Error during GameConfig __main__ test: {e}", exc_info=True)
    finally:
        if os.path.exists(dummy_toml_path_main):
            os.remove(dummy_toml_path_main)
        # Clean up the dummy factory from SCENARIO_REGISTRY if it was added for the test
        if "ai_diplomacy.game_config.dummy_factory_for_test" in SCENARIO_REGISTRY:
            del SCENARIO_REGISTRY["ai_diplomacy.game_config.dummy_factory_for_test"]


    logger.info("--- GameConfig __main__ Test Complete ---")
