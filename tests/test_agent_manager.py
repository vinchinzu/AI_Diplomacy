import logging
import pytest
from unittest.mock import patch

from ai_diplomacy.agent_manager import AgentManager
from ai_diplomacy.agents.llm_agent import LLMAgent
from tests._shared_fixtures import create_game_config
from tests.fixtures.assertions_agent_manager import assertion_map

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


@pytest.fixture
def game_config_factory():
    return create_game_config


PARAMETRIZED_TEST_CASES = [
    (
        "test_1_basic_assignment",
        2,
        None,
        None,
        ["ollama/modelA", "ollama/modelB"],
        None,
        False,
        None,
    ),
    (
        "test_2_primary_agent_specified",
        3,
        "FRANCE",
        "gpt-4o",
        ["ollama/modelC"],
        None,
        False,
        None,
    ),
    (
        "test_3_exclude_powers_randomize",
        2,
        None,
        None,
        ["modelX", "modelY", "modelZ"],
        ["ITALY", "TURKEY"],
        True,
        None,
    ),
    (
        "test_4_not_enough_fixed_models",
        3,
        None,
        None,
        ["only_one_model"],
        None,
        False,
        None,
    ),
    ("test_5_num_players_zero", 0, None, None, None, None, False, None),
    (
        "test_6_num_players_one_primary",
        1,
        "GERMANY",
        "claude-3",
        None,
        None,
        False,
        None,
    ),
    (
        "test_7_primary_agent_excluded",
        1,
        "FRANCE",
        "gpt-4o",
        None,
        ["FRANCE"],
        False,
        None,
    ),
    (
        "test_8a_toml_limited_players",
        2,
        None,
        None,
        None,
        None,
        False,
        TOML_CONTENT_TEST_8,
    ),
    ("test_8b_toml_all_players", 7, None, None, None, None, False, TOML_CONTENT_TEST_8),
    (
        "test_9_toml_cli_conflict",
        1,
        "FRANCE",
        "cli_france_model_wins",
        None,
        None,
        False,
        TOML_CONTENT_TEST_9,
    ),
    (
        "test_10_num_players_limits_toml",
        3,
        None,
        None,
        None,
        None,
        False,
        TOML_CONTENT_TEST_10,
    ),
    (
        "test_11_default_model_from_config",
        2,
        None,
        None,
        None,
        None,
        False,
        TOML_CONTENT_TEST_11,
    ),
    ("test_12_fallback_model_no_default", 1, None, None, None, None, False, None),
]


@pytest.mark.parametrize(
    "test_id, num_players, cli_power_name, cli_model_id, fixed_models, exclude_powers, randomize_fixed, toml_content",
    PARAMETRIZED_TEST_CASES,
    ids=[case[0] for case in PARAMETRIZED_TEST_CASES],
)
@pytest.mark.unit
def test_assign_models_parametrized(
    game_config_factory,
    tmp_path,
    all_powers,
    test_id,
    num_players,
    cli_power_name,
    cli_model_id,
    fixed_models,
    exclude_powers,
    randomize_fixed,
    toml_content,
):
    logger.info(f"--- Running Parametrized Test Case: {test_id} ---")
    models_config_file_path = None
    if toml_content:
        models_config_file_path = tmp_path / f"{test_id}_models.toml"
        with open(models_config_file_path, "w") as f:
            f.write(toml_content)

    config_params = {
        "num_players": num_players,
        "power_name": cli_power_name,
        "model_id": cli_model_id,
        "fixed_models": fixed_models,
        "exclude_powers": exclude_powers,
        "randomize_fixed_models": randomize_fixed,
        "models_config_file": str(models_config_file_path)
        if models_config_file_path
        else None,
        "log_to_file": False,
    }
    config_params = {
        k: v
        for k, v in config_params.items()
        if v is not None or k == "models_config_file"
    }

    config = game_config_factory(**config_params)
    manager = AgentManager(config)

    assigned = manager.assign_models(all_powers)
    logger.info(f"Test Case {test_id} Assigned: {assigned}")

    current_assertion_fn = assertion_map[test_id]
    current_assertion_fn(assigned, manager, config, all_powers)

    with patch(
        "ai_diplomacy.agents.llm_agent.LLMAgent.__init__",
        return_value=None,
        autospec=True,
    ) as mock_llm_agent_init:
        if assigned:
            manager.initialize_agents(assigned)
            assert len(manager.agents) == len(assigned)
            assert mock_llm_agent_init.call_count == len(assigned)

            actual_calls_summary = []
            for call_args_tuple in mock_llm_agent_init.call_args_list:
                _, kwargs = call_args_tuple
                actual_calls_summary.append(
                    {
                        "power_name": kwargs.get("power_name"),
                        "model_id": kwargs.get("model_id"),
                    }
                )

            for power_name_assigned, model_id_assigned in assigned.items():
                expected_call_found = False
                for call_kwargs in mock_llm_agent_init.call_args_list:
                    actual_kwargs = call_kwargs[1]
                    if (
                        actual_kwargs.get("power_name") == power_name_assigned
                        and actual_kwargs.get("model_id") == model_id_assigned
                        and actual_kwargs.get("config") == config
                        and actual_kwargs.get("llm_coordinator")
                        == manager.llm_coordinator
                    ):
                        expected_call_found = True
                        break
                assert expected_call_found, (
                    f"LLMAgent.__init__ not called correctly for power {power_name_assigned} with model {model_id_assigned}.\nActual calls: {actual_calls_summary}"
                )

                agent_instance = manager.get_agent(power_name_assigned)
                assert agent_instance is not None
                assert isinstance(agent_instance, LLMAgent)

            if test_id == "test_6_num_players_one_primary":
                assert manager.get_agent("FRANCE") is None
            elif test_id == "test_7_primary_agent_excluded":
                assert manager.get_agent("FRANCE") is None

        else:
            manager.initialize_agents(assigned)
            assert len(manager.agents) == 0
            assert mock_llm_agent_init.call_count == 0


logger.info("--- All AgentManager tests collected (parametrized) ---")
