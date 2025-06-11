import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from pathlib import Path
from ai_diplomacy.services.config import AgentConfig
from generic_llm_framework.llm_coordinator import LLMCoordinator  # Updated import
from ai_diplomacy.services.context_provider import (
    ContextProviderFactory,
    ContextProvider,
)
from ai_diplomacy.core.state import PhaseState
from typing import List

# Import the shared factory
from ._shared_fixtures import create_game_config
from ai_diplomacy.game_config import GameConfig

# Register assert rewrite for fakes
pytest.register_assert_rewrite("tests.fakes")
import tests.fakes as fakes_module


@pytest.fixture
def cfg_file() -> Path:
    """Returns the path to the dummy config file."""
    # This path is relative to conftest.py
    return Path(__file__).parent / "fixtures" / "dummy_config.toml"


@pytest.fixture
def agent_cfg_builder():
    """
    Returns a builder function for AgentConfig.
    The builder injects a default 'context_provider'.
    """
    from ai_diplomacy.services.config import AgentConfig

    def _builder(**kwargs) -> AgentConfig:
        data = {}
        # Set default, but allow override
        if "context_provider" not in kwargs:
            data["context_provider"] = "inline"

        data.update(kwargs)

        # 'name' and 'type' are mandatory, tests must provide them.
        return AgentConfig(**data)

    return _builder


@pytest.fixture
def agent_config(agent_cfg_builder):
    """Provides a default, valid AgentConfig instance."""
    return agent_cfg_builder(name="ENGLAND", type="llm", model_id="test_model")


@pytest.fixture
def mock_llm_coordinator():
    return AsyncMock(spec=LLMCoordinator, autospec=True)


@pytest.fixture
def mock_context_provider():
    provider = AsyncMock(spec=ContextProvider, autospec=True)
    provider.provide_context = AsyncMock(
        return_value={
            "context_text": "Mocked context",
            "tools_available": False,
            "tools": [],
            "provider_type": "mock_inline",
        }
    )
    return provider


@pytest.fixture
def mock_context_provider_factory(mock_context_provider):
    factory = Mock(spec=ContextProviderFactory, autospec=True)
    factory.get_provider.return_value = mock_context_provider
    return factory


@pytest.fixture
def mock_phase_state():
    phase_state = AsyncMock(spec=PhaseState, autospec=True)
    phase_state.phase_name = "S1901M"
    phase_state.get_power_units = Mock(return_value=["A LON", "F EDI"])
    phase_state.get_power_centers = Mock(return_value=["LON", "EDI"])
    phase_state.is_game_over = False
    phase_state.powers = ["ENGLAND", "FRANCE", "GERMANY"]
    phase_state.is_power_eliminated = Mock(return_value=False)
    return phase_state


@pytest.fixture
def mock_load_prompt_file_func():
    return lambda filename: "Mocked system prompt from new func"


@pytest.fixture
def mock_game_config_results(tmp_path) -> GameConfig:
    return create_game_config(
        game_id="results_test_game", log_dir=str(tmp_path / "test_results_logs")
    )


@pytest.fixture
def mock_diplomacy_agent_france():
    return fakes_module.FakeDiplomacyAgent("FRANCE")


@pytest.fixture
def mock_diplomacy_agent_germany():
    return fakes_module.FakeDiplomacyAgent("GERMANY", model_id="gpt-4-mini")


@pytest.fixture
def mock_game_history_results():
    return fakes_module.FakeGameHistory()


@pytest.fixture
def mock_diplomacy_game():
    return fakes_module.FakeDiplomacyGame()


@pytest.fixture
def mock_llm_interface_phase_summary():
    return fakes_module.MockLLMInterface_PhaseSummary()


@pytest.fixture
def mock_game_phase_summary():
    return fakes_module.MockGame_PhaseSummary()


@pytest.fixture
def mock_game_history_phase_summary():
    return fakes_module.MockGameHistory_PhaseSummary()


@pytest.fixture
def mock_game_config_phase_summary(tmp_path) -> GameConfig:
    return create_game_config(
        game_id="test_phase_summary",
        power_name="FRANCE",
        model_id="default_summary_model",
        log_dir=str(tmp_path / "test_phase_summary_logs"),
    )


@pytest.fixture
def mock_args_logging_setup():
    return fakes_module.MockArgs_LoggingSetup()


@pytest.fixture
def minimal_game_config_logging_setup_debug_verbose_false(tmp_path):
    log_dir = tmp_path / "minimal_log_debug_vfalse"
    log_dir.mkdir()
    return fakes_module.MinimalGameConfig_LoggingSetup(
        log_level="DEBUG",
        log_to_file=True,
        log_dir=str(log_dir),
        verbose_llm_debug=False,
    )


@pytest.fixture
def minimal_game_config_logging_setup_debug_verbose_true(tmp_path):
    log_dir = tmp_path / "minimal_log_debug_vtrue"
    log_dir.mkdir()
    return fakes_module.MinimalGameConfig_LoggingSetup(
        log_level="DEBUG",
        log_to_file=True,
        log_dir=str(log_dir),
        verbose_llm_debug=True,
    )


@pytest.fixture
def minimal_game_config_logging_setup_info_verbose_false(tmp_path):
    log_dir = tmp_path / "minimal_log_info_vfalse"
    log_dir.mkdir()
    return fakes_module.MinimalGameConfig_LoggingSetup(
        log_level="INFO",
        log_to_file=True,
        log_dir=str(log_dir),
        verbose_llm_debug=False,
    )


@pytest.fixture
def fake_game_factory(fakes_module_param):
    def _create_fake_game(
        phase="S1901M",
        powers_names=None,
        build_conditions=None,
        retreat_conditions=None,
    ):
        if powers_names is None:
            powers_names = ["FRANCE", "GERMANY"]
        return fakes_module.FakeGame(
            phase, powers_names, build_conditions, retreat_conditions
        )

    return _create_fake_game


@pytest.fixture
def mock_game_config_for_orchestrator():
    return MagicMock(spec=GameConfig, spec_set=True, autospec=True)


@pytest.fixture
def mock_agent_manager_for_orchestrator():
    from ai_diplomacy.agent_manager import AgentManager

    manager = MagicMock(spec=AgentManager, spec_set=True, autospec=True)
    manager.get_agent = MagicMock()
    return manager


@pytest.fixture
def default_dummy_orchestrator(
    mock_game_config_for_orchestrator, mock_agent_manager_for_orchestrator
):
    default_powers = ["FRANCE", "GERMANY"]
    orchestrator = fakes_module.DummyOrchestrator(
        default_powers,
        mock_game_config_for_orchestrator,
        mock_agent_manager_for_orchestrator,
    )
    orchestrator._get_orders_for_power = AsyncMock(return_value=["WAIVE"])
    return orchestrator


ALL_POWERS_IN_GAME_CONSTANT = [  # Renamed to avoid conflict if a global was imported elsewhere
    "AUSTRIA",
    "ENGLAND",
    "FRANCE",
    "GERMANY",
    "ITALY",
    "RUSSIA",
    "TURKEY",
]


@pytest.fixture
def all_powers() -> List[str]:
    return (
        ALL_POWERS_IN_GAME_CONSTANT.copy()
    )  # Return a copy to prevent modification by tests
