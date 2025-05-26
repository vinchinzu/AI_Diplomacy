import logging
import random
from typing import Optional, List, Dict

# Assuming DiplomacyAgent is in agent.py and accessible in the test environment
# If not, this might need adjustment based on the project structure and PYTHONPATH for tests
from ai_diplomacy.agent import DiplomacyAgent 
from ai_diplomacy.agent_manager import AgentManager, DEFAULT_AGENT_MANAGER_FALLBACK_MODEL

# Mock GameConfig for testing (copied from agent_manager.py)
class MockGameConfig:
    def __init__(self, num_players=2, power_name=None, model_id=None, fixed_models=None, randomize_fixed_models=False, exclude_powers=None, power_model_assignments=None, default_model_from_config=None):
        self.num_players = num_players
        self.power_name = power_name
        self.model_id = model_id
        self.fixed_models = fixed_models if fixed_models is not None else []
        self.randomize_fixed_models = randomize_fixed_models
        self.exclude_powers = exclude_powers if exclude_powers is not None else []
        self.power_model_assignments = power_model_assignments if power_model_assignments is not None else [] # From TOML
        self.default_model_from_config = default_model_from_config # From TOML


        # Attributes needed for AgentManager and DiplomacyAgent instantiation
        self.powers_and_models = None # To be filled by assign_models
        self.agents = None # To be filled by initialize_agents
        self.game_id = "test_game_manager" 
        self.log_level = "DEBUG" # Example, pytest might override or manage this
        self.current_datetime_str = "test_time"
        self.game_id_prefix = "test"
        self.log_to_file = False # To simplify test output

        # Add other attributes GameConfig might expect, defaults from original mock
        self.perform_planning_phase = False
        self.num_negotiation_rounds = 1
        self.negotiation_style = "simultaneous"
        self.max_years = None

# Global for tests
ALL_POWERS_IN_GAME = ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"]

# Pytest typically handles logging, but if specific formatting is needed for debugging tests:
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_basic_assignment_two_llm_players_no_primary():
    logger.info("--- Test 1: Basic assignment, 2 LLM players, no primary agent ---")
    config1 = MockGameConfig(num_players=2, fixed_models=["ollama/modelA", "ollama/modelB"])
    manager1 = AgentManager(config1)
    assigned1 = manager1.assign_models(ALL_POWERS_IN_GAME)
    logger.info(f"Test 1 Assigned: {assigned1}")
    assert len(assigned1) == 2
    # Check if the models assigned are from the fixed_models list
    assigned_model_values = list(assigned1.values())
    assert "ollama/modelA" in assigned_model_values
    assert "ollama/modelB" in assigned_model_values

    manager1.initialize_agents(assigned1) 
    assert len(manager1.agents) == 2
    # Example of checking agent initialization (optional, depends on test depth)
    for power_name in assigned1.keys():
        assert power_name in manager1.agents
        agent = manager1.get_agent(power_name)
        assert agent is not None
        assert agent.power_name == power_name
        assert agent.model_id == assigned1[power_name]
        # logger.info(f"Agent {power_name} goals: {agent.goals}") # Informational


def test_primary_agent_specified_three_llm_players():
    logger.info("\n--- Test 2: Primary agent specified, 3 LLM players total ---")
    config2 = MockGameConfig(num_players=3, power_name="FRANCE", model_id="gpt-4o", fixed_models=["ollama/modelC"])
    manager2 = AgentManager(config2)
    assigned2 = manager2.assign_models(ALL_POWERS_IN_GAME)
    logger.info(f"Test 2 Assigned: {assigned2}")
    assert len(assigned2) == 3
    assert assigned2.get("FRANCE") == "gpt-4o"
    # Ensure the other models are picked from fixed_models or default
    other_models_count = 0
    for power, model in assigned2.items():
        if power != "FRANCE":
            other_models_count +=1
            assert model == "ollama/modelC" or model == DEFAULT_AGENT_MANAGER_FALLBACK_MODEL
    assert other_models_count == 2 # 3 total - 1 primary = 2 others

    manager2.initialize_agents(assigned2)
    assert "FRANCE" in manager2.agents
    assert manager2.get_agent("FRANCE").model_id == "gpt-4o"


