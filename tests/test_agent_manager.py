import logging
import pytest
from pathlib import Path
from ai_diplomacy.agent_manager import (
    AgentManager,
    DEFAULT_AGENT_MANAGER_FALLBACK_MODEL,
)
from ai_diplomacy.agents.llm_agent import LLMAgent
from ._shared_fixtures import create_game_config

ALL_POWERS_IN_GAME = [
    "AUSTRIA",
    "ENGLAND",
    "FRANCE",
    "GERMANY",
    "ITALY",
    "RUSSIA",
    "TURKEY",
]

logger = logging.getLogger(__name__)

TOML_CONTENT_TEST_8 = """
default_model = "toml_default_model"
[powers]
FRANCE = "toml_france_model"
GERMANY = "toml_germany_model"
"""

TOML_CONTENT_TEST_9 = """
[powers]
FRANCE = "toml_france_model_should_be_overridden"
"""

TOML_CONTENT_TEST_10 = """
default_model = "toml_default"
[powers]
AUSTRIA = "toml_austria"
ENGLAND = "toml_england"
FRANCE = "toml_france"
GERMANY = "toml_germany"
ITALY = "toml_italy"
RUSSIA = "toml_russia"
TURKEY = "toml_turkey"
"""

TOML_CONTENT_TEST_11 = """
default_model = "my_global_default_from_toml"
[powers]
"""

def _assert_test_1_basic_assignment(assigned, manager, config, all_powers):
    assert len(assigned) == 2
    assigned_model_values = list(assigned.values())
    assert "ollama/modelA" in assigned_model_values
    assert "ollama/modelB" in assigned_model_values

def _assert_test_2_primary_agent_specified(assigned, manager, config, all_powers):
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

def _assert_test_3_exclude_powers_randomize(assigned, manager, config, all_powers):
    assert len(assigned) == 2
    assert "ITALY" not in assigned
    assert "TURKEY" not in assigned
    for power_name in assigned.keys():
        if config.args.exclude_powers is not None:
            assert power_name not in config.args.exclude_powers

def _assert_test_4_not_enough_fixed_models(assigned, manager, config, all_powers):
    assert len(assigned) == 3
    models_assigned = list(assigned.values())
    assert models_assigned.count("only_one_model") == 3

def _assert_test_5_num_players_zero(assigned, manager, config, all_powers):
    assert len(assigned) == 0

def _assert_test_6_num_players_one_primary(assigned, manager, config, all_powers):
    assert len(assigned) == 1
    assert assigned.get("GERMANY") == "claude-3"
    manager.initialize_agents(assigned)
    assert manager.get_agent("FRANCE") is None

def _assert_test_7_primary_agent_excluded(assigned, manager, config, all_powers):
    assert "FRANCE" not in assigned
    assert len(assigned) == 1
    assigned_power = list(assigned.keys())[0]
    assert assigned_power != "FRANCE"
    assert assigned[assigned_power] == DEFAULT_AGENT_MANAGER_FALLBACK_MODEL
    manager.initialize_agents(assigned)
    assert manager.get_agent("FRANCE") is None

def _assert_test_8a_toml_respected_limited_players(assigned, manager, config, all_powers):
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

def _assert_test_8b_toml_respected_all_players(assigned, manager, config, all_powers):
    assert config.default_model_from_config == "toml_default_model"
    assert config.power_model_assignments.get("FRANCE") == "toml_france_model"
    assert assigned.get("FRANCE") == "toml_france_model"
    assert assigned.get("GERMANY") == "toml_germany_model"
    for power in all_powers:
        if power not in ["FRANCE", "GERMANY"]:
            assert assigned.get(power) == "toml_default_model"

def _assert_test_9_toml_cli_conflict(assigned, manager, config, all_powers):
    assert len(assigned) == 1
    assert assigned.get("FRANCE") == "cli_france_model_wins"

def _assert_test_10_num_players_limits_toml(assigned, manager, config, all_powers):
    assert len(assigned) == 3
    for power_name, model_id in assigned.items():
        assert model_id == f"toml_{power_name.lower()}"

def _assert_test_11_default_model_from_config(assigned, manager, config, all_powers):
    assert len(assigned) == 2
    for model_id in assigned.values():
        assert model_id == "my_global_default_from_toml"

