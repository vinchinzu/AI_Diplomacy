import logging
import random
from typing import Optional, List, Dict, TYPE_CHECKING  # Removed Set

from .agents.factory import AgentFactory
from .agents.base import BaseAgent
from .services.config import AgentConfig

if TYPE_CHECKING:
    from .game_config import GameConfig

logger = logging.getLogger(__name__)

# Default model if not enough are specified or for remaining players
DEFAULT_AGENT_MANAGER_FALLBACK_MODEL = "gemma3:4b"  # More specific name


class AgentManager:
    """
    Manages the creation, initialization, and storage of DiplomacyAgents.
    """

    def __init__(self, game_config: "GameConfig"):
        """
        Initializes the AgentManager.

        Args:
            game_config: The game configuration object.
        """
        self.game_config = game_config
        self.agents: Dict[str, BaseAgent] = {}
        self.agent_factory = AgentFactory()
        logger.info("AgentManager initialized.")

    def assign_models(self, all_game_powers: List[str]) -> Dict[str, str]:
        """
        Assigns LLM model IDs to each participating power in the game.

        This method considers:
        - A specific power controlled by a specific model (from config.power_name & config.model_id).
        - A list of fixed models to be assigned to other powers (from config.fixed_models).
        - Randomization of fixed model assignments (config.randomize_fixed_models).
        - Powers to be excluded (config.exclude_powers).
        - The total number of LLM-controlled players (config.num_players).

        Args:
            all_game_powers: A list of all power names in the game (e.g., ["AUSTRIA", "ENGLAND", ...]).

        Returns:
            A dictionary mapping power names to their assigned model IDs.
        """
        logger.info(
            "Assigning models to powers using TOML config and GameConfig overrides..."
        )

        # Handle None exclude_powers by using empty list
        exclude_powers = self.game_config.exclude_powers or []

        # Start with TOML configurations from GameConfig
        powers_and_models: Dict[str, str] = dict(
            self.game_config.power_model_assignments
        )
        default_model = (
            self.game_config.default_model_from_config
            or DEFAULT_AGENT_MANAGER_FALLBACK_MODEL
        )
        logger.info(
            f"Using default model: '{default_model}' (from TOML or AgentManager fallback)"
        )

        # Determine powers that still need assignment (not in TOML or to be LLM controlled)
        # powers_needing_assignment_for_llm_control = [] # This variable is assigned but not used.
        # for p in all_game_powers:
        #     if p not in exclude_powers:
        #         if p not in powers_and_models: # Not specified in TOML
        #             powers_needing_assignment_for_llm_control.append(p)
        # If p is in powers_and_models, it means TOML explicitly assigned it.
        # We will respect that, unless num_players limits LLM control.

        # Override or fill in based on primary agent settings from GameConfig (CLI overrides)
        primary_agent_power = self.game_config.power_name
        primary_agent_model_cli = (
            self.game_config.model_id
        )  # Model specified via CLI for primary agent

        if primary_agent_power and primary_agent_model_cli:
            if primary_agent_power in exclude_powers:
                logger.warning(
                    f"Primary agent power {primary_agent_power} is excluded. Ignoring CLI model assignment."
                )
            else:
                logger.info(
                    f"CLI override: Assigning primary agent {primary_agent_power} -> {primary_agent_model_cli}"
                )
                powers_and_models[primary_agent_power] = primary_agent_model_cli
        elif primary_agent_power and primary_agent_power not in powers_and_models:
            # Primary power specified but no model via CLI, and not in TOML.
            # Assign default model to it if it's not excluded.
            if primary_agent_power not in exclude_powers:
                logger.info(
                    f"Primary power {primary_agent_power} specified without model, assigning default: {default_model}"
                )
                powers_and_models[primary_agent_power] = default_model

        # Fill remaining LLM slots using fixed_models from CLI or default model
        # Count how many LLM-controlled powers we have so far from TOML + primary CLI override.
        current_llm_powers = {
            p for p, m in powers_and_models.items() if p not in exclude_powers
        }
        num_llm_controlled_so_far = len(current_llm_powers)

        num_additional_llm_players_needed = (
            self.game_config.num_players - num_llm_controlled_so_far
        )

        # Consider powers from TOML that are not excluded for this calculation
        candidate_powers_for_filling_slots = [
            p
            for p in all_game_powers
            if p not in exclude_powers and p not in current_llm_powers
        ]

        if self.game_config.randomize_fixed_models:
            random.shuffle(candidate_powers_for_filling_slots)

        fixed_models_cli_list = (
            list(self.game_config.fixed_models) if self.game_config.fixed_models else []
        )
        if self.game_config.randomize_fixed_models and fixed_models_cli_list:
            random.shuffle(fixed_models_cli_list)

        additional_llm_assigned_count = 0
        # Loop variable 'i' was not used. Replaced with '_'
        for _, power_to_assign_additional_model in enumerate(
            candidate_powers_for_filling_slots
        ):
            if additional_llm_assigned_count >= num_additional_llm_players_needed:
                break

            if (
                fixed_models_cli_list
            ):  # Use CLI fixed_models first for these additional slots
                model_to_assign = fixed_models_cli_list[
                    additional_llm_assigned_count % len(fixed_models_cli_list)
                ]
            else:  # If no CLI fixed_models, use the default (from TOML or AgentManager fallback)
                model_to_assign = default_model

            powers_and_models[power_to_assign_additional_model] = model_to_assign
            logger.info(
                f"Assigned additional LLM agent: {power_to_assign_additional_model} -> {model_to_assign} (num_players target)"
            )
            additional_llm_assigned_count += 1

        # Final filter: ensure only num_players are LLM controlled, respecting exclusions
        final_llm_assignments: Dict[str, str] = {}
        powers_considered_for_final_llm_list = [
            p for p in all_game_powers if p not in exclude_powers
        ]

        # Prioritize powers that have specific assignments (CLI primary, then TOML)
        priority_order: List[str] = []
        if (
            primary_agent_power
            and primary_agent_power in powers_and_models
            and primary_agent_power not in exclude_powers
        ):
            priority_order.append(primary_agent_power)
        for p in powers_and_models.keys():  # Iterate keys from TOML based assignments
            if p not in priority_order and p not in exclude_powers:
                priority_order.append(p)
        for p in powers_considered_for_final_llm_list:
            if p not in priority_order:  # Add remaining non-excluded powers
                priority_order.append(p)

        llm_slots_filled = 0
        for power_name in priority_order:
            if llm_slots_filled >= self.game_config.num_players:
                break
            if (
                power_name in powers_and_models
            ):  # Has an assignment from TOML or CLI override or additional filling
                final_llm_assignments[power_name] = powers_and_models[power_name]
                llm_slots_filled += 1
            elif (
                power_name not in exclude_powers
            ):  # Needs a default because it wasn't specified earlier
                final_llm_assignments[power_name] = default_model
                logger.info(
                    f"Assigning default model '{default_model}' to {power_name} to meet num_players target."
                )
                llm_slots_filled += 1

        logger.info(
            f"Final model assignments after considering num_players ({self.game_config.num_players}): {final_llm_assignments}"
        )

        # Store in game_config as well
        self.game_config.powers_and_models = final_llm_assignments
        return final_llm_assignments

    def _initialize_agent_state_ext(self, agent: BaseAgent):
        """
        Initializes extended state for an agent (e.g., loading from files, specific heuristics).
        This method is a placeholder for more complex setup that might be needed in the future.
        """
        logger.debug(
            f"Performing extended state initialization for {agent.country} (currently minimal)."
        )
        # This function can be expanded if there's a need to load specific initial states
        # from files or apply more complex power-specific heuristics here.
        pass

    def initialize_agents(self, powers_and_models: Dict[str, str]):
        """
        Creates and initializes agent instances for each power using the new factory system.

        Args:
            powers_and_models: A dictionary mapping power names to their assigned model IDs.
        """
        logger.info("Initializing agents...")
        self.agents = {}  # Clear any previous agents

        for power_name, model_id_for_power in powers_and_models.items():
            logger.info(
                f"Creating agent for {power_name} with model {model_id_for_power}"
            )
            try:
                # Create agent configuration
                agent_config = AgentConfig(
                    country=power_name,
                    type="llm",
                    model_id=model_id_for_power,
                    context_provider="auto",  # Will auto-select based on model capabilities
                )

                # Create agent using factory
                agent_id = f"{power_name.lower()}_{self.game_config.game_id}"
                agent = self.agent_factory.create_agent(
                    agent_id=agent_id,
                    country=power_name,
                    config=agent_config,
                    game_id=self.game_config.game_id,
                )

                self._initialize_agent_state_ext(agent)  # Call extended initializer
                self.agents[power_name] = agent
                logger.info(f"Agent for {power_name} created and initialized.")
            except Exception as e:
                logger.error(
                    f"Failed to create or initialize agent for {power_name} with model {model_id_for_power}: {e}",
                    exc_info=True,
                )
                # Continue with other agents

        # Store in game_config as well
        self.game_config.agents = self.agents
        logger.info(f"All {len(self.agents)} agents initialized.")

    def get_agent(self, power_name: str) -> Optional[BaseAgent]:
        """
        Retrieves an initialized agent by its power name.

        Args:
            power_name: The name of the power whose agent is to be retrieved.

        Returns:
            The BaseAgent instance, or None if not found.
        """
        return self.agents.get(power_name)