def test_exclude_powers_randomize_fixed_models():
    logger.info("\n--- Test 3: Exclude powers, randomize fixed models ---")
    config3 = MockGameConfig(num_players=2, fixed_models=["modelX", "modelY", "modelZ"], randomize_fixed_models=True, exclude_powers=["ITALY", "TURKEY"])
    manager3 = AgentManager(config3)
    assigned3 = manager3.assign_models(ALL_POWERS_IN_GAME)
    logger.info(f"Test 3 Assigned: {assigned3}")
    assert len(assigned3) == 2
    assert "ITALY" not in assigned3
    assert "TURKEY" not in assigned3
    # Ensure assigned powers are not from the excluded list
    for power_name in assigned3.keys():
        assert power_name not in config3.exclude_powers

    manager3.initialize_agents(assigned3)
    for power_name in assigned3.keys():
        assert power_name in manager3.agents


def test_not_enough_fixed_models_for_num_players():
    logger.info("\n--- Test 4: Not enough fixed models for num_players ---")
    config4 = MockGameConfig(num_players=3, fixed_models=["only_one_model"])
    manager4 = AgentManager(config4)
    assigned4 = manager4.assign_models(ALL_POWERS_IN_GAME)
    logger.info(f"Test 4 Assigned: {assigned4}") 
    assert len(assigned4) == 3
    # Expect cycling of "only_one_model" or use of default for others
    models_assigned = list(assigned4.values())
    assert models_assigned.count("only_one_model") > 0 or models_assigned.count(DEFAULT_AGENT_MANAGER_FALLBACK_MODEL) > 0
    
    # More specific check:
    # If fixed_models are provided, they should be used up before resorting to default for additional slots.
    # And if num_players > len(fixed_models), then fixed models should be cycled.
    # In this case, "only_one_model" should be assigned to at least one player.
    # The other players will also get "only_one_model" due to cycling if fixed_models is the only source,
    # or DEFAULT_AGENT_MANAGER_FALLBACK_MODEL if the logic uses it to fill up.
    # The current assign_models logic seems to cycle fixed_models if available.
    
    # Update based on understanding of assign_models:
    # It uses fixed_models in rotation if available for additional players.
    # If fixed_models is empty, it uses default_model.
    # Here, fixed_models has one model. So it should be used for all 3 players.
    assert models_assigned.count("only_one_model") == 3
    
    manager4.initialize_agents(assigned4)
    assert len(manager4.agents) == 3

def test_num_players_is_zero():
    logger.info("\n--- Test 5: num_players is 0 ---")
    config5 = MockGameConfig(num_players=0)
    manager5 = AgentManager(config5)
    assigned5 = manager5.assign_models(ALL_POWERS_IN_GAME)
    logger.info(f"Test 5 Assigned: {assigned5}")
    assert len(assigned5) == 0
    manager5.initialize_agents(assigned5)
    assert len(manager5.agents) == 0

def test_num_players_one_primary_agent_set():
    logger.info("\n--- Test 6: num_players is 1, primary agent set ---")
    config6 = MockGameConfig(num_players=1, power_name="GERMANY", model_id="claude-3")
    manager6 = AgentManager(config6)
    assigned6 = manager6.assign_models(ALL_POWERS_IN_GAME)
    logger.info(f"Test 6 Assigned: {assigned6}")
    assert len(assigned6) == 1
    assert assigned6.get("GERMANY") == "claude-3"
    manager6.initialize_agents(assigned6)
    assert "GERMANY" in manager6.agents
    assert manager6.get_agent("GERMANY") is not None
    assert manager6.get_agent("GERMANY").model_id == "claude-3"
    assert manager6.get_agent("FRANCE") is None # Example of checking non-existence

def test_primary_agent_excluded():
    logger.info("\n--- Test 7: Primary agent power is in exclude_powers ---")
    config = MockGameConfig(num_players=1, power_name="FRANCE", model_id="gpt-4o", exclude_powers=["FRANCE"])
    manager = AgentManager(config)
    assigned = manager.assign_models(ALL_POWERS_IN_GAME)
    logger.info(f"Test 7 Assigned: {assigned}")
    assert "FRANCE" not in assigned # FRANCE should not be assigned a model
    assert len(assigned) == 1 # One player should still be chosen, but not FRANCE
    
    # Check that the assigned player is not FRANCE
    assigned_power = list(assigned.keys())[0]
    assert assigned_power != "FRANCE"
    # And it should get the default model, as the primary's model was tied to the excluded power
    assert assigned[assigned_power] == DEFAULT_AGENT_MANAGER_FALLBACK_MODEL

    manager.initialize_agents(assigned)
    assert manager.get_agent("FRANCE") is None

