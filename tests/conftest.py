import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from ai_diplomacy.services.config import AgentConfig
from ai_diplomacy.services.llm_coordinator import LLMCoordinator
from ai_diplomacy.services.context_provider import (
    ContextProviderFactory,
    ContextProvider,
)
from ai_diplomacy.core.state import PhaseState
from datetime import datetime
from typing import List, Any, Optional, Dict
import logging
import os
import pytest # Import pytest

# Import the shared factory
from ._shared_fixtures import create_game_config
from ai_diplomacy.game_config import GameConfig # Keep for type hinting if needed

# Register assert rewrite for fakes
# pytest.register_assert_rewrite("tests._diplomacy_fakes") # No longer needed
# from tests._diplomacy_fakes import FakeGame, DummyOrchestrator, FakeDiplomacyAgent, FakeDiplomacyGame, FakeGameHistory # No longer needed
pytest.register_assert_rewrite("tests.fakes")
from tests.fakes import ( # Added
    FakeGame,
    DummyOrchestrator,
    FakeDiplomacyAgent,
    FakeDiplomacyGame,
    FakeGameHistory,
    MockLLMInterface_PhaseSummary,
    MockGame_PhaseSummary,
    MockPhase_PhaseSummary,
    MockGameHistory_PhaseSummary,
    MockArgs_LoggingSetup,
    MinimalGameConfig_LoggingSetup,
)


@pytest.fixture
def agent_config():
    return AgentConfig(
        country="ENGLAND",
        type="llm",
        model_id="test_model",
        context_provider="inline",
    )


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
def mock_load_prompt_file_func(): # Renamed to reflect it returns a function
    return lambda filename: "Mocked system prompt from new func"

# Removed MockDiplomacyAgent, MockGameHistoryResults, MockDiplomacyGame
# These have been moved to tests/fakes/__init__.py

@pytest.fixture
def mock_game_config_results(tmp_path) -> GameConfig:
    # Using tmp_path to ensure log files (if any created by GameConfig) go to a temp dir
    # The factory defaults log_to_file=False, but if a test overrides it, this is safer.
    return create_game_config(game_id="results_test_game", log_dir=str(tmp_path / "test_results_logs"))


@pytest.fixture
def mock_diplomacy_agent_france():
    return FakeDiplomacyAgent("FRANCE") # Updated to use new class name


@pytest.fixture
def mock_diplomacy_agent_germany():
    return FakeDiplomacyAgent("GERMANY", model_id="gpt-4-mini") # Updated


@pytest.fixture
def mock_game_history_results():
    return FakeGameHistory() # Updated


@pytest.fixture
def mock_diplomacy_game():
    return FakeDiplomacyGame() # Updated


# Mock classes from ai_diplomacy.phase_summary have been moved to tests/fakes/__init__.py


@pytest.fixture
def mock_llm_interface_phase_summary():
    return MockLLMInterface_PhaseSummary()


@pytest.fixture
def mock_game_phase_summary():
    return MockGame_PhaseSummary()


@pytest.fixture
def mock_game_history_phase_summary():
    return MockGameHistory_PhaseSummary()


@pytest.fixture
def mock_game_config_phase_summary(tmp_path) -> GameConfig:
    # This fixture previously returned an instance of MockGameConfig_PhaseSummary.
    # Now it uses the factory, passing parameters that were specific to MockGameConfig_PhaseSummary.
    # The `power_name` and `model_id` were key customizations.
    # The llm_log_path was also overridden. GameConfig creates this path based on game_id and log_dir.
    # If a specific dummy path is needed, it might require post-modification or more complex factory options.
    # For now, let's rely on the factory's defaults and allow specific tests to override further if needed.
    # Note: The `agents` dict with `MockAgent_PhaseSummary` was part of the old mock config.
    # This is not something GameConfig itself holds directly in its constructor args.
    # If tests relied on config.agents, they will need to be adjusted or this mock needs to be more complex.
    # For now, creating a standard config. Tests can add mock agents to it if necessary.

    return create_game_config(
        game_id="test_phase_summary",
        power_name="FRANCE", # This was a param to MockGameConfig_PhaseSummary
        model_id="default_summary_model", # This was a param to MockGameConfig_PhaseSummary
        log_dir=str(tmp_path / "test_phase_summary_logs"),
        # llm_log_path was previously hardcoded to "dummy_llm_log.csv". 
        # The factory will generate one based on game_id and log_dir. If tests need a fixed one,
        # they might need to mock os.path.join or adjust assertions.
    )


# Mock classes from ai_diplomacy.logging_setup have been moved to tests/fakes/__init__.py


@pytest.fixture
def mock_args_logging_setup():
    return MockArgs_LoggingSetup()


@pytest.fixture
def minimal_game_config_logging_setup_debug_verbose_false(tmp_path):
    log_dir = tmp_path / "minimal_log_debug_vfalse"
    log_dir.mkdir()
    return MinimalGameConfig_LoggingSetup(log_level="DEBUG", log_to_file=True, log_dir=str(log_dir), verbose_llm_debug=False)


@pytest.fixture
def minimal_game_config_logging_setup_debug_verbose_true(tmp_path):
    log_dir = tmp_path / "minimal_log_debug_vtrue"
    log_dir.mkdir()
    return MinimalGameConfig_LoggingSetup(log_level="DEBUG", log_to_file=True, log_dir=str(log_dir), verbose_llm_debug=True)


@pytest.fixture
def minimal_game_config_logging_setup_info_verbose_false(tmp_path):
    log_dir = tmp_path / "minimal_log_info_vfalse"
    log_dir.mkdir()
    return MinimalGameConfig_LoggingSetup(log_level="INFO", log_to_file=True, log_dir=str(log_dir), verbose_llm_debug=False)


@pytest.fixture
def fake_game_factory():
    # FakeGame class is imported from tests.fakes
    def _create_fake_game(phase="S1901M", powers_names=None, build_conditions=None, retreat_conditions=None):
        if powers_names is None:
            powers_names = ["FRANCE", "GERMANY"]
        return FakeGame(phase, powers_names, build_conditions, retreat_conditions)
    return _create_fake_game

@pytest.fixture
def mock_game_config_for_orchestrator():
    return MagicMock(spec=GameConfig, autospec=True)

@pytest.fixture
def mock_agent_manager_for_orchestrator():
    from ai_diplomacy.agent_manager import AgentManager
    manager = MagicMock(spec=AgentManager, autospec=True)
    manager.get_agent = MagicMock()
    return manager

@pytest.fixture
def default_dummy_orchestrator(mock_game_config_for_orchestrator, mock_agent_manager_for_orchestrator):
    # DummyOrchestrator class is imported from tests.fakes
    default_powers = ["FRANCE", "GERMANY"]
    orchestrator = DummyOrchestrator(default_powers, mock_game_config_for_orchestrator, mock_agent_manager_for_orchestrator)
    orchestrator._get_orders_for_power = AsyncMock(return_value=["WAIVE"]) # Default behavior
    return orchestrator
