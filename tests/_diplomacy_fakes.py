from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

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