def test_toml_power_model_assignments_respected():
    logger.info("\n--- Test 8: power_model_assignments from TOML are respected ---")
    toml_assignments = [("AUSTRIA", "toml_model_A"), ("ENGLAND", "toml_model_B")]
    config = MockGameConfig(num_players=2, power_model_assignments=toml_assignments)
    manager = AgentManager(config)
    assigned = manager.assign_models(ALL_POWERS_IN_GAME)
    logger.info(f"Test 8 Assigned: {assigned}")
    assert len(assigned) == 2
    assert assigned.get("AUSTRIA") == "toml_model_A"
    assert assigned.get("ENGLAND") == "toml_model_B"
    manager.initialize_agents(assigned)
    assert manager.get_agent("AUSTRIA").model_id == "toml_model_A"
    assert manager.get_agent("ENGLAND").model_id == "toml_model_B"

def test_toml_and_cli_primary_agent_conflict_cli_wins():
    logger.info("\n--- Test 9: TOML assignment conflicts with CLI primary agent, CLI wins ---")
    toml_assignments = [("FRANCE", "toml_model_F")]
    config = MockGameConfig(num_players=1, power_name="FRANCE", model_id="cli_model_F", power_model_assignments=toml_assignments)
    manager = AgentManager(config)
    assigned = manager.assign_models(ALL_POWERS_IN_GAME)
    logger.info(f"Test 9 Assigned: {assigned}")
    assert len(assigned) == 1
    assert assigned.get("FRANCE") == "cli_model_F" # CLI model should override TOML
    manager.initialize_agents(assigned)
    assert manager.get_agent("FRANCE").model_id == "cli_model_F"

def test_num_players_limits_toml_assignments():
    logger.info("\n--- Test 10: num_players is less than TOML assignments ---")
    toml_assignments = [("AUSTRIA", "modelA"), ("ENGLAND", "modelB"), ("FRANCE", "modelC")]
    # num_players = 1, so only one of the TOML assignments should be kept.
    # The logic should prioritize them based on some order, or it might be arbitrary
    # depending on dict iteration. For robustness, we check that *one* of them is chosen.
    # The current implementation detail: priority_order in assign_models iterates TOML keys.
    config = MockGameConfig(num_players=1, power_model_assignments=toml_assignments)
    manager = AgentManager(config)
    assigned = manager.assign_models(ALL_POWERS_IN_GAME)
    logger.info(f"Test 10 Assigned: {assigned}")
    assert len(assigned) == 1 
    
    # Check that the assigned power is one of those specified in TOML
    assigned_power = list(assigned.keys())[0]
    assigned_model = list(assigned.values())[0]
    assert (assigned_power, assigned_model) in toml_assignments
    
    manager.initialize_agents(assigned)
    assert manager.get_agent(assigned_power).model_id == assigned_model

def test_default_model_from_config_used():
    logger.info("\n--- Test 11: Default model from TOML (GameConfig) is used ---")
    # No fixed_models, no CLI primary, num_players = 1. Should use default_model_from_config.
    config = MockGameConfig(num_players=1, default_model_from_config="toml_default_model")
    manager = AgentManager(config)
    assigned = manager.assign_models(ALL_POWERS_IN_GAME)
    logger.info(f"Test 11 Assigned: {assigned}")
    assert len(assigned) == 1
    assigned_model = list(assigned.values())[0]
    assert assigned_model == "toml_default_model"
    manager.initialize_agents(assigned)
    # Ensure the agent got the toml_default_model
    agent_power = list(manager.agents.keys())[0]
    assert manager.get_agent(agent_power).model_id == "toml_default_model"

def test_fallback_model_used_if_no_config_default():
    logger.info("\n--- Test 12: AgentManager fallback model is used if no default in TOML/GameConfig ---")
    # No fixed_models, no CLI primary, no default_model_from_config. Should use AgentManager's fallback.
    config = MockGameConfig(num_players=1) # default_model_from_config is None by default in MockGameConfig
    manager = AgentManager(config)
    assigned = manager.assign_models(ALL_POWERS_IN_GAME)
    logger.info(f"Test 12 Assigned: {assigned}")
    assert len(assigned) == 1
    assigned_model = list(assigned.values())[0]
    assert assigned_model == DEFAULT_AGENT_MANAGER_FALLBACK_MODEL # Check against the imported constant
    manager.initialize_agents(assigned)
    agent_power = list(manager.agents.keys())[0]
    assert manager.get_agent(agent_power).model_id == DEFAULT_AGENT_MANAGER_FALLBACK_MODEL

# More tests can be added for edge cases like:
# - All powers excluded
# - num_players > number of available non-excluded powers
# - Interactions between fixed_models (CLI), power_model_assignments (TOML), and default models.

logger.info("--- All AgentManager tests collected ---")
