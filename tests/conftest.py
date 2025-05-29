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
pytest.register_assert_rewrite("tests._diplomacy_fakes")
from tests._diplomacy_fakes import FakeGame, DummyOrchestrator, FakeDiplomacyAgent, FakeDiplomacyGame, FakeGameHistory # Added


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
# These will be moved to _diplomacy_fakes.py and renamed.

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


# Mock classes from ai_diplomacy.phase_summary for testing purposes
# TODO: Consider moving these to a more specific fixture file e.g. tests/fixtures/phase_summary_fixtures.py


class MockLLMInterface_PhaseSummary:  # Renamed to avoid conflict if other MockLLMInterfaces exist
    def __init__(self, power_name="FRANCE"):
        self.power_name = power_name
        self.logger = logging.getLogger(f"MockLLMInterface_PhaseSummary.{power_name}")

    async def request(
        self,
        model_id,
        prompt_text,
        system_prompt_text,
        game_id,
        agent_name,
        phase_str,
        request_identifier,
    ):
        # This mock simulate the request method of LLMCoordinator,
        # as PhaseSummaryGenerator uses llm_coordinator.request
        self.logger.info(
            f"request called for {phase_str} by {agent_name} with prompt: {prompt_text[:50]}..."
        )
        return f"This is a generated summary for {agent_name} for phase {phase_str}. Events: ..."


class MockGame_PhaseSummary:  # Renamed to avoid conflict
    def __init__(self, current_phase_name="SPRING 1901M"):
        self.current_short_phase = current_phase_name
        self.powers = {"FRANCE": None, "GERMANY": None}  # Dummy powers

    def get_current_phase(self):  # Ensure this method exists
        return self.current_short_phase


class MockPhase_PhaseSummary:  # Renamed
    def __init__(self, name):
        self.name = name
        self.orders_by_power = {}
        self.messages = []
        self.phase_summaries = {}

    def add_phase_summary(self, power_name, summary):
        self.phase_summaries[power_name] = summary


class MockGameHistory_PhaseSummary:  # Renamed
    def __init__(self):
        self.phases_by_name: Dict[str, MockPhase_PhaseSummary] = {} # Use renamed
        self.current_phase_name: Optional[str] = None
        self.all_phases: List[MockPhase_PhaseSummary] = [] # Use renamed

    def add_phase(self, phase_name: str):
        if phase_name not in self.phases_by_name:
            phase = MockPhase_PhaseSummary(phase_name) # Use renamed
            self.phases_by_name[phase_name] = phase
            self.all_phases.append(phase)
            self.current_phase_name = phase_name

    def get_phase_by_name(
        self, name_to_find: str
    ) -> Optional[MockPhase_PhaseSummary]:  # Use renamed
        return self.phases_by_name.get(name_to_find)

    def get_current_phase(self) -> Optional[MockPhase_PhaseSummary]: # Use renamed
        if self.current_phase_name:
            return self.phases_by_name.get(self.current_phase_name)
        return None

    def get_messages_by_phase(self, phase_name: str) -> List[Any]:
        phase = self.get_phase_by_name(phase_name)
        return phase.messages if phase else []

    def add_phase_summary(self, phase_name: str, power_name: str, summary: str):
        phase = self.get_phase_by_name(phase_name)
        if phase:
            phase.add_phase_summary(power_name, summary)


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


# Mock classes from ai_diplomacy.logging_setup for testing purposes
# TODO: Consider moving these to a more specific fixture file e.g. tests/fixtures/logging_fixtures.py


class MockArgs_LoggingSetup:
    def __init__(
        self,
        log_level="DEBUG",
        game_id="test_log_game_conftest",
        log_to_file=True,
        log_dir=None,
    ):
        self.log_level = log_level
        self.game_id_prefix = "test_log_conftest"
        self.game_id = game_id
        # self.current_datetime_str = datetime.now().strftime("%Y%m%d_%H%M%S") # Not needed by MinimalGameConfig_LoggingSetup
        self.log_to_file = log_to_file
        self.log_dir = log_dir
        # Attributes GameConfig expects from args, that MinimalGameConfig_LoggingSetup might not use directly
        # but could be part of a fuller GameConfig mock if this were to replace it.
        self.power_name = None
        self.model_id = None
        self.num_players = 7
        self.perform_planning_phase = False
        self.num_negotiation_rounds = 3
        self.negotiation_style = "simultaneous"
        self.fixed_models = None
        self.randomize_fixed_models = False
        self.exclude_powers = None
        self.max_years = None
        self.dev_mode = False  # Added as GameConfig might expect it
        self.verbose_llm_debug = False  # Added as GameConfig might expect it
        self.max_diary_tokens = 6500  # Added
        self.models_config_file = "models.toml"  # Added


# This MinimalGameConfig_LoggingSetup is quite different from the main GameConfig
# as it only sets a few attributes. It's used by test_logging_setup.py.
# It does not call super().__init__(args) with an argparse.Namespace.
# For now, let this remain as is, as its usage is specific.
# If it were to be a full GameConfig, it would use the factory.
class MinimalGameConfig_LoggingSetup:
    """Minimal GameConfig for testing logging setup without full GameConfig overhead."""

    def __init__(
        self,
        log_level="DEBUG",
        game_id="test_log_game_conftest",
        log_to_file=True,
        log_dir=None,
        verbose_llm_debug=False, # Added verbose_llm_debug
    ):
        self.log_level = log_level.upper()
        self.game_id = game_id
        self.log_to_file = log_to_file
        self.current_datetime_str = datetime.now().strftime("%Y%m%d_%H%M%S")

        if log_dir is None:
            self.base_log_dir = os.path.join(os.getcwd(), "logs_conftest_minimal")
        else:
            self.base_log_dir = log_dir

        self.game_id_specific_log_dir = os.path.join(self.base_log_dir, self.game_id)
        self.general_log_path = os.path.join(
            self.game_id_specific_log_dir, f"{self.game_id}_general.log"
        )
        self.llm_log_path = os.path.join( # Added llm_log_path
            self.game_id_specific_log_dir, f"{self.game_id}_llm_interactions.csv"
        )
        self.verbose_llm_debug = verbose_llm_debug # Added verbose_llm_debug

        # Ensure log directory exists if logging to file
        if self.log_to_file:
            os.makedirs(self.game_id_specific_log_dir, exist_ok=True)


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
def fake_game_factory(): # Removed FakeGame parameter
    # FakeGame class is imported at the top of this file from ._diplomacy_fakes
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
def default_dummy_orchestrator(mock_game_config_for_orchestrator, mock_agent_manager_for_orchestrator): # Removed DummyOrchestrator parameter
    # DummyOrchestrator class is imported at the top of this file from ._diplomacy_fakes
    default_powers = ["FRANCE", "GERMANY"]
    orchestrator = DummyOrchestrator(default_powers, mock_game_config_for_orchestrator, mock_agent_manager_for_orchestrator)
    orchestrator._get_orders_for_power = AsyncMock(return_value=["WAIVE"]) # Default behavior
    return orchestrator
