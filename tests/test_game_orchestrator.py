import unittest
from unittest.mock import (
    Mock,
    AsyncMock,
    patch,
)  # Added call for checking multiple calls

from ai_diplomacy.game_orchestrator import GamePhaseOrchestrator, PhaseType
from ai_diplomacy.services.config import (
    GameConfig,
)  # Corrected: GameConfig is directly in services.config
from ai_diplomacy.agent_manager import AgentManager
from ai_diplomacy.agents.base import Message, Order  # Added Order
from ai_diplomacy.agents.llm_agent import LLMAgent
from ai_diplomacy.core.state import PhaseState
from ai_diplomacy.game_history import GameHistory
from diplomacy import Game  # For type hinting Game


class TestGamePhaseOrchestrator(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_game_config = Mock(spec=GameConfig)
        self.mock_game_config.powers_and_models = {"ENGLAND": "test_model"}
        self.mock_game_config.num_negotiation_rounds = 1
        self.mock_game_config.perform_planning_phase = False  # As per example
        self.mock_game_config.llm_log_path = "/tmp/mock_log.txt"
        self.mock_game_config.game_id = (
            "test_orchestrator_game"  # For PhaseState.from_game if it uses it
        )

        self.mock_agent_manager = Mock(spec=AgentManager)

        self.mock_llm_agent = AsyncMock(spec=LLMAgent)
        self.mock_llm_agent.country = "ENGLAND"
        self.mock_llm_agent.agent_id = "england_agent"
        self.mock_llm_agent.negotiate = AsyncMock(
            return_value=[Message("FRANCE", "Hello from ENGLAND", "private")]
        )
        # decide_orders should return List[Order] objects based on LLMAgent's implementation
        self.mock_llm_agent.decide_orders = AsyncMock(return_value=[Order("A LON H")])
        # Mock other methods that might be called by the orchestrator on the agent
        self.mock_llm_agent.generate_order_diary_entry = (
            AsyncMock()
        )  # Called in _execute_movement_phase_actions
        self.mock_llm_agent.analyze_phase_and_update_state = (
            AsyncMock()
        )  # Called in _process_phase_results_and_updates
        self.mock_llm_agent.consolidate_year_diary_entries = (
            AsyncMock()
        )  # Called in _process_phase_results_and_updates

        self.mock_agent_manager.get_agent = Mock(return_value=self.mock_llm_agent)

        self.mock_game = Mock(
            spec=Game
        )  # Use Mock not AsyncMock, diplomacy.Game methods are generally synchronous
        self.mock_game.get_current_phase = Mock(return_value="S1901M")
        self.mock_game.is_game_done = False
        self.mock_game.powers = {
            "ENGLAND": Mock(),
            "FRANCE": Mock(),
        }  # Mock powers attribute
        self.mock_game.powers["ENGLAND"].is_eliminated = Mock(return_value=False)
        self.mock_game.powers["FRANCE"].is_eliminated = Mock(return_value=False)

        # For PhaseState.from_game(game) - it will inspect the game object
        # We need to ensure game.get_state(), game.get_all_possible_orders() etc. are valid if from_game uses them.
        # For simplicity, let's mock what PhaseState.from_game might need or patch PhaseState.from_game itself.
        self.mock_phase_state_instance = AsyncMock(spec=PhaseState)
        self.mock_phase_state_instance.phase_name = "S1901M"  # Match game phase

        # It's cleaner to patch PhaseState.from_game
        self.patcher_from_game = patch(
            "ai_diplomacy.core.state.PhaseState.from_game",
            return_value=self.mock_phase_state_instance,
        )
        self.MockPhaseState_from_game = self.patcher_from_game.start()
        self.addCleanup(self.patcher_from_game.stop)

        self.mock_game_history = AsyncMock(
            spec=GameHistory
        )  # Use AsyncMock if its methods are async

        self.mock_get_valid_orders_func = AsyncMock(
            return_value=[Order("F LVP H")]
        )  # Ensure it returns Order objects if that's the type

        self.orchestrator = GamePhaseOrchestrator(
            game_config=self.mock_game_config,
            agent_manager=self.mock_agent_manager,
            get_valid_orders_func=self.mock_get_valid_orders_func,
        )
        # active_powers is usually determined in run_game_loop, set it manually for unit tests
        self.orchestrator.active_powers = ["ENGLAND"]

    async def test_perform_negotiation_llm_agent(self):
        self.mock_game.get_current_phase.return_value = "S1901M"  # Ensure phase is set

        await self.orchestrator._perform_negotiation_rounds(
            self.mock_game, self.mock_game_history
        )

        self.MockPhaseState_from_game.assert_called_with(self.mock_game)
        self.mock_llm_agent.negotiate.assert_called_once_with(
            self.mock_phase_state_instance
        )
        self.mock_game_history.add_message.assert_called_once_with(
            "S1901M", "ENGLAND", "FRANCE", "Hello from ENGLAND"
        )

    async def test_execute_movement_phase_llm_agent_decide_orders(self):
        self.mock_game.get_current_phase.return_value = "S1901M"
        # _get_orders_for_power is called, which then calls agent.decide_orders
        # The result of decide_orders is List[Order], add_orders expects List[str]
        # So, need to mock what add_orders receives.
        # The orchestrator's _get_orders_for_power will convert Order to str if GamePhaseOrchestrator is responsible,
        # or LLMAgent.decide_orders returns List[str].
        # Given LLMAgent returns List[Order], and GameHistory.add_orders likely takes List[str],
        # there's a type mismatch to consider.
        # For this test, we assume _get_orders_for_power handles the conversion if necessary,
        # or that add_orders can take List[Order] or List[str].
        # The current _get_orders_for_power in orchestrator returns List[str] from the callback,
        # but for LLMAgent, it returns List[Order] from decide_orders.
        # Let's assume the test is checking the direct output from decide_orders is used.
        # GameHistory.add_orders(phase, power, orders_list_str)
        # This means the orchestrator must convert Order objects to strings.
        # The refactored _get_orders_for_power in previous step returns List[str] for LLMAgent
        # IF agent.decide_orders returns List[str]. But LLMAgent returns List[Order].
        # This test will assume the orchestrator handles this.

        # Let's adjust the mock_llm_agent.decide_orders to return List[Order] as LLMAgent does
        self.mock_llm_agent.decide_orders = AsyncMock(return_value=[Order("A LON H")])

        with patch.object(
            self.orchestrator,
            "_get_orders_for_power",
            new=AsyncMock(return_value=["A LON H"]),
        ) as mock_gofp:
            mock_gofp.return_value = [
                "A LON H"
            ]  # Ensure it returns List[str] as expected by caller loop

            await self.orchestrator._execute_movement_phase_actions(
                self.mock_game, self.mock_game_history
            )

            # Check that _get_orders_for_power was called for ENGLAND
            mock_gofp.assert_called_once_with(
                self.mock_game, "ENGLAND", self.mock_llm_agent, self.mock_game_history
            )

        # Now, assert that GameHistory.add_orders was called with the string list
        self.mock_game_history.add_orders.assert_called_once_with(
            "S1901M", "ENGLAND", ["A LON H"]
        )

        # And that the agent's generate_order_diary_entry was called
        # generate_order_diary_entry in the old agent took List[str].
        # If LLMAgent.generate_order_diary_entry expects List[Order], this also needs care.
        # Assuming List[str] for now based on common patterns.
        self.mock_llm_agent.generate_order_diary_entry.assert_called_once_with(
            self.mock_game, ["A LON H"], self.mock_game_config.llm_log_path
        )

    def test_get_phase_type_from_game(self):
        test_cases = {
            "S1901M": PhaseType.MVT.value,
            "FALL 1901 MOVEMENT": PhaseType.MVT.value,
            "F1901A": PhaseType.BLD.value,  # Adjustment is BLD
            "WINTER 1901 BUILD": PhaseType.BLD.value,
            "SPRING 1902 RETREAT": PhaseType.RET.value,
            "S1902R": PhaseType.RET.value,
            "COMPLETED": "-",
            "FORMING": "-",
            "": "-",
            "S1905X": "X",  # Fallback to last char if not recognized
            "SUMMER 1901 WEIRDPHASE": "WEIRDPHASE",  # Fallback to last char if not recognized
        }
        for phase_str, expected_type in test_cases.items():
            with self.subTest(phase_str=phase_str):
                self.mock_game.get_current_phase = Mock(return_value=phase_str)
                phase_type = self.orchestrator.get_phase_type_from_game(self.mock_game)
                self.assertEqual(phase_type, expected_type)


if __name__ == "__main__":
    unittest.main()
