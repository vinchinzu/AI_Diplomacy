import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
# SimpleNamespace is no longer needed here as it's encapsulated in FakeGame in _diplomacy_fakes.py
# from types import SimpleNamespace 

from ai_diplomacy.orchestrators.build import BuildPhaseStrategy
from tests._diplomacy_fakes import FakeGame, DummyOrchestrator

@pytest.mark.asyncio
async def test_build_generates_orders_for_building_power(mocker):
    strat = BuildPhaseStrategy()
    powers = ["ENG", "FRA"]
    # FRA has 1 build, ENG has 0
    build_conditions = {"FRA": 1, "ENG": 0}
    fake_game = FakeGame("W1901B", powers, build_conditions)
    
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
    dummy_orchestrator._get_orders_for_power = AsyncMock(return_value=["A PAR B"])
    
    mock_game_history = MagicMock()
    mock_game_history.add_orders = MagicMock()

    orders = await strat.get_orders(fake_game, dummy_orchestrator, mock_game_history)

    dummy_orchestrator._get_orders_for_power.assert_awaited_once_with(
        fake_game, "FRA", mock_agent_fra, mock_game_history
    )
    mock_game_history.add_orders.assert_called_once_with(fake_game.get_current_phase(), "FRA", ["A PAR B"])
    
    assert isinstance(orders, dict)
    assert set(orders.keys()) == set(powers)
    assert orders["FRA"] == ["A PAR B"]
    assert orders["ENG"] == []

@pytest.mark.asyncio
async def test_build_generates_orders_for_disbanding_power(mocker):
    strat = BuildPhaseStrategy()
    powers = ["GER"]
    # GER has -1 builds (must disband)
    build_conditions = {"GER": -1}
    fake_game = FakeGame("W1901B", powers, build_conditions)
    
    mock_game_config = MagicMock()
    mock_agent_manager = MagicMock()
    mock_agent_ger = MagicMock()
    mock_agent_manager.get_agent.return_value = mock_agent_ger

    dummy_orchestrator = DummyOrchestrator(powers, mock_game_config, mock_agent_manager)
    dummy_orchestrator._get_orders_for_power = AsyncMock(return_value=["A BER D"])
    
    mock_game_history = MagicMock()
    mock_game_history.add_orders = MagicMock()

    orders = await strat.get_orders(fake_game, dummy_orchestrator, mock_game_history)

    dummy_orchestrator._get_orders_for_power.assert_awaited_once_with(
        fake_game, "GER", mock_agent_ger, mock_game_history
    )
    mock_game_history.add_orders.assert_called_once_with(fake_game.get_current_phase(), "GER", ["A BER D"])
    
    assert isinstance(orders, dict)
    assert orders["GER"] == ["A BER D"]

@pytest.mark.asyncio
async def test_build_no_building_or_disbanding_powers(mocker):
    strat = BuildPhaseStrategy()
    powers = ["ENG", "GER"]
    build_conditions = {"ENG": 0, "GER": 0} # No builds or disbands
    fake_game = FakeGame("W1901B", powers, build_conditions)
    
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
async def test_build_agent_fails_to_provide_orders(mocker):
    strat = BuildPhaseStrategy()
    powers = ["ITA"]
    build_conditions = {"ITA": 1} # ITA has one build
    fake_game = FakeGame("W1901B", powers, build_conditions)
    
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