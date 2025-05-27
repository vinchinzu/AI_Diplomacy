import pytest
from unittest.mock import MagicMock
from ai_diplomacy.utils.phase_parsing import get_phase_type_from_game, _extract_year_from_phase, PhaseType

# Test cases for get_phase_type_from_game
@pytest.mark.parametrize(
    "phase_string, expected_type",
    [
        ("SPRING 1901 MOVEMENT", PhaseType.MVT.value),
        ("S1901M", PhaseType.MVT.value),
        ("FALL 1902 RETREAT", PhaseType.RET.value),
        ("F1902R", PhaseType.RET.value),
        ("WINTER 1903 ADJUSTMENTS", PhaseType.BLD.value),
        ("W1903A", PhaseType.BLD.value),
        ("winter 1903 adjustments", PhaseType.BLD.value), # Lowercase
        ("Spring 1901 Movement", PhaseType.MVT.value), # Mixed case
        ("FORMING", "-"),
        ("COMPLETED", "-"),
        ("S1901MVT", PhaseType.MVT.value), # another variation of MVT
        ("AUTUMN 1901 BUILD", PhaseType.BLD.value), # another variation of BLD/Adjustments
        ("A1901B", PhaseType.BLD.value), # variation
    ],
)
def test_get_phase_type_from_game_valid(phase_string, expected_type):
    mock_game = MagicMock()
    mock_game.get_current_phase.return_value = phase_string
    assert get_phase_type_from_game(mock_game) == expected_type

@pytest.mark.parametrize(
    "invalid_phase_string",
    [
        ("X1901Z"),
        ("SUMMER 1904 PICNIC"),
        ("S190B"), # Invalid compact form
        ("SPRANG 1901 MOVEMENT"), # Misspelled season
    ]
)
def test_get_phase_type_from_game_invalid(invalid_phase_string):
    mock_game = MagicMock()
    mock_game.get_current_phase.return_value = invalid_phase_string
    with pytest.raises(RuntimeError):
        get_phase_type_from_game(mock_game)

def test_get_phase_type_from_game_empty_phase():
    mock_game = MagicMock()
    mock_game.get_current_phase.return_value = ""
    assert get_phase_type_from_game(mock_game) == "-"
    mock_game.get_current_phase.return_value = None
    assert get_phase_type_from_game(mock_game) == "-"

# Test cases for _extract_year_from_phase
@pytest.mark.parametrize(
    "phase_string, expected_year",
    [
        ("SPRING 1901 MOVEMENT", 1901),
        ("S1901M", 1901),
        ("FALL 1902 RETREAT", 1902),
        ("F1902R", 1902),
        ("WINTER 1903 ADJUSTMENTS", 1903),
        ("W1903A", 1903),
        ("FORMING", None),
        ("COMPLETED", None),
        ("S1901MVT", 1901),
        ("AUTUMN 1901 BUILD", 1901),
        ("A1901B", 1901),
        ("Random String", None),
        ("S19ABM", None), # Non-digit year
        ("S190M", None), # Too short year
        ("S2023M", 2023), # Modern year
        ("Spring 2023 Movement", 2023),
        ("", None),
        (None, None),
    ],
)
def test_extract_year_from_phase(phase_string, expected_year):
    assert _extract_year_from_phase(phase_string) == expected_year 