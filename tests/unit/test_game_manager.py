import pytest
from ai_diplomacy.core.manager import GameEvent

@pytest.mark.unit
def test_game_event_creation():
    """Test GameEvent creation and basic attributes."""
    # We need a mock diplomacy Game for testing
    # For now, let's test what we can without the actual game

    # Test GameEvent creation
    event = GameEvent(
        event_type="unit_lost",
        phase="S1901M",
        participants={"country": "FRANCE", "unit": "A PAR"},
        details={"unit_type": "A"},
    )

    assert event.event_type == "unit_lost"
    assert event.participants["country"] == "FRANCE"
