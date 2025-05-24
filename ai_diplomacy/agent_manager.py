import logging
import random
from typing import Optional, List, Dict, Set, TYPE_CHECKING

from .agent import DiplomacyAgent # Assuming DiplomacyAgent is in agent.py
if TYPE_CHECKING:
    from .game_config import GameConfig

logger = logging.getLogger(__name__)

# Default model if not enough are specified or for remaining players
DEFAULT_FALLBACK_MODEL = "gpt-3.5-turbo" # Or consider a local model like "ollama/mistral"

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
        logger.info("Assigning models to powers...")
        
        powers_to_assign = list(all_game_powers)
        if self.game_config.exclude_powers:
            powers_to_assign = [p for p in powers_to_assign if p not in self.game_config.exclude_powers]
            logger.info(f"Excluded powers: {self.game_config.exclude_powers}. Remaining for assignment: {powers_to_assign}")

        powers_and_models: Dict[str, str] = {}
        assigned_powers: Set[str] = set()

        # 1. Assign model to the primary agent if specified
        primary_agent_power = self.game_config.power_name
        primary_agent_model = self.game_config.model_id

        if primary_agent_power and primary_agent_model:
            if primary_agent_power in powers_to_assign:
                powers_and_models[primary_agent_power] = primary_agent_model
                assigned_powers.add(primary_agent_power)
                logger.info(f"Assigned primary agent: {primary_agent_power} -> {primary_agent_model}")
            else:
                logger.warning(f"Primary agent power {primary_agent_power} is not in the list of assignable powers (possibly excluded).")
        
        # 2. Prepare list of remaining powers that need models
        remaining_powers = [p for p in powers_to_assign if p not in assigned_powers]
        
        # Determine how many more LLM players are needed based on num_players
        # num_players defines the total number of LLM-controlled agents.
        # If a primary agent was set, that's one LLM player.
        num_additional_llm_players_needed = self.game_config.num_players
        if primary_agent_power and primary_agent_power in powers_and_models:
            num_additional_llm_players_needed -= 1
        
        # Ensure we don't try to assign more LLM players than available remaining powers
        num_additional_llm_players_needed = min(num_additional_llm_players_needed, len(remaining_powers))

        if num_additional_llm_players_needed <= 0 and remaining_powers:
            logger.info(f"Target number of LLM players ({self.game_config.num_players}) reached or exceeded. "
                        f"Remaining powers ({len(remaining_powers)}) will not be LLM-controlled by this manager's assignment pass.")
            # These remaining powers might be controlled by DipNet or other means later in game setup.

        llm_powers_to_select = random.sample(remaining_powers, num_additional_llm_players_needed) \
            if self.game_config.randomize_fixed_models or not self.game_config.fixed_models else remaining_powers[:num_additional_llm_players_needed]

        # 3. Assign fixed models to the selected LLM powers
        fixed_models_list = list(self.game_config.fixed_models) if self.game_config.fixed_models else []
        if self.game_config.randomize_fixed_models and fixed_models_list:
            random.shuffle(fixed_models_list)

        for i, power_name in enumerate(llm_powers_to_select):
            if fixed_models_list:
                model_to_assign = fixed_models_list[i % len(fixed_models_list)] # Cycle through fixed models
            else:
                model_to_assign = DEFAULT_FALLBACK_MODEL # Fallback if no fixed models
                logger.warning(f"No fixed models specified or list exhausted, assigning fallback {DEFAULT_FALLBACK_MODEL} to {power_name}")
            
            powers_and_models[power_name] = model_to_assign
            assigned_powers.add(power_name)
            logger.info(f"Assigned LLM agent: {power_name} -> {model_to_assign}")
            if i + 1 >= num_additional_llm_players_needed : # Check if we have assigned enough LLM players
                 break


        logger.info(f"Final model assignments: {powers_and_models}")
        logger.info(f"Total LLM-controlled powers assigned by AgentManager: {len(powers_and_models)}")
        
        # Store in game_config as well
        self.game_config.powers_and_models = powers_and_models
        return powers_and_models

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
