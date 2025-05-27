import pytest
from unittest.mock import MagicMock, AsyncMock, patch
# Remove other unittest imports if not used by pytest tests or MockGame.

from ai_diplomacy.orchestrators.phase_orchestrator import GamePhaseOrchestrator, PhaseType
from ai_diplomacy.game_config import GameConfig
from ai_diplomacy.general_utils import gather_possible_orders
# diplomacy.Game might be needed if MockGame directly inherits or uses it for spec, but here it's self-contained.
# from diplomacy import Game


# Mock Game class for testing get_phase_type_from_game
class MockGame:
    def __init__(self, current_phase: str):
        self._current_phase = current_phase

    def get_current_phase(self) -> str:
        return self._current_phase

    # Minimal __getattr__ for robustness if other attributes are accidentally accessed by the tested method
    # though get_phase_type_from_game only uses get_current_phase().
    def __getattr__(self, name):
        if name == "phase":  # common alias for current_phase in some contexts
            return self._current_phase
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )


@pytest.mark.parametrize(
    "phase_string, expected_type",
    [
        ("S1901M", PhaseType.MVT.value),
        ("SPRING 1901 MOVEMENT", PhaseType.MVT.value),
        ("F1901R", PhaseType.RET.value),
        ("FALL 1901 RETREAT", PhaseType.RET.value),
        ("W1901A", PhaseType.BLD.value),
        ("WINTER 1901 ADJUSTMENT", PhaseType.BLD.value),
        ("WINTER 1901 BUILD", PhaseType.BLD.value),
        (
            "AUTUMN 1905 ADJUSTMENTS",
            PhaseType.BLD.value,
        ),  # Test with 'ADJUSTMENTS' (plural)
        ("FORMING", "-"),
        ("COMPLETED", "-"),
        ("S1902M", PhaseType.MVT.value),  # Another movement
        (
            "F1903 RET",
            PhaseType.RET.value,
        ),  # Slightly different retreat format (short season)
        (
            "WINTER 1904 BLD",
            PhaseType.BLD.value,
        ),  # Slightly different build format (short keyword)
        ("SPR 1901 M", PhaseType.MVT.value),  # Abbreviated season and type
        ("FAL 1901 R", PhaseType.RET.value),  # Abbreviated season and type
        ("WIN 1901 A", PhaseType.BLD.value),  # Abbreviated season and type
    ],
)
def test_get_phase_type_from_game_valid(phase_string, expected_type):
    """Tests get_phase_type_from_game with various valid phase strings."""
    mock_game = MockGame(current_phase=phase_string)
    assert GamePhaseOrchestrator.get_phase_type_from_game(mock_game) == expected_type


def test_get_phase_type_from_game_invalid_format():
    """Tests get_phase_type_from_game with an unknown phase string, expecting RuntimeError."""
    mock_game = MockGame(current_phase="XYZ1234 UNKNOWN_PHASE")
    with pytest.raises(RuntimeError) as excinfo:
        GamePhaseOrchestrator.get_phase_type_from_game(mock_game)
    assert "Unknown or unhandled phase format: 'XYZ1234 UNKNOWN_PHASE'" in str(
        excinfo.value
    )


def test_get_phase_type_from_game_empty_phase():
    """Tests get_phase_type_from_game with an empty phase string, expecting '-'."""
    mock_game = MockGame(current_phase="")
    assert GamePhaseOrchestrator.get_phase_type_from_game(mock_game) == "-"


# If you need to test GamePhaseOrchestrator instances, you might use a fixture like this:
# @pytest.fixture
# def orchestrator_fixture():
#     mock_game_config = Mock(spec=GameConfig) # Assuming GameConfig is defined/imported
#     mock_agent_manager = Mock(spec=AgentManager) # Assuming AgentManager is defined/imported
#     mock_get_valid_orders_func = AsyncMock() # If the function is async
#     orchestrator = GamePhaseOrchestrator(
#         game_config=mock_game_config,
#         agent_manager=mock_agent_manager,
#         get_valid_orders_func=mock_get_valid_orders_func
#     )
#     return orchestrator
