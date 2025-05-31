from ai_diplomacy.model_utils import DEFAULT_AGENT_MANAGER_FALLBACK_MODEL
from ai_diplomacy.game_config import GameConfig # For type hinting
from ai_diplomacy.agent_manager import AgentManager # For type hinting
from typing import Dict, List, Any

# These assertion functions are designed to be used with the parametrized tests
# in test_agent_manager.py. Each function corresponds to a specific test case.

def _assert_test_1_basic_assignment(assigned: Dict[str, str], manager: AgentManager, config: GameConfig, all_powers: List[str]):
    assert len(assigned) == 2
    assigned_model_values = list(assigned.values())
    assert "ollama/modelA" in assigned_model_values
    assert "ollama/modelB" in assigned_model_values

def _assert_test_2_primary_agent_specified(assigned: Dict[str, str], manager: AgentManager, config: GameConfig, all_powers: List[str]):
    assert len(assigned) == 3
    assert assigned.get("FRANCE") == "gpt-4o"
    other_models_count = 0
    for power, model in assigned.items():
        if power != "FRANCE":
            other_models_count += 1
            assert (
                model == "ollama/modelC"
                or model == DEFAULT_AGENT_MANAGER_FALLBACK_MODEL
            )
    assert other_models_count == 2

def _assert_test_3_exclude_powers_randomize(assigned: Dict[str, str], manager: AgentManager, config: GameConfig, all_powers: List[str]):
    assert len(assigned) == 2
    assert "ITALY" not in assigned
    assert "TURKEY" not in assigned
    for power_name in assigned.keys():
        if config.args.exclude_powers is not None:
            assert power_name not in config.args.exclude_powers

def _assert_test_4_not_enough_fixed_models(assigned: Dict[str, str], manager: AgentManager, config: GameConfig, all_powers: List[str]):
    assert len(assigned) == 3
    models_assigned = list(assigned.values())
    assert models_assigned.count("only_one_model") == 3

def _assert_test_5_num_players_zero(assigned: Dict[str, str], manager: AgentManager, config: GameConfig, all_powers: List[str]):
    assert len(assigned) == 0

def _assert_test_6_num_players_one_primary(assigned: Dict[str, str], manager: AgentManager, config: GameConfig, all_powers: List[str]):
    assert len(assigned) == 1
    assert assigned.get("GERMANY") == "claude-3"
    # The following check was originally in the main test.
    # It relies on manager.initialize_agents being called AFTER assign_models.
    # manager.initialize_agents(assigned) # This should be done in the test itself
    # assert manager.get_agent("FRANCE") is None

def _assert_test_7_primary_agent_excluded(assigned: Dict[str, str], manager: AgentManager, config: GameConfig, all_powers: List[str]):
    assert "FRANCE" not in assigned
    assert len(assigned) == 1
    assigned_power = list(assigned.keys())[0]
    assert assigned_power != "FRANCE"
    assert assigned[assigned_power] == DEFAULT_AGENT_MANAGER_FALLBACK_MODEL
    # The following check was originally in the main test.
    # manager.initialize_agents(assigned) # This should be done in the test itself
    # assert manager.get_agent("FRANCE") is None

def _assert_test_8a_toml_respected_limited_players(assigned: Dict[str, str], manager: AgentManager, config: GameConfig, all_powers: List[str]):
    assert config.default_model_from_config == "toml_default_model"
    assert config.power_model_assignments.get("FRANCE") == "toml_france_model"
    assert len(assigned) == 2
    chosen_powers = list(assigned.keys())
    if "FRANCE" in chosen_powers:
        assert assigned["FRANCE"] == "toml_france_model"
    if "GERMANY" in chosen_powers:
        assert assigned["GERMANY"] == "toml_germany_model"
    for power, model_id in assigned.items():
        if power not in ["FRANCE", "GERMANY"]:
            assert model_id == "toml_default_model"
        elif power == "FRANCE":
            assert model_id == "toml_france_model"
        elif power == "GERMANY":
            assert model_id == "toml_germany_model"

def _assert_test_8b_toml_respected_all_players(assigned: Dict[str, str], manager: AgentManager, config: GameConfig, all_powers: List[str]):
    assert config.default_model_from_config == "toml_default_model"
    assert config.power_model_assignments.get("FRANCE") == "toml_france_model"
    assert assigned.get("FRANCE") == "toml_france_model"
    assert assigned.get("GERMANY") == "toml_germany_model"
    for power in all_powers: # Use the passed all_powers
        if power not in ["FRANCE", "GERMANY"]:
            assert assigned.get(power) == "toml_default_model"

def _assert_test_9_toml_cli_conflict(assigned: Dict[str, str], manager: AgentManager, config: GameConfig, all_powers: List[str]):
    assert len(assigned) == 1
    assert assigned.get("FRANCE") == "cli_france_model_wins"

def _assert_test_10_num_players_limits_toml(assigned: Dict[str, str], manager: AgentManager, config: GameConfig, all_powers: List[str]):
    assert len(assigned) == 3
    for power_name, model_id in assigned.items():
        assert model_id == f"toml_{power_name.lower()}"

def _assert_test_11_default_model_from_config(assigned: Dict[str, str], manager: AgentManager, config: GameConfig, all_powers: List[str]):
    assert len(assigned) == 2
    for model_id in assigned.values():
        assert model_id == "my_global_default_from_toml"

def _assert_test_12_fallback_model_no_config_default(assigned: Dict[str, str], manager: AgentManager, config: GameConfig, all_powers: List[str]):
    assert config.default_model_from_config is None
    assert len(assigned) == 1
    assert list(assigned.values())[0] == DEFAULT_AGENT_MANAGER_FALLBACK_MODEL

# Expose assertions for import
assertion_map = {
    "test_1_basic_assignment": _assert_test_1_basic_assignment,
    "test_2_primary_agent_specified": _assert_test_2_primary_agent_specified,
    "test_3_exclude_powers_randomize": _assert_test_3_exclude_powers_randomize,
    "test_4_not_enough_fixed_models": _assert_test_4_not_enough_fixed_models,
    "test_5_num_players_zero": _assert_test_5_num_players_zero,
    "test_6_num_players_one_primary": _assert_test_6_num_players_one_primary,
    "test_7_primary_agent_excluded": _assert_test_7_primary_agent_excluded,
    "test_8a_toml_respected_limited_players": _assert_test_8a_toml_respected_limited_players,
    "test_8b_toml_respected_all_players": _assert_test_8b_toml_respected_all_players,
    "test_9_toml_cli_conflict": _assert_test_9_toml_cli_conflict,
    "test_10_num_players_limits_toml": _assert_test_10_num_players_limits_toml,
    "test_11_default_model_from_config": _assert_test_11_default_model_from_config,
    "test_12_fallback_model_no_default": _assert_test_12_fallback_model_no_config_default,
} 