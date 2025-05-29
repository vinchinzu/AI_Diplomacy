import pytest
import asyncio
import logging # Added import
from unittest.mock import MagicMock, AsyncMock, patch, call
# SimpleNamespace is no longer needed here as it's encapsulated in FakeGame in _diplomacy_fakes.py
# from types import SimpleNamespace 

from ai_diplomacy.orchestrators.movement import MovementPhaseStrategy
from ai_diplomacy.game_history import GameHistory # Added import
# FakeGame and DummyOrchestrator are now injected via fixtures from conftest
# from tests._diplomacy_fakes import FakeGame, DummyOrchestrator 

@pytest.mark.unit
@pytest.mark.asyncio
async def test_movement_generates_orders(fake_game_factory, default_dummy_orchestrator):
    strat = MovementPhaseStrategy()
    powers = ["ENG", "FRA"]
    fake_game = fake_game_factory(phase="S1901M", powers_names=powers)
    
    dummy_orchestrator = default_dummy_orchestrator
    dummy_orchestrator.active_powers = powers
    dummy_orchestrator.config.num_negotiation_rounds = 1 # For perform_negotiation_rounds

    # Simplistic agent mock, can be customized if needed per power
    mock_agent = MagicMock(name="GenericAgent")
    dummy_orchestrator.agent_manager.get_agent.return_value = mock_agent
    dummy_orchestrator._get_orders_for_power = AsyncMock(return_value=["WAIVE"])

    mock_game_history = MagicMock(spec=GameHistory, autospec=True)
    # Removed: mock_game_history.add_orders = MagicMock()
    # Removed: mock_game_history.add_phase = MagicMock()
    # Removed: mock_game_history.add_message = MagicMock()

    with patch(
        "ai_diplomacy.orchestrators.movement.perform_negotiation_rounds", 
        new_callable=AsyncMock, 
        return_value=None
    ) as mocked_perform_negotiation:
        # _get_orders_for_power is a method on the orchestrator, already mocked in DummyOrchestrator
        # gather_possible_orders is used by orchestrator._get_orders_for_power for non-LLM agents
        # For this test, _get_orders_for_power on DummyOrchestrator is an AsyncMock, so gather_possible_orders won't be hit
        # unless we were testing the non-LLM path of _get_orders_for_power itself.
        # mocker.patch("ai_diplomacy.utils.gather_possible_orders", return_value={"A LON": ["A LON H"]})

        orders = await strat.get_orders(fake_game, dummy_orchestrator, mock_game_history)

        # Assertions
        mocked_perform_negotiation.assert_awaited_once_with(
            fake_game, mock_game_history, dummy_orchestrator.agent_manager, 
            dummy_orchestrator.active_powers, dummy_orchestrator.config
        )
        
        # Check that _get_orders_for_power was called for each active power
        assert dummy_orchestrator._get_orders_for_power.await_count == len(powers)
        for power_name in powers:
            # Check if _get_orders_for_power was called with this power_name
            # This is a bit tricky as it's called multiple times. 
            # We can check call_args_list
            power_found_in_calls = False
            for call in dummy_orchestrator._get_orders_for_power.call_args_list:
                args, _ = call
                if args[1] == power_name: # game, power_name, agent, game_history
                    power_found_in_calls = True
                    break
            assert power_found_in_calls, f"_get_orders_for_power not called for {power_name}"

        # Check that game_history.add_orders was called for each power
        assert mock_game_history.add_orders.call_count == len(powers)
        
        expected_calls = [
            call(fake_game.get_current_phase(), "ENG", ["WAIVE"]), # unittest.mock.call
            call(fake_game.get_current_phase(), "FRA", ["WAIVE"])  # unittest.mock.call
        ]
        # Check that all expected calls are present in the actual calls.
        # This is more robust than assert_any_call in a loop if call order might vary or for exactness.
        actual_calls = mock_game_history.add_orders.call_args_list
        for expected_call in expected_calls:
            assert expected_call in actual_calls, f"{expected_call} not found in {actual_calls}"

        # Validate the structure of returned orders
        assert isinstance(orders, dict)
        assert set(orders.keys()) == set(powers)
        for power_name in powers:
            assert orders[power_name] == ["WAIVE"] # Based on DummyOrchestrator's _get_orders_for_power mock

@pytest.mark.unit
@pytest.mark.asyncio
async def test_movement_agent_not_found_and_agent_error(fake_game_factory, default_dummy_orchestrator, caplog): # Added caplog
    strat = MovementPhaseStrategy()
    powers = ["ENG", "FRA", "GER"] # ENG: agent fails, FRA: no agent, GER: success
    fake_game = fake_game_factory(phase="S1901M", powers_names=powers)
    
    dummy_orchestrator = default_dummy_orchestrator
    dummy_orchestrator.active_powers = powers
    dummy_orchestrator.config.num_negotiation_rounds = 0 # No negotiation

    mock_agent_eng = MagicMock(name="AgentENG")
    mock_agent_ger = MagicMock(name="AgentGER")

    def get_agent_side_effect(power_name):
        if power_name == "ENG": return mock_agent_eng
        if power_name == "GER": return mock_agent_ger
        if power_name == "FRA": return None
        return MagicMock()
    dummy_orchestrator.agent_manager.get_agent.side_effect = get_agent_side_effect

    async def get_orders_side_effect_orchestrator(game_obj, power_name_call, agent_obj, history_obj):
        if power_name_call == "ENG":
            raise AttributeError("ENG LLM simulated attribute error")
        elif power_name_call == "GER":
            return ["A BER H"]
        return ["WAIVE"] 
    dummy_orchestrator._get_orders_for_power = AsyncMock(side_effect=get_orders_side_effect_orchestrator)
    
    mock_game_history = MagicMock()
    mock_game_history.add_orders = MagicMock()
    mock_game_history.add_phase = MagicMock() # Still needed by perform_negotiation_rounds even if not awaited
    mock_game_history.add_message = MagicMock() # Still needed by perform_negotiation_rounds

    with patch(
        "ai_diplomacy.orchestrators.movement.perform_negotiation_rounds", 
        new_callable=AsyncMock, 
        return_value=None
    ) as mocked_perform_negotiation:
        caplog.set_level(logging.WARNING, logger="ai_diplomacy.orchestrators.movement") # Set to capture WARNING and above
        orders = await strat.get_orders(fake_game, dummy_orchestrator, mock_game_history)

    mocked_perform_negotiation.assert_not_awaited()
        
    # _get_orders_for_power should be called for ENG and GER, but not FRA (no agent)
    assert dummy_orchestrator._get_orders_for_power.await_count == 2
    dummy_orchestrator._get_orders_for_power.assert_any_await(fake_game, "ENG", mock_agent_eng, mock_game_history)
    dummy_orchestrator._get_orders_for_power.assert_any_await(fake_game, "GER", mock_agent_ger, mock_game_history)

    # Check game_history.add_orders calls
    expected_history_calls = [
        call(fake_game.get_current_phase(), "ENG", []), # ENG failed
        call(fake_game.get_current_phase(), "FRA", []), # FRA no agent
        call(fake_game.get_current_phase(), "GER", ["A BER H"]) # GER succeeded
    ]
    mock_game_history.add_orders.assert_has_calls(expected_history_calls, any_order=True)
    assert mock_game_history.add_orders.call_count == 3

    assert isinstance(orders, dict)
    assert orders["ENG"] == []
    assert orders["FRA"] == []
    assert orders["GER"] == ["A BER H"]

    # Check logs
    warn_records = [r for r in caplog.records if r.levelname == "WARNING" and r.name == "ai_diplomacy.orchestrators.movement"]
    error_records = [r for r in caplog.records if r.levelname == "ERROR" and r.name == "ai_diplomacy.orchestrators.movement"]
    
    assert len(warn_records) == 1
    assert "No agent found for active power FRA during movement order generation" in warn_records[0].message
    assert len(error_records) == 1
    assert "Error getting movement orders for ENG: ENG LLM simulated attribute error" in error_records[0].message

