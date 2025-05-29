import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
# SimpleNamespace is no longer needed here as it's encapsulated in FakeGame in _diplomacy_fakes.py
# from types import SimpleNamespace 

from ai_diplomacy.orchestrators.build import BuildPhaseStrategy
from tests._diplomacy_fakes import FakeGame, DummyOrchestrator

@pytest.mark.asyncio
async def test_build_generates_orders_for_building_power():
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
async def test_build_generates_orders_for_disbanding_power():
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
async def test_build_no_building_or_disbanding_powers():
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
    assert orders == {"ENG": [], "GER": []}

@pytest.mark.asyncio
async def test_build_agent_fails_to_provide_orders():
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

@pytest.mark.asyncio
async def test_build_agent_not_found():
    strat = BuildPhaseStrategy()
    powers = ["AUS"]
    build_conditions = {"AUS": 1} # AUS has one build
    fake_game = FakeGame("W1901B", powers, build_conditions=build_conditions)
    
    mock_game_config = MagicMock()
    mock_agent_manager = MagicMock()
    # Simulate agent_manager.get_agent returning None for "AUS"
    mock_agent_manager.get_agent.return_value = None 

    dummy_orchestrator = DummyOrchestrator(powers, mock_game_config, mock_agent_manager)
    # _get_orders_for_power should not be called if agent is None
    dummy_orchestrator._get_orders_for_power = AsyncMock() 
    
    mock_game_history = MagicMock()
    mock_game_history.add_orders = MagicMock()

    # Expected log: logger.warning(f"No agent found for active power {power_name} during build order generation.")
    with pytest.logs(logger="ai_diplomacy.orchestrators.build", level="WARNING") as log_capture:
        orders = await strat.get_orders(fake_game, dummy_orchestrator, mock_game_history)

    dummy_orchestrator._get_orders_for_power.assert_not_awaited()
    # game_history.add_orders should still be called with empty orders for the power with no agent
    mock_game_history.add_orders.assert_called_once_with(fake_game.get_current_phase(), "AUS", [])
    
    assert isinstance(orders, dict)
    # Even if agent not found, the power should be in the final orders dict with an empty list
    assert orders == {"AUS": []}
    assert len(log_capture.records) == 1
    assert "No agent found for active power AUS" in log_capture.records[0].getMessage() 

@pytest.mark.asyncio
async def test_build_one_agent_fails_another_succeeds():
    strat = BuildPhaseStrategy()
    powers = ["FRA", "GER"]
    # Both have 1 build
    build_conditions = {"FRA": 1, "GER": 1}
    fake_game = FakeGame("W1901B", powers, build_conditions=build_conditions)
    
    mock_game_config = MagicMock()
    mock_agent_manager = MagicMock()
    mock_agent_fra = MagicMock(name="AgentFRA")
    mock_agent_ger = MagicMock(name="AgentGER")

    # _get_orders_for_power will be called for both FRA and GER.
    # Let FRA succeed and GER fail.
    async def get_orders_side_effect(game_obj, power_name_call, agent_obj, history_obj):
        if power_name_call == "FRA":
            return ["A PAR B"]
        elif power_name_call == "GER":
            raise ValueError("GER LLM simulated error")
        return []

    dummy_orchestrator = DummyOrchestrator(powers, mock_game_config, mock_agent_manager)
    dummy_orchestrator._get_orders_for_power = AsyncMock(side_effect=get_orders_side_effect)
    
    # Need to set up agent_manager.get_agent to return the correct agents
    def get_agent_side_effect_manager(power_name_manager):
        if power_name_manager == "FRA":
            return mock_agent_fra
        if power_name_manager == "GER":
            return mock_agent_ger
        return None
    mock_agent_manager.get_agent.side_effect = get_agent_side_effect_manager

    mock_game_history = MagicMock()
    mock_game_history.add_orders = MagicMock()

    with pytest.logs(logger="ai_diplomacy.orchestrators.build", level="ERROR") as log_capture:
        orders = await strat.get_orders(fake_game, dummy_orchestrator, mock_game_history)

    assert dummy_orchestrator._get_orders_for_power.await_count == 2
    dummy_orchestrator._get_orders_for_power.assert_any_await(fake_game, "FRA", mock_agent_fra, mock_game_history)
    dummy_orchestrator._get_orders_for_power.assert_any_await(fake_game, "GER", mock_agent_ger, mock_game_history)

    # Check game_history.add_orders calls
    # FRA should have its orders, GER should have empty orders due to failure
    expected_history_calls = [
        pytest.call(fake_game.get_current_phase(), "FRA", ["A PAR B"]),
        pytest.call(fake_game.get_current_phase(), "GER", [])
    ]
    # Order of calls to add_orders might vary due to asyncio.gather, so check presence
    mock_game_history.add_orders.assert_has_calls(expected_history_calls, any_order=True)
    assert mock_game_history.add_orders.call_count == 2
    
    assert isinstance(orders, dict)
    assert orders["FRA"] == ["A PAR B"]
    assert orders["GER"] == [] # GER failed, so empty orders

    assert len(log_capture.records) == 1
    assert "Error getting build orders for GER: GER LLM simulated error" in log_capture.records[0].getMessage() 