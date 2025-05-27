import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from types import SimpleNamespace

from ai_diplomacy.orchestrators.retreat import RetreatPhaseStrategy

# Using the same FakeGame and DummyOrchestrator definitions as in test_movement_strategy
# Ideally, these would be in a shared conftest.py or a common test utility file.
# For now, duplicating for simplicity until a broader test structure is decided.

class FakeGame:
    def __init__(self, phase, powers_names, retreat_conditions=None):
        self.phase = phase
        self.year = int(phase[1:5]) if phase and len(phase) >= 5 and phase[1:5].isdigit() else 1901
        self.powers = {}
        for name in powers_names:
            must_retreat_val = retreat_conditions.get(name, False) if retreat_conditions else False
            self.powers[name] = SimpleNamespace(
                is_eliminated=lambda: False,
                must_retreat=must_retreat_val,
                n_builds=0 
            )
    def get_current_phase(self):
        return self.phase
    def get_state(self):
        return {"centers": {}}

class DummyOrchestrator:
    def __init__(self, active_powers_list, game_config_mock, agent_manager_mock):
        self.active_powers = active_powers_list
        self.config = game_config_mock 
        self.agent_manager = agent_manager_mock
        self._get_orders_for_power = AsyncMock(return_value=["A BUD - STP"])
        self.get_valid_orders_func = None 

@pytest.mark.asyncio
async def test_retreat_generates_orders_for_retreating_power(mocker):
    strat = RetreatPhaseStrategy()
    powers = ["ENG", "FRA"]
    retreat_conditions = {"FRA": True, "ENG": False}
    fake_game = FakeGame("F1901R", powers, retreat_conditions)
    
    mock_game_config = MagicMock()
    mock_agent_manager = MagicMock()
    mock_agent_fra = MagicMock()
    mock_agent_eng = MagicMock()

    def get_agent_side_effect(power_name):
        if power_name == "FRA": return mock_agent_fra
        if power_name == "ENG": return mock_agent_eng
        return MagicMock()
    mock_agent_manager.get_agent.side_effect = get_agent_side_effect

    dummy_orchestrator = DummyOrchestrator(powers, mock_game_config, mock_agent_manager)
    dummy_orchestrator._get_orders_for_power = AsyncMock(return_value=["A PAR R A MAR"])
    
    mock_game_history = MagicMock()
    mock_game_history.add_orders = MagicMock()

    orders = await strat.get_orders(fake_game, dummy_orchestrator, mock_game_history)

    dummy_orchestrator._get_orders_for_power.assert_awaited_once_with(
        fake_game, "FRA", mock_agent_fra, mock_game_history
    )
    mock_game_history.add_orders.assert_called_once_with(fake_game.get_current_phase(), "FRA", ["A PAR R A MAR"])
    
    assert isinstance(orders, dict)
    assert set(orders.keys()) == set(powers)
    assert orders["FRA"] == ["A PAR R A MAR"]
    assert orders["ENG"] == []

@pytest.mark.asyncio
async def test_retreat_no_retreating_powers(mocker):
    strat = RetreatPhaseStrategy()
    powers = ["ENG", "GER"]
    retreat_conditions = {"ENG": False, "GER": False}
    fake_game = FakeGame("F1901R", powers, retreat_conditions)
    
    mock_game_config = MagicMock()
    mock_agent_manager = MagicMock()
    dummy_orchestrator = DummyOrchestrator(powers, mock_game_config, mock_agent_manager)
    mock_game_history = MagicMock()
    mock_game_history.add_orders = MagicMock()

    orders = await strat.get_orders(fake_game, dummy_orchestrator, mock_game_history)

    dummy_orchestrator._get_orders_for_power.assert_not_awaited()
    mock_game_history.add_orders.assert_not_called()
    assert orders == {}

@pytest.mark.asyncio
async def test_retreat_agent_fails_to_provide_orders(mocker):
    strat = RetreatPhaseStrategy()
    powers = ["ITA"]
    retreat_conditions = {"ITA": True}
    fake_game = FakeGame("F1901R", powers, retreat_conditions)
    
    mock_game_config = MagicMock()
    mock_agent_manager = MagicMock()
    mock_agent_ita = MagicMock()
    mock_agent_manager.get_agent.return_value = mock_agent_ita

    dummy_orchestrator = DummyOrchestrator(powers, mock_game_config, mock_agent_manager)
    dummy_orchestrator._get_orders_for_power = AsyncMock(side_effect=Exception("LLM error"))
    
    mock_game_history = MagicMock()
    mock_game_history.add_orders = MagicMock()

    orders = await strat.get_orders(fake_game, dummy_orchestrator, mock_game_history)

    dummy_orchestrator._get_orders_for_power.assert_awaited_once_with(
        fake_game, "ITA", mock_agent_ita, mock_game_history
    )
    mock_game_history.add_orders.assert_called_once_with(fake_game.get_current_phase(), "ITA", [])
    
    assert isinstance(orders, dict)
    assert orders["ITA"] == []
 