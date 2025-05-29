from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from ai_diplomacy.services.llm_coordinator import LLMCoordinator # Added import

class FakeGame:
    def __init__(self, phase, powers_names, build_conditions=None, retreat_conditions=None):
        self.phase = phase
        self.year = int(phase[1:5]) if phase and len(phase) >= 5 and phase[1:5].isdigit() else 1901
        self.powers = {}
        for name in powers_names:
            n_builds_val = build_conditions.get(name, 0) if build_conditions else 0
            must_retreat_val = retreat_conditions.get(name, False) if retreat_conditions else False
            self.powers[name] = SimpleNamespace(
                is_eliminated=lambda: False,
                must_retreat=must_retreat_val,
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

class FakeDiplomacyAgent:
    def __init__(self, power_name, model_id="mock_model"):
        self.power_name = power_name
        self.model_id = model_id
        self.goals = [f"Take over the world ({power_name})", "Make friends"]
        self.relationships = {"OTHER_POWER": "Neutral"}
        self.private_journal = [
            f"Journal Entry 1 for {power_name}",
            f"Journal Entry 2 for {power_name}",
        ]
        self.private_diary = [f"[S1901M] Diary entry for {power_name}"]

    def get_agent_info(
        self,
    ):  # Added to match BaseAgent interface if needed by processor
        return {
            "agent_id": f"mock_agent_{self.power_name}",
            "country": self.power_name,
            "type": self.__class__.__name__,
            "model_id": self.model_id,
        }


class FakeGameHistory: # Renamed from MockGameHistoryResults
    def __init__(self):
        self.phases = [  # Simplified phase objects for testing to_dict fallback
            {"name": "SPRING 1901M", "orders_by_power": {"FRANCE": ["A PAR H"]}},
            {
                "name": "AUTUMN 1901M",
                "orders_by_power": {"FRANCE": ["A PAR - BUR"]},
            },
        ]

    def to_dict(self):  # Added to satisfy GameResultsProcessor's expectation
        return {"phases": self.phases}


class FakeDiplomacyGame:  # Renamed from MockDiplomacyGame
    def __init__(self):
        self.is_game_done = True  # Mark as done for saving state
        self._current_phase = "WINTER 1905"  # Example
        self._centers = {  # Example SC map
            "FRANCE": ["PAR", "MAR", "BRE", "SPA", "POR", "BEL", "HOL"],
            "ENGLAND": ["LON", "LVP", "EDI", "NWY", "SWE"],
            "GERMANY": ["BER", "MUN", "KIE", "DEN", "RUH", "WAR", "MOS"],
        }
        self._winners = ["GERMANY"]  # Example winner

    def get_current_phase(self):
        return self._current_phase

    def get_state(self):  # Corresponds to game.map.centers in some diplomacy versions
        return {
            "centers": self._centers
        }  # Or however the real Game object structures this

    def get_winners(self):
        return self._winners

class FakeLLMCoordinator(LLMCoordinator): # Renamed from DummyCoordinator
    async def request(
        self,
        model_id,
        prompt_text,
        system_prompt_text,
        game_id="test_game",
        agent_name="test_agent",
        phase_str="test_phase",
        request_identifier="request",
        llm_caller_override=None, # Added to match signature
    ):
        # Simulate a successful LLM response
        return "This is a dummy LLM response."
