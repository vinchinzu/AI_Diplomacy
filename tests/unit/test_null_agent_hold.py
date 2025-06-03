import pytest
from unittest.mock import Mock, MagicMock

from ai_diplomacy.agents.neutral_agent import NeutralAgent
from ai_diplomacy.agents.base import Order
from ai_diplomacy.core.state import PhaseState

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_phase_state() -> MagicMock:
    """Creates a mock PhaseState object with a nested game mock."""
    phase_state = MagicMock(spec=PhaseState)
    phase_state.game = MagicMock()  # Mock the 'game' attribute
    return phase_state

async def test_neutral_agent_hold_orders_from_power_state(mock_phase_state: MagicMock):
    """
    Tests that NeutralAgent generates hold orders correctly using phase.get_power_state().units.
    """
    agent = NeutralAgent(agent_id="test_neutral_france", country="FRANCE")
    
    mock_power_state_france = MagicMock()
    mock_power_state_france.units = ["A PAR", "F MAR"]
    
    mock_phase_state.get_power_state.return_value = mock_power_state_france
    # Ensure fallback is not called or its return doesn't interfere
    mock_phase_state.game.get_units.return_value = [] 

    orders = await agent.decide_orders(mock_phase_state)

    mock_phase_state.get_power_state.assert_called_once_with("FRANCE")
    # We don't want to assert not_called for game.get_units because the mixin might try the first path,
    # fail due to structure (if units not directly there), then try the second.
    # The important part is that mock_power_state_france.units was the source.
    # If the first path in HoldBehaviourMixin's try block for power_state.units is successful,
    # phase.game.get_units should not be *relied upon*.

    assert len(orders) == 2
    assert Order("A PAR HLD") in orders
    assert Order("F MAR HLD") in orders
    # Check exact order objects if necessary, or just their string representations
    expected_orders = [Order("A PAR HLD"), Order("F MAR HLD")]
    assert all(o in orders for o in expected_orders) and len(orders) == len(expected_orders)

async def test_neutral_agent_hold_orders_fallback_to_game_get_units(mock_phase_state: MagicMock):
    """
    Tests that NeutralAgent generates hold orders correctly using phase.game.get_units()
    when phase.get_power_state().units is not available or get_power_state returns None.
    """
    agent = NeutralAgent(agent_id="test_neutral_italy", country="ITALY")

    # Scenario 1: get_power_state returns None
    mock_phase_state.get_power_state.return_value = None
    mock_phase_state.game.get_units.return_value = ["A ROM", "F NAP"]

    orders = await agent.decide_orders(mock_phase_state)

    mock_phase_state.get_power_state.assert_called_once_with("ITALY")
    mock_phase_state.game.get_units.assert_called_once_with("ITALY")
    
    assert len(orders) == 2
    assert Order("A ROM HLD") in orders
    assert Order("F NAP HLD") in orders
    expected_orders = [Order("A ROM HLD"), Order("F NAP HLD")]
    assert all(o in orders for o in expected_orders) and len(orders) == len(expected_orders)

    # Reset mocks for Scenario 2
    mock_phase_state.reset_mock()
    mock_phase_state.game.reset_mock() # Also reset the game mock

    # Scenario 2: get_power_state().units raises AttributeError (or object has no 'units')
    mock_power_state_no_units = MagicMock()
    del mock_power_state_no_units.units # Ensure it doesn't have 'units'
    
    # Alternative for stricter AttributeError simulation if needed:
    # mock_power_state_no_units = MagicMock(spec=['some_other_attribute']) 
    # or
    # type(mock_power_state_no_units).units = PropertyMock(side_effect=AttributeError)


    mock_phase_state.get_power_state.return_value = mock_power_state_no_units
    mock_phase_state.game.get_units.return_value = ["A VEN", "F TRI"]

    orders_scenario2 = await agent.decide_orders(mock_phase_state)

    mock_phase_state.get_power_state.assert_called_with("ITALY") # Called again
    mock_phase_state.game.get_units.assert_called_with("ITALY") # Called again
    
    assert len(orders_scenario2) == 2
    assert Order("A VEN HLD") in orders_scenario2
    assert Order("F TRI HLD") in orders_scenario2
    expected_orders_s2 = [Order("A VEN HLD"), Order("F TRI HLD")]
    assert all(o in orders_scenario2 for o in expected_orders_s2) and len(orders_scenario2) == len(expected_orders_s2)


async def test_neutral_agent_no_units(mock_phase_state: MagicMock):
    """
    Tests that NeutralAgent returns an empty list of orders when the power has no units.
    """
    agent = NeutralAgent(agent_id="test_neutral_germany", country="GERMANY")

    # Scenario 1: Power state has no units
    mock_power_state_no_units = MagicMock()
    mock_power_state_no_units.units = []
    mock_phase_state.get_power_state.return_value = mock_power_state_no_units
    mock_phase_state.game.get_units.return_value = [] # Fallback also returns no units

    orders = await agent.decide_orders(mock_phase_state)
    assert orders == []

    # Reset and test Scenario 2: get_power_state returns None, and game.get_units returns []
    mock_phase_state.reset_mock()
    mock_phase_state.game.reset_mock()
    
    mock_phase_state.get_power_state.return_value = None
    mock_phase_state.game.get_units.return_value = []

    orders_scenario2 = await agent.decide_orders(mock_phase_state)
    assert orders_scenario2 == []
    mock_phase_state.get_power_state.assert_called_once_with("GERMANY")
    mock_phase_state.game.get_units.assert_called_once_with("GERMANY")

async def test_neutral_agent_unit_object_to_string(mock_phase_state: MagicMock):
    """
    Tests that NeutralAgent correctly converts unit objects (if any) to strings.
    The HoldBehaviourMixin uses str(unit_name).
    """
    agent = NeutralAgent(agent_id="test_neutral_austria", country="AUSTRIA")
    
    # Mock unit objects that have a __str__ method
    class MockUnit:
        def __init__(self, name):
            self.name = name
        def __str__(self):
            return self.name

    mock_power_state_austria = MagicMock()
    mock_power_state_austria.units = [MockUnit("A VIE"), MockUnit("F BUD")] # Units are objects
    
    mock_phase_state.get_power_state.return_value = mock_power_state_austria
    mock_phase_state.game.get_units.return_value = [] # Fallback not used

    orders = await agent.decide_orders(mock_phase_state)

    assert len(orders) == 2
    assert Order("A VIE HLD") in orders
    assert Order("F BUD HLD") in orders
    expected_orders = [Order("A VIE HLD"), Order("F BUD HLD")]
    assert all(o in orders for o in expected_orders) and len(orders) == len(expected_orders)