def _assert_test_12_fallback_model_no_config_default(assigned, manager, config, all_powers):
    assert config.default_model_from_config is None
    assert len(assigned) == 1
    assert list(assigned.values())[0] == DEFAULT_AGENT_MANAGER_FALLBACK_MODEL

@pytest.fixture
def game_config_factory():
    return create_game_config

PARAMETRIZED_TEST_CASES = [
    ("test_1_basic_assignment", 2, None, None, ["ollama/modelA", "ollama/modelB"], None, False, None, _assert_test_1_basic_assignment),
    ("test_2_primary_agent_specified", 3, "FRANCE", "gpt-4o", ["ollama/modelC"], None, False, None, _assert_test_2_primary_agent_specified),
    ("test_3_exclude_powers_randomize", 2, None, None, ["modelX", "modelY", "modelZ"], ["ITALY", "TURKEY"], True, None, _assert_test_3_exclude_powers_randomize),
    ("test_4_not_enough_fixed_models", 3, None, None, ["only_one_model"], None, False, None, _assert_test_4_not_enough_fixed_models),
    ("test_5_num_players_zero", 0, None, None, None, None, False, None, _assert_test_5_num_players_zero),
    ("test_6_num_players_one_primary", 1, "GERMANY", "claude-3", None, None, False, None, _assert_test_6_num_players_one_primary),
    ("test_7_primary_agent_excluded", 1, "FRANCE", "gpt-4o", None, ["FRANCE"], False, None, _assert_test_7_primary_agent_excluded),
    ("test_8a_toml_limited_players", 2, None, None, None, None, False, TOML_CONTENT_TEST_8, _assert_test_8a_toml_respected_limited_players),
    ("test_8b_toml_all_players", 7, None, None, None, None, False, TOML_CONTENT_TEST_8, _assert_test_8b_toml_respected_all_players),
    ("test_9_toml_cli_conflict", 1, "FRANCE", "cli_france_model_wins", None, None, False, TOML_CONTENT_TEST_9, _assert_test_9_toml_cli_conflict),
    ("test_10_num_players_limits_toml", 3, None, None, None, None, False, TOML_CONTENT_TEST_10, _assert_test_10_num_players_limits_toml),
    ("test_11_default_model_from_config", 2, None, None, None, None, False, TOML_CONTENT_TEST_11, _assert_test_11_default_model_from_config),
    ("test_12_fallback_model_no_default", 1, None, None, None, None, False, None, _assert_test_12_fallback_model_no_config_default),
]

@pytest.mark.parametrize(
    "test_id, num_players, cli_power_name, cli_model_id, fixed_models, exclude_powers, randomize_fixed, toml_content, assertion_fn",
    PARAMETRIZED_TEST_CASES,
    ids=[case[0] for case in PARAMETRIZED_TEST_CASES]
)
@pytest.mark.unit
def test_assign_models_parametrized(
    game_config_factory, tmp_path,
    test_id, num_players, cli_power_name, cli_model_id, fixed_models, exclude_powers, randomize_fixed, toml_content, assertion_fn
):
    logger.info(f"--- Running Parametrized Test Case: {test_id} ---")
    models_config_file_path = None
    if toml_content:
        models_config_file_path = tmp_path / f"{test_id}_models.toml"
        with open(models_config_file_path, "w") as f:
            f.write(toml_content)
    config = game_config_factory(
        num_players=num_players,
        power_name=cli_power_name,
        model_id=cli_model_id,
        fixed_models=fixed_models,
        exclude_powers=exclude_powers,
        randomize_fixed_models=randomize_fixed,
        models_config_file=str(models_config_file_path) if models_config_file_path else None,
        log_to_file=False
    )
    manager = AgentManager(config)
    assigned = manager.assign_models(ALL_POWERS_IN_GAME)
    logger.info(f"Test Case {test_id} Assigned: {assigned}")
    assertion_fn(assigned, manager, config, ALL_POWERS_IN_GAME)
    if assigned:
        manager.initialize_agents(assigned)
        assert len(manager.agents) == len(assigned)
        for power_name, model_id_assigned in assigned.items():
            assert power_name in manager.agents
            agent = manager.get_agent(power_name)
            assert agent is not None
            assert agent.country == power_name
            assert isinstance(agent, LLMAgent)
            assert agent.model_id == model_id_assigned
    else:
        manager.initialize_agents(assigned)
        assert len(manager.agents) == 0

logger.info("--- All AgentManager tests collected (parametrized) ---")
