from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from generic_llm_framework.llm_coordinator import LLMCoordinator # Updated import
import logging
from typing import List, Any, Optional, Dict
from datetime import datetime
import os  # Added for MinimalGameConfig_LoggingSetup


class LoggingMixin:
    def __init__(
        self, logger_name=None, **kwargs
    ):  # Added **kwargs to play nice with super() in multiple inheritance
        super().__init__(**kwargs)  # Ensure other parent initializers are called if any
        self.logger = logging.getLogger(logger_name or self.__class__.__name__)


class PhaseProviderMixin:
    # Subclasses should define _phase_attribute_name as a string
    # indicating the name of the attribute holding the phase string.
    _phase_attribute_name: str

    def get_current_phase(self):
        if not hasattr(self, self._phase_attribute_name):
            raise NotImplementedError(
                f"{self.__class__.__name__} must have an attribute named '{self._phase_attribute_name}' to use PhaseProviderMixin."
            )
        return getattr(self, self._phase_attribute_name)


class GameConfigAttributesMixin:
    def __init__(
        self,
        log_level="DEBUG",
        game_id="test_game_mixin",
        log_to_file=True,
        log_dir=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.log_level = log_level.upper() if isinstance(log_level, str) else "DEBUG"
        self.game_id = game_id
        self.log_to_file = log_to_file
        self.log_dir = log_dir
        # Common paths, can be overridden by subclasses if needed after super().__init__()
        if self.log_to_file:
            _base_log_dir = self.log_dir or os.path.join(
                os.getcwd(), "logs_mixin_default"
            )
            self.game_id_specific_log_dir = os.path.join(_base_log_dir, self.game_id)
            self.general_log_path = os.path.join(
                self.game_id_specific_log_dir, f"{self.game_id}_general.log"
            )
            self.llm_log_path = os.path.join(
                self.game_id_specific_log_dir, f"{self.game_id}_llm_interactions.csv"
            )
            os.makedirs(self.game_id_specific_log_dir, exist_ok=True)
        else:
            self.game_id_specific_log_dir = None
            self.general_log_path = None
            self.llm_log_path = None


class FakeGame(PhaseProviderMixin):
    _phase_attribute_name = (
        "_actual_phase_name"  # Define which attribute holds the phase
    )

    def __init__(
        self, phase, powers_names, build_conditions=None, retreat_conditions=None
    ):
        super().__init__()  # Initialize mixins if any in MRO
        self._actual_phase_name = phase  # Store phase in the designated attribute
        self.year = (
            int(phase[1:5])
            if phase and len(phase) >= 5 and phase[1:5].isdigit()
            else 1901
        )
        self.powers = {}
        for name in powers_names:
            n_builds_val = build_conditions.get(name, 0) if build_conditions else 0
            must_retreat_val = (
                retreat_conditions.get(name, False) if retreat_conditions else False
            )
            self.powers[name] = SimpleNamespace(
                is_eliminated=lambda: False,
                must_retreat=must_retreat_val,
                n_builds=n_builds_val,
            )

    # get_current_phase() is now inherited from PhaseProviderMixin
    def get_state(self):
        return {"centers": {}}


class DummyOrchestrator:
    def __init__(self, active_powers_list, game_config_mock, agent_manager_mock):
        self.active_powers = active_powers_list
        self.config = game_config_mock
        self.agent_manager = agent_manager_mock
        self._get_orders_for_power = AsyncMock(return_value=["A PAR B"])
        self.get_valid_orders_func = None


class FakeDiplomacyAgent:
    def __init__(self, power_name, model_id="mock_model"):
        self.power_name = power_name
        self.model_id = model_id
        self.goals = [f"Take over the world ({power_name})", "Make friends"]
        self.relationships = {"OTHER_POWER": "Neutral"}
        self.private_journal = [
            f"Journal Entry 1 for {power_name}",
            f"Journal Entry 2 for {power_name}",
        ]
        self.private_diary = [f"[S1901M] Diary entry for {power_name}"]

    def get_agent_info(
        self,
    ):
        return {
            "agent_id": f"mock_agent_{self.power_name}",
            "country": self.power_name,
            "type": self.__class__.__name__,
            "model_id": self.model_id,
        }


class FakeGameHistory:
    def __init__(self):
        self.phases = [
            {"name": "SPRING 1901M", "orders_by_power": {"FRANCE": ["A PAR H"]}},
            {
                "name": "AUTUMN 1901M",
                "orders_by_power": {"FRANCE": ["A PAR - BUR"]},
            },
        ]

    def to_dict(self):
        return {"phases": self.phases}


class FakeDiplomacyGame(PhaseProviderMixin):
    _phase_attribute_name = "_current_phase"  # Define which attribute holds the phase

    def __init__(self):
        super().__init__()
        self.is_game_done = True
        self._current_phase = "WINTER 1905"
        self._centers = {
            "FRANCE": ["PAR", "MAR", "BRE", "SPA", "POR", "BEL", "HOL"],
            "ENGLAND": ["LON", "LVP", "EDI", "NWY", "SWE"],
            "GERMANY": ["BER", "MUN", "KIE", "DEN", "RUH", "WAR", "MOS"],
        }
        self._winners = ["GERMANY"]

    # get_current_phase() is now inherited

    def get_state(self):
        return {"centers": self._centers}

    def get_winners(self):
        return self._winners


class FakeLLMCoordinator(LLMCoordinator):
    async def request(
        self,
        model_id,
        prompt_text,
        system_prompt_text,
        game_id="test_game",
        agent_name="test_agent",
        phase_str="test_phase",
        request_identifier="request",
        llm_caller_override=None,
    ):
        return "This is a dummy LLM response."


class MockLLMInterface_PhaseSummary(LoggingMixin):
    def __init__(self, power_name="FRANCE", **kwargs):
        logger_name = f"MockLLMInterface_PhaseSummary.{power_name}"
        super().__init__(logger_name=logger_name, **kwargs)
        self.power_name = power_name

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
        self.logger.info(
            f"request called for {phase_str} by {agent_name} with prompt: {prompt_text[:50]}..."
        )
        return f"This is a generated summary for {agent_name} for phase {phase_str}. Events: ..."


class MockGame_PhaseSummary(PhaseProviderMixin):
    _phase_attribute_name = (
        "current_short_phase"  # Define which attribute holds the phase
    )

    def __init__(self, current_phase_name="SPRING 1901M"):
        super().__init__()
        self.current_short_phase = current_phase_name
        self.powers = {"FRANCE": None, "GERMANY": None}

    # get_current_phase() is now inherited


class MockPhase_PhaseSummary:
    def __init__(self, name):
        self.name = name
        self.orders_by_power = {}
        self.messages = []
        self.phase_summaries = {}

    def add_phase_summary(self, power_name, summary):
        self.phase_summaries[power_name] = summary


class MockGameHistory_PhaseSummary:
    def __init__(self):
        self.phases_by_name: Dict[str, MockPhase_PhaseSummary] = {}
        self.current_phase_name: Optional[str] = None
        self.all_phases: List[MockPhase_PhaseSummary] = []

    def add_phase(self, phase_name: str):
        if phase_name not in self.phases_by_name:
            phase = MockPhase_PhaseSummary(phase_name)
            self.phases_by_name[phase_name] = phase
            self.all_phases.append(phase)
            self.current_phase_name = phase_name

    def get_phase_by_name(self, name_to_find: str) -> Optional[MockPhase_PhaseSummary]:
        return self.phases_by_name.get(name_to_find)

    def get_current_phase(self) -> Optional[MockPhase_PhaseSummary]:
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


class MockArgs_LoggingSetup(GameConfigAttributesMixin):
    def __init__(
        self,
        log_level="DEBUG",
        game_id="test_log_game_conftest",
        log_to_file=True,
        log_dir=None,
        # Additional attributes specific to MockArgs_LoggingSetup
        game_id_prefix="test_log_conftest_mockargs",  # Different default
        power_name=None,
        model_id=None,
        num_players=7,
        perform_planning_phase=False,
        num_negotiation_rounds=3,
        negotiation_style="simultaneous",
        fixed_models=None,
        randomize_fixed_models=False,
        exclude_powers=None,
        max_years=None,
        dev_mode=False,
        verbose_llm_debug=False,
        max_diary_tokens=6500,
        models_config_file="models.toml",
    ):
        super().__init__(
            log_level=log_level,
            game_id=game_id,
            log_to_file=log_to_file,
            log_dir=log_dir,
        )
        # Attributes specific to MockArgs or that override/extend mixin behavior
        self.game_id_prefix = game_id_prefix
        self.power_name = power_name
        self.model_id = model_id
        self.num_players = num_players
        self.perform_planning_phase = perform_planning_phase
        self.num_negotiation_rounds = num_negotiation_rounds
        self.negotiation_style = negotiation_style
        self.fixed_models = fixed_models
        self.randomize_fixed_models = randomize_fixed_models
        self.exclude_powers = exclude_powers
        self.max_years = max_years
        self.dev_mode = dev_mode
        self.verbose_llm_debug = verbose_llm_debug
        self.max_diary_tokens = max_diary_tokens
        self.models_config_file = models_config_file
        # Note: current_datetime_str is not part of GameConfigAttributesMixin directly,
        # but MinimalGameConfig_LoggingSetup adds it. MockArgs_LoggingSetup does not seem to need it.


class MinimalGameConfig_LoggingSetup(GameConfigAttributesMixin):
    """Minimal GameConfig for testing logging setup without full GameConfig overhead."""

    def __init__(
        self,
        log_level="DEBUG",
        game_id="test_log_game_conftest_minimal",  # Different default
        log_to_file=True,
        log_dir=None,
        verbose_llm_debug=False,
    ):
        # Call mixin's __init__ to set up common attributes like log_level, game_id, log_paths
        super().__init__(
            log_level=log_level,
            game_id=game_id,
            log_to_file=log_to_file,
            log_dir=log_dir,
        )

        # Attributes specific to MinimalGameConfig or that override/extend mixin behavior
        self.verbose_llm_debug = verbose_llm_debug
        self.current_datetime_str = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Overwrite log paths if custom logic is needed beyond what mixin provides
        # For example, if base_log_dir logic is different:
        if (
            log_dir is None
        ):  # This check is also in mixin, but can be more specific here
            self.base_log_dir = os.path.join(os.getcwd(), "logs_minimal_specific")
        else:
            self.base_log_dir = log_dir

        # Re-generate paths if base_log_dir changed or other specific logic:
        if self.log_to_file:
            self.game_id_specific_log_dir = os.path.join(
                self.base_log_dir, self.game_id
            )
            self.general_log_path = os.path.join(
                self.game_id_specific_log_dir, f"{self.game_id}_general.log"
            )
            self.llm_log_path = os.path.join(
                self.game_id_specific_log_dir, f"{self.game_id}_llm_interactions.csv"
            )
            os.makedirs(self.game_id_specific_log_dir, exist_ok=True)
        else:  # Ensure these are None if log_to_file is False, overriding mixin
            self.game_id_specific_log_dir = None
            self.general_log_path = None
            self.llm_log_path = None
