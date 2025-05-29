import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, call
# SimpleNamespace is no longer needed here as it's encapsulated in FakeGame in _diplomacy_fakes.py
# from types import SimpleNamespace 

from ai_diplomacy.orchestrators.retreat import RetreatPhaseStrategy
# FakeGame and DummyOrchestrator are now injected via fixtures from conftest
# from tests._diplomacy_fakes import FakeGame, DummyOrchestrator 

@pytest.mark.unit
@pytest.mark.asyncio
async def test_retreat_generates_orders_for_retreating_power(fake_game_factory, default_dummy_orchestrator):
    strat = RetreatPhaseStrategy()
    powers = ["ENG", "FRA"]
    retreat_conditions_map = {"FRA": True, "ENG": False}
    fake_game = fake_game_factory(phase="F1901R", powers_names=powers, retreat_conditions=retreat_conditions_map)
    
    dummy_orchestrator = default_dummy_orchestrator
    dummy_orchestrator.active_powers = powers
    
    mock_agent_fra = MagicMock(name="AgentFRA")
    mock_agent_eng = MagicMock(name="AgentENG")

    def get_agent_side_effect(power_name):
        if power_name == "FRA": return mock_agent_fra
        if power_name == "ENG": return mock_agent_eng
        return MagicMock()
    dummy_orchestrator.agent_manager.get_agent.side_effect = get_agent_side_effect
    dummy_orchestrator._get_orders_for_power = AsyncMock(return_value=["A PAR R A MAR"])
    
    mock_game_history = MagicMock()
    mock_game_history.add_orders = MagicMock()

    orders = await strat.get_orders(fake_game, dummy_orchestrator, mock_game_history)

    # Assert that _get_orders_for_power was called for FRA (the retreating power)
    dummy_orchestrator._get_orders_for_power.assert_awaited_once_with(
        fake_game, "FRA", mock_agent_fra, mock_game_history
    )
    # Assert that game_history.add_orders was called for FRA with its orders
    # and for ENG with empty orders (as it was not retreating)
    expected_history_calls = [
        call(fake_game.get_current_phase(), "FRA", ["A PAR R A MAR"]),
        call(fake_game.get_current_phase(), "ENG", [])
    ]
    mock_game_history.add_orders.assert_has_calls(expected_history_calls, any_order=True)
    assert mock_game_history.add_orders.call_count == 2
    
    assert isinstance(orders, dict)
    assert set(orders.keys()) == set(powers)
    assert orders["FRA"] == ["A PAR R A MAR"]
    assert orders["ENG"] == []

@pytest.mark.unit
@pytest.mark.asyncio
async def test_retreat_no_retreating_powers(fake_game_factory, default_dummy_orchestrator):
    strat = RetreatPhaseStrategy()
    powers = ["ENG", "GER"]
    retreat_conditions_map = {"ENG": False, "GER": False}
    fake_game = fake_game_factory(phase="F1901R", powers_names=powers, retreat_conditions=retreat_conditions_map)
    
    dummy_orchestrator = default_dummy_orchestrator
    dummy_orchestrator.active_powers = powers
    # _get_orders_for_power should not be called as no power is retreating
    
    mock_game_history = MagicMock()
    mock_game_history.add_orders = MagicMock()

    orders = await strat.get_orders(fake_game, dummy_orchestrator, mock_game_history)

    dummy_orchestrator._get_orders_for_power.assert_not_awaited()
    # game_history.add_orders should be called for each power with empty orders
    expected_history_calls = [
        call(fake_game.get_current_phase(), "ENG", []),
        call(fake_game.get_current_phase(), "GER", [])
    ]
    mock_game_history.add_orders.assert_has_calls(expected_history_calls, any_order=True)
    assert mock_game_history.add_orders.call_count == 2
    assert orders == {"ENG": [], "GER": []} # Strategy now ensures all powers are keys

@pytest.mark.unit
@pytest.mark.asyncio
async def test_retreat_agent_fails_to_provide_orders(fake_game_factory, default_dummy_orchestrator):
    strat = RetreatPhaseStrategy()
    powers = ["ITA"]
    retreat_conditions_map = {"ITA": True}
    fake_game = fake_game_factory(phase="F1901R", powers_names=powers, retreat_conditions=retreat_conditions_map)
    
    dummy_orchestrator = default_dummy_orchestrator
    dummy_orchestrator.active_powers = powers
    
    mock_agent_ita = MagicMock(name="AgentITA")
    dummy_orchestrator.agent_manager.get_agent.return_value = mock_agent_ita
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

@pytest.mark.unit
@pytest.mark.asyncio
async def test_retreat_agent_not_found(fake_game_factory, default_dummy_orchestrator):
    strat = RetreatPhaseStrategy()
    powers = ["AUS"]
    retreat_conditions_map = {"AUS": True}
    fake_game = fake_game_factory(phase="F1901R", powers_names=powers, retreat_conditions=retreat_conditions_map)
    
    dummy_orchestrator = default_dummy_orchestrator
    dummy_orchestrator.active_powers = powers
    dummy_orchestrator.agent_manager.get_agent.return_value = None # Agent not found
    # _get_orders_for_power should not be called
    
    mock_game_history = MagicMock()
    mock_game_history.add_orders = MagicMock()

    with pytest.logs(logger="ai_diplomacy.orchestrators.retreat", level="WARNING") as log_capture:
        orders = await strat.get_orders(fake_game, dummy_orchestrator, mock_game_history)

    dummy_orchestrator._get_orders_for_power.assert_not_awaited()
    # game_history.add_orders should still be called with empty orders for AUS
    mock_game_history.add_orders.assert_called_once_with(fake_game.get_current_phase(), "AUS", [])
    
    assert isinstance(orders, dict)
    # Even if agent not found, the power should be in the final orders dict with an empty list
    assert orders == {"AUS": []}
    assert len(log_capture.records) == 1
    assert "No agent found for active power AUS during retreat order generation." in log_capture.records[0].getMessage()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_retreat_one_agent_fails_another_succeeds(fake_game_factory, default_dummy_orchestrator):
    strat = RetreatPhaseStrategy()
    powers = ["FRA", "GER"]
    retreat_conditions_map = {"FRA": True, "GER": True}
    fake_game = fake_game_factory(phase="F1901R", powers_names=powers, retreat_conditions=retreat_conditions_map)
    
    dummy_orchestrator = default_dummy_orchestrator
    dummy_orchestrator.active_powers = powers

    mock_agent_fra = MagicMock(name="AgentFRA")
    mock_agent_ger = MagicMock(name="AgentGER")

    def get_agent_side_effect(power_name):
        if power_name == "FRA": return mock_agent_fra
        if power_name == "GER": return mock_agent_ger
        return None
    dummy_orchestrator.agent_manager.get_agent.side_effect = get_agent_side_effect

    async def get_orders_side_effect(game_obj, power_name_call, agent_obj, history_obj):
        if power_name_call == "FRA":
            return ["A PAR R MAR"]
        elif power_name_call == "GER":
            if agent_obj is not mock_agent_ger: # Ensure correct agent is passed
                 pytest.fail("Incorrect agent object passed to _get_orders_for_power for GER")
            raise ConnectionError("GER LLM simulated connection error")
        return []
    dummy_orchestrator._get_orders_for_power = AsyncMock(side_effect=get_orders_side_effect)
    
    mock_game_history = MagicMock()
    mock_game_history.add_orders = MagicMock()

    with pytest.logs(logger="ai_diplomacy.orchestrators.retreat", level="ERROR") as log_capture:
        orders = await strat.get_orders(fake_game, dummy_orchestrator, mock_game_history)

    assert dummy_orchestrator._get_orders_for_power.await_count == 2
    dummy_orchestrator._get_orders_for_power.assert_any_await(fake_game, "FRA", mock_agent_fra, mock_game_history)
    dummy_orchestrator._get_orders_for_power.assert_any_await(fake_game, "GER", mock_agent_ger, mock_game_history)
    
    expected_history_calls = [
        call(fake_game.get_current_phase(), "FRA", ["A PAR R MAR"]),
        call(fake_game.get_current_phase(), "GER", [])
    ]
    mock_game_history.add_orders.assert_has_calls(expected_history_calls, any_order=True)
    assert mock_game_history.add_orders.call_count == 2
    
    assert isinstance(orders, dict)
    assert orders["FRA"] == ["A PAR R MAR"]
    assert orders["GER"] == []

    assert len(log_capture.records) == 1
    assert "Error getting retreat orders for GER: GER LLM simulated connection error" in log_capture.records[0].getMessage()
 