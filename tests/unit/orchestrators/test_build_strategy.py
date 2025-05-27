import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from types import SimpleNamespace

from ai_diplomacy.orchestrators.build import BuildPhaseStrategy

# Using the same FakeGame and DummyOrchestrator definitions as in test_movement_strategy
# Ideally, these would be in a shared conftest.py or a common test utility file.
# For now, duplicating for simplicity until a broader test structure is decided.

class FakeGame:
    def __init__(self, phase, powers_names, build_conditions=None):
        self.phase = phase
        self.year = int(phase[1:5]) if phase and len(phase) >= 5 and phase[1:5].isdigit() else 1901
        self.powers = {}
        for name in powers_names:
            n_builds_val = build_conditions.get(name, 0) if build_conditions else 0
            self.powers[name] = SimpleNamespace(
                is_eliminated=lambda: False,
                must_retreat=False, # Not relevant for build
                n_builds=n_builds_val
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
        self._get_orders_for_power = AsyncMock(return_value=["A PAR B"])
        self.get_valid_orders_func = None 

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