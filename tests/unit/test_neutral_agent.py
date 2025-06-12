import pytest
from unittest.mock import MagicMock

from ai_diplomacy.agents.neutral_agent import NeutralAgent
from ai_diplomacy.core.order import Order
from ai_diplomacy.core.state import PhaseState  # Removed PowerState


@pytest.fixture
def neutral_agent_france():
    return NeutralAgent(agent_id="neutral_france_test", country="FRANCE")


@pytest.fixture
def phase_state_with_units():
    mock_phase = MagicMock(spec=PhaseState)
    mock_phase.name = "S1901M"
    mock_phase.year = 1901
    mock_phase.season = "SPRING"

    # Mock the game object and its get_units method, as HoldBehaviourMixin will fallback to this
    mock_game = MagicMock()
    mock_game.get_units = MagicMock(return_value=["A PAR", "F MAR"])
    mock_phase.game = mock_game

    # Ensure get_power_units returns an empty list to trigger the fallback to game.get_units
    mock_phase.get_power_units.return_value = []

    return mock_phase


def test_neutral_agent_initialization(neutral_agent_france):
    assert neutral_agent_france.country == "FRANCE"
    assert neutral_agent_france.model_id == "neutral"
    info = neutral_agent_france.get_agent_info()
    assert info["type"] == "NeutralAgent"
    assert info["country"] == "FRANCE"


@pytest.mark.asyncio
async def test_neutral_agent_decide_orders_empty(neutral_agent_france):
    # Test with a phase state where the neutral power has no units
    mock_phase_no_units = MagicMock(spec=PhaseState)
    mock_game_no_units = MagicMock()
    mock_game_no_units.get_units = MagicMock(return_value=[])
    mock_phase_no_units.game = mock_game_no_units

    # Make get_power_units return an empty list to allow fallback (which also returns [])
    mock_phase_no_units.get_power_units.return_value = []

    orders = await neutral_agent_france.decide_orders(mock_phase_no_units)
    assert orders == []


@pytest.mark.asyncio
async def test_neutral_agent_decide_orders_with_units(neutral_agent_france, phase_state_with_units):
    orders = await neutral_agent_france.decide_orders(phase_state_with_units)
    assert len(orders) == 2
    assert Order("A PAR HLD") in orders
    assert Order("F MAR HLD") in orders
    # Ensure game.get_units was called for the correct country (FRANCE)
    # as HoldBehaviourMixin will use this fallback.
    phase_state_with_units.game.get_units.assert_called_with("FRANCE")


@pytest.mark.asyncio
async def test_neutral_agent_negotiate(neutral_agent_france, phase_state_with_units):
    messages = await neutral_agent_france.negotiate(phase_state_with_units)
    assert messages == []


@pytest.mark.asyncio
async def test_neutral_agent_update_state(neutral_agent_france, phase_state_with_units):
    # update_state has no return value, just call it to ensure no errors
    await neutral_agent_france.update_state(phase_state_with_units, [])
    # No assertions needed beyond successful execution
