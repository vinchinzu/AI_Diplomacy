import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
# SimpleNamespace is no longer needed here as it's encapsulated in FakeGame in _diplomacy_fakes.py
# from types import SimpleNamespace 

from ai_diplomacy.orchestrators.retreat import RetreatPhaseStrategy
from tests._diplomacy_fakes import FakeGame, DummyOrchestrator

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
 