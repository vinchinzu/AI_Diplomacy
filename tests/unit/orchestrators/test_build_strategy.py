import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, call
# SimpleNamespace is no longer needed here as it's encapsulated in FakeGame in _diplomacy_fakes.py
# from types import SimpleNamespace 

from ai_diplomacy.orchestrators.build import BuildPhaseStrategy
# FakeGame and DummyOrchestrator are now injected via fixtures from conftest
# from tests._diplomacy_fakes import FakeGame, DummyOrchestrator 

@pytest.mark.unit
@pytest.mark.asyncio
async def test_build_generates_orders_for_building_power(fake_game_factory, default_dummy_orchestrator):
    strat = BuildPhaseStrategy()
    powers = ["ENG", "FRA"]
    build_conditions = {"FRA": 1, "ENG": 0}
    fake_game = fake_game_factory(phase="W1901B", powers_names=powers, build_conditions=build_conditions)
    
    dummy_orchestrator = default_dummy_orchestrator
    dummy_orchestrator.active_powers = powers
    
    mock_agent_fra = MagicMock(name="AgentFRA")
    mock_agent_eng = MagicMock(name="AgentENG")

    def get_agent_side_effect(power_name):
        if power_name == "FRA": return mock_agent_fra
        if power_name == "ENG": return mock_agent_eng
        return MagicMock()
    dummy_orchestrator.agent_manager.get_agent.side_effect = get_agent_side_effect
    dummy_orchestrator._get_orders_for_power = AsyncMock(return_value=["A PAR B"])
    
    mock_game_history = MagicMock()
    mock_game_history.add_orders = MagicMock()

    orders = await strat.get_orders(fake_game, dummy_orchestrator, mock_game_history)

    # Assert that _get_orders_for_power was called for FRA (the building power)
    # It should not be called for ENG (0 builds)
    dummy_orchestrator._get_orders_for_power.assert_awaited_once_with(
        fake_game, "FRA", mock_agent_fra, mock_game_history
    )
    # Assert that game_history.add_orders was called for FRA with its orders
    # and for ENG with empty orders (as it had no builds/disbands)
    expected_history_calls = [
        call(fake_game.get_current_phase(), "FRA", ["A PAR B"]),
        call(fake_game.get_current_phase(), "ENG", [])
    ]
    mock_game_history.add_orders.assert_has_calls(expected_history_calls, any_order=True)
    assert mock_game_history.add_orders.call_count == 2
    
    assert isinstance(orders, dict)
    assert set(orders.keys()) == set(powers)
    assert orders["FRA"] == ["A PAR B"]
    assert orders["ENG"] == []

@pytest.mark.unit
@pytest.mark.asyncio
async def test_build_generates_orders_for_disbanding_power(fake_game_factory, default_dummy_orchestrator):
    strat = BuildPhaseStrategy()
    powers = ["GER"]
    build_conditions = {"GER": -1} # GER must disband 1
    fake_game = fake_game_factory(phase="W1901B", powers_names=powers, build_conditions=build_conditions)
    
    dummy_orchestrator = default_dummy_orchestrator
    dummy_orchestrator.active_powers = powers
    
    mock_agent_ger = MagicMock(name="AgentGER")
    dummy_orchestrator.agent_manager.get_agent.return_value = mock_agent_ger
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

@pytest.mark.unit
@pytest.mark.asyncio
async def test_build_no_building_or_disbanding_powers(fake_game_factory, default_dummy_orchestrator):
    strat = BuildPhaseStrategy()
    powers = ["ENG", "GER"]
    build_conditions = {"ENG": 0, "GER": 0}
    fake_game = fake_game_factory(phase="W1901B", powers_names=powers, build_conditions=build_conditions)
    
    dummy_orchestrator = default_dummy_orchestrator
    dummy_orchestrator.active_powers = powers
    # _get_orders_for_power should not be called as no power has builds/disbands
    # The default AsyncMock(return_value=["WAIVE"]) on default_dummy_orchestrator is fine
    
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
    assert orders == {"ENG": [], "GER": []}

@pytest.mark.unit
@pytest.mark.asyncio
async def test_build_agent_fails_to_provide_orders(fake_game_factory, default_dummy_orchestrator):
    strat = BuildPhaseStrategy()
    powers = ["ITA"]
    build_conditions = {"ITA": 1}
    fake_game = fake_game_factory(phase="W1901B", powers_names=powers, build_conditions=build_conditions)
    
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
async def test_build_agent_not_found(fake_game_factory, default_dummy_orchestrator):
    strat = BuildPhaseStrategy()
    powers = ["AUS"]
    build_conditions = {"AUS": 1}
    fake_game = fake_game_factory(phase="W1901B", powers_names=powers, build_conditions=build_conditions)
    
    dummy_orchestrator = default_dummy_orchestrator
    dummy_orchestrator.active_powers = powers
    dummy_orchestrator.agent_manager.get_agent.return_value = None # Agent not found
    # _get_orders_for_power should not be called, default mock on orchestrator is fine.
    
    mock_game_history = MagicMock()
    mock_game_history.add_orders = MagicMock()

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

@pytest.mark.unit
@pytest.mark.asyncio
async def test_build_one_agent_fails_another_succeeds(fake_game_factory, default_dummy_orchestrator):
    strat = BuildPhaseStrategy()
    powers = ["FRA", "GER"]
    build_conditions = {"FRA": 1, "GER": 1}
    fake_game = fake_game_factory(phase="W1901B", powers_names=powers, build_conditions=build_conditions)

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
            return ["A PAR B"]
        elif power_name_call == "GER":
            # Ensure the agent object passed is the correct one for GER before raising error
            if agent_obj is not mock_agent_ger:
                 pytest.fail("Incorrect agent object passed to _get_orders_for_power for GER")
            raise ValueError("GER LLM simulated error")
        return [] # Should not be reached
    dummy_orchestrator._get_orders_for_power = AsyncMock(side_effect=get_orders_side_effect)
    
    mock_game_history = MagicMock()
    mock_game_history.add_orders = MagicMock()

    with pytest.logs(logger="ai_diplomacy.orchestrators.build", level="ERROR") as log_capture:
        orders = await strat.get_orders(fake_game, dummy_orchestrator, mock_game_history)

    assert dummy_orchestrator._get_orders_for_power.await_count == 2
    # Check calls with specific agent objects
    dummy_orchestrator._get_orders_for_power.assert_any_await(fake_game, "FRA", mock_agent_fra, mock_game_history)
    dummy_orchestrator._get_orders_for_power.assert_any_await(fake_game, "GER", mock_agent_ger, mock_game_history)
    
    expected_history_calls = [
        call(fake_game.get_current_phase(), "FRA", ["A PAR B"]),
        call(fake_game.get_current_phase(), "GER", [])
    ]
    mock_game_history.add_orders.assert_has_calls(expected_history_calls, any_order=True)
    assert mock_game_history.add_orders.call_count == 2
    
    assert isinstance(orders, dict)
    assert orders["FRA"] == ["A PAR B"]
    assert orders["GER"] == []

    assert len(log_capture.records) == 1
    assert "Error getting build orders for GER: GER LLM simulated error" in log_capture.records[0].getMessage()