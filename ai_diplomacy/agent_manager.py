import logging
import random
from typing import Optional, List, Dict, Set, TYPE_CHECKING

from .agent import DiplomacyAgent # Assuming DiplomacyAgent is in agent.py
if TYPE_CHECKING:
    from .game_config import GameConfig

logger = logging.getLogger(__name__)

# Default model if not enough are specified or for remaining players
DEFAULT_AGENT_MANAGER_FALLBACK_MODEL = "ollama/gemma3:4b" # More specific name

class AgentManager:
    """
    Manages the creation, initialization, and storage of DiplomacyAgents.
    """

    def __init__(self, game_config: 'GameConfig'):
        """
        Initializes the AgentManager.

        Args:
            game_config: The game configuration object.
        """
        self.game_config = game_config
        self.agents: Dict[str, DiplomacyAgent] = {}
        logger.info("AgentManager initialized.")

    def assign_models_to_powers(self, all_game_powers: List[str]) -> Dict[str, str]:
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
        logger.info("Assigning models to powers using TOML config and GameConfig overrides...")
        
        # Start with TOML configurations from GameConfig
        powers_and_models: Dict[str, str] = dict(self.game_config.power_model_assignments) 
        default_model = self.game_config.default_model_from_config or DEFAULT_AGENT_MANAGER_FALLBACK_MODEL
        logger.info(f"Using default model: '{default_model}' (from TOML or AgentManager fallback)")

        # Determine powers that still need assignment (not in TOML or to be LLM controlled)
        powers_needing_assignment_for_llm_control = []
        for p in all_game_powers:
            if p not in self.game_config.exclude_powers:
                if p not in powers_and_models: # Not specified in TOML
                    powers_needing_assignment_for_llm_control.append(p)
                # If p is in powers_and_models, it means TOML explicitly assigned it.
                # We will respect that, unless num_players limits LLM control.

        # Override or fill in based on primary agent settings from GameConfig (CLI overrides)
        primary_agent_power = self.game_config.power_name
        primary_agent_model_cli = self.game_config.model_id # Model specified via CLI for primary agent

        if primary_agent_power and primary_agent_model_cli:
            if primary_agent_power in self.game_config.exclude_powers:
                logger.warning(f"Primary agent power {primary_agent_power} is excluded. Ignoring CLI model assignment.")
            else:
                logger.info(f"CLI override: Assigning primary agent {primary_agent_power} -> {primary_agent_model_cli}")
                powers_and_models[primary_agent_power] = primary_agent_model_cli
        elif primary_agent_power and primary_agent_power not in powers_and_models:
            # Primary power specified but no model via CLI, and not in TOML.
            # Assign default model to it if it's not excluded.
            if primary_agent_power not in self.game_config.exclude_powers:
                 logger.info(f"Primary power {primary_agent_power} specified without model, assigning default: {default_model}")
                 powers_and_models[primary_agent_power] = default_model
        
        # Fill remaining LLM slots using fixed_models from CLI or default model
        # Count how many LLM-controlled powers we have so far from TOML + primary CLI override.
        current_llm_powers = {p for p, m in powers_and_models.items() if p not in self.game_config.exclude_powers}
        num_llm_controlled_so_far = len(current_llm_powers)
        
        num_additional_llm_players_needed = self.game_config.num_players - num_llm_controlled_so_far

        # Consider powers from TOML that are not excluded for this calculation
        candidate_powers_for_filling_slots = [p for p in all_game_powers if p not in self.game_config.exclude_powers and p not in current_llm_powers]
        
        if self.game_config.randomize_fixed_models:
            random.shuffle(candidate_powers_for_filling_slots)

        fixed_models_cli_list = list(self.game_config.fixed_models) if self.game_config.fixed_models else []
        if self.game_config.randomize_fixed_models and fixed_models_cli_list:
            random.shuffle(fixed_models_cli_list)
        
        additional_llm_assigned_count = 0
        for i, power_to_assign_additional_model in enumerate(candidate_powers_for_filling_slots):
            if additional_llm_assigned_count >= num_additional_llm_players_needed:
                break
            
            if fixed_models_cli_list: # Use CLI fixed_models first for these additional slots
                model_to_assign = fixed_models_cli_list[additional_llm_assigned_count % len(fixed_models_cli_list)]
            else: # If no CLI fixed_models, use the default (from TOML or AgentManager fallback)
                model_to_assign = default_model
            
            powers_and_models[power_to_assign_additional_model] = model_to_assign
            logger.info(f"Assigned additional LLM agent: {power_to_assign_additional_model} -> {model_to_assign} (num_players target)")
            additional_llm_assigned_count += 1

        # Final filter: ensure only num_players are LLM controlled, respecting exclusions
        final_llm_assignments: Dict[str, str] = {}
        powers_considered_for_final_llm_list = [p for p in all_game_powers if p not in self.game_config.exclude_powers]
        
        # Prioritize powers that have specific assignments (CLI primary, then TOML)
        priority_order: List[str] = []
        if primary_agent_power and primary_agent_power in powers_and_models and primary_agent_power not in self.game_config.exclude_powers:
            priority_order.append(primary_agent_power)
        for p in powers_and_models.keys(): # Iterate keys from TOML based assignments
            if p not in priority_order and p not in self.game_config.exclude_powers:
                priority_order.append(p)
        for p in powers_considered_for_final_llm_list:
            if p not in priority_order: # Add remaining non-excluded powers
                priority_order.append(p)

        llm_slots_filled = 0
        for power_name in priority_order:
            if llm_slots_filled >= self.game_config.num_players:
                break
            if power_name in powers_and_models: # Has an assignment from TOML or CLI override or additional filling
                final_llm_assignments[power_name] = powers_and_models[power_name]
                llm_slots_filled +=1
            elif power_name not in self.game_config.exclude_powers: # Needs a default because it wasn't specified earlier
                final_llm_assignments[power_name] = default_model
                logger.info(f"Assigning default model '{default_model}' to {power_name} to meet num_players target.")
                llm_slots_filled +=1

        logger.info(f"Final model assignments after considering num_players ({self.game_config.num_players}): {final_llm_assignments}")
        
        # Store in game_config as well
        self.game_config.powers_and_models = final_llm_assignments
        return final_llm_assignments

    def _initialize_agent_state_ext(self, agent: DiplomacyAgent):
        """
        Initializes extended state for an agent (e.g., loading from files, specific heuristics).
        Currently, the DiplomacyAgent constructor handles basic default initialization
        of goals and relationships. This method is a placeholder for more complex setup.
        """
        # In the original lm_game.py, initial goals and relationships were largely
        # handled by the DiplomacyAgent's __init__ (e.g., relationships default to Neutral).
        # This function can be expanded if there's a need to load specific initial states
        # from files or apply more complex power-specific heuristics here.
        logger.debug(f"Performing extended state initialization for {agent.power_name} (currently minimal).")
        # Example: Load power-specific initial goals from a configuration file if it existed
        # initial_goals_config = load_goals_for_power(agent.power_name)
        # if initial_goals_config:
        #    agent.goals = initial_goals_config
        # agent.add_journal_entry("Extended state initialization complete.")
        pass


    def initialize_agents(self, powers_and_models: Dict[str, str]):
        """
        Creates and initializes DiplomacyAgent instances for each power.

        Args:
            powers_and_models: A dictionary mapping power names to their assigned model IDs.
        """
        logger.info("Initializing agents...")
        self.agents = {} # Clear any previous agents
        for power_name, model_id_for_power in powers_and_models.items():
            logger.info(f"Creating agent for {power_name} with model {model_id_for_power}")
            try:
                agent = DiplomacyAgent(
                    power_name=power_name,
                    model_id=model_id_for_power
                    # Initial goals and relationships are handled by DiplomacyAgent's __init__
                )
                self._initialize_agent_state_ext(agent) # Call extended initializer
                self.agents[power_name] = agent
                logger.info(f"Agent for {power_name} created and initialized.")
            except Exception as e:
                logger.error(f"Failed to create or initialize agent for {power_name} with model {model_id_for_power}: {e}", exc_info=True)
                # Decide if this is fatal or if the game can proceed without this agent
                # For now, it will skip this agent.

        # Store in game_config as well
        self.game_config.agents = self.agents
        logger.info(f"All {len(self.agents)} agents initialized.")


    def get_agent(self, power_name: str) -> Optional[DiplomacyAgent]:
        """
        Retrieves an initialized agent by its power name.

        Args:
            power_name: The name of the power whose agent is to be retrieved.

        Returns:
            The DiplomacyAgent instance, or None if not found.
        """
        return self.agents.get(power_name)

if __name__ == '__main__':
    # Example Usage for testing AgentManager
    
    # Mock GameConfig for testing
    class MockGameConfig:
        def __init__(self, num_players=2, power_name=None, model_id=None, fixed_models=None, randomize=False, exclude=None):
            self.num_players = num_players
            self.power_name = power_name
            self.model_id = model_id
            self.fixed_models = fixed_models
            self.randomize_fixed_models = randomize
            self.exclude_powers = exclude
            self.powers_and_models = None # To be filled by assign_models_to_powers
            self.agents = None # To be filled by initialize_agents
            # For DiplomacyAgent instantiation (not strictly needed for assign_models_to_powers test)
            self.game_id = "test_game_manager" 
            self.log_level = "DEBUG"
            self.current_datetime_str = "test_time"
            self.game_id_prefix = "test"
            self.log_to_file = False # To simplify test output, no file creation
            # Add other attributes GameConfig expects
            self.perform_planning_phase = False
            self.num_negotiation_rounds = 1
            self.negotiation_style = "simultaneous"
            self.max_years = None


    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    all_powers_in_game = ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"]

    logger.info("--- Test 1: Basic assignment, 2 LLM players, no primary agent ---")
    config1 = MockGameConfig(num_players=2, fixed_models=["ollama/modelA", "ollama/modelB"])
    manager1 = AgentManager(config1)
    assigned1 = manager1.assign_models_to_powers(all_powers_in_game)
    logger.info(f"Test 1 Assigned: {assigned1}")
    assert len(assigned1) == 2
    manager1.initialize_agents(assigned1) # Test initialization
    assert len(manager1.agents) == 2
    if "AUSTRIA" in manager1.agents: logger.info(f"Agent AUSTRIA goals: {manager1.agents['AUSTRIA'].goals}")


    logger.info("\n--- Test 2: Primary agent specified, 3 LLM players total ---")
    config2 = MockGameConfig(num_players=3, power_name="FRANCE", model_id="gpt-4o", fixed_models=["ollama/modelC"])
    manager2 = AgentManager(config2)
    assigned2 = manager2.assign_models_to_powers(all_powers_in_game)
    logger.info(f"Test 2 Assigned: {assigned2}")
    assert len(assigned2) == 3
    assert assigned2.get("FRANCE") == "gpt-4o"
    manager2.initialize_agents(assigned2)
    assert "FRANCE" in manager2.agents

    logger.info("\n--- Test 3: Exclude powers, randomize fixed models ---")
    config3 = MockGameConfig(num_players=2, fixed_models=["modelX", "modelY", "modelZ"], randomize=True, exclude=["ITALY", "TURKEY"])
    manager3 = AgentManager(config3)
    assigned3 = manager3.assign_models_to_powers(all_powers_in_game)
    logger.info(f"Test 3 Assigned: {assigned3}")
    assert len(assigned3) == 2
    assert "ITALY" not in assigned3
    assert "TURKEY" not in assigned3
    manager3.initialize_agents(assigned3)


    logger.info("\n--- Test 4: Not enough fixed models for num_players ---")
    config4 = MockGameConfig(num_players=3, fixed_models=["only_one_model"])
    manager4 = AgentManager(config4)
    assigned4 = manager4.assign_models_to_powers(all_powers_in_game)
    logger.info(f"Test 4 Assigned: {assigned4}") # Expects cycling or fallback
    assert len(assigned4) == 3
    assert list(assigned4.values()).count("only_one_model") >= 1 # Could be more due to cycling
    manager4.initialize_agents(assigned4)

    logger.info("\n--- Test 5: num_players is 0 ---")
    config5 = MockGameConfig(num_players=0)
    manager5 = AgentManager(config5)
    assigned5 = manager5.assign_models_to_powers(all_powers_in_game)
    logger.info(f"Test 5 Assigned: {assigned5}")
    assert len(assigned5) == 0
    manager5.initialize_agents(assigned5)
    
    logger.info("\n--- Test 6: num_players is 1, primary agent set ---")
    config6 = MockGameConfig(num_players=1, power_name="GERMANY", model_id="claude-3")
    manager6 = AgentManager(config6)
    assigned6 = manager6.assign_models_to_powers(all_powers_in_game)
    logger.info(f"Test 6 Assigned: {assigned6}")
    assert len(assigned6) == 1
    assert assigned6.get("GERMANY") == "claude-3"
    manager6.initialize_agents(assigned6)
    assert "GERMANY" in manager6.agents
    assert manager6.get_agent("GERMANY") is not None
    assert manager6.get_agent("FRANCE") is None


    logger.info("--- AgentManager Test Complete ---")
