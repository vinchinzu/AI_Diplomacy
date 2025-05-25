import unittest
import asyncio
from unittest.mock import patch, MagicMock 
from ai_diplomacy.llm_coordinator import LocalLLMCoordinator, LLMCallResult
from ai_diplomacy.llm_interface import AgentLLMInterface
from ai_diplomacy.game_config import GameConfig
from diplomacy import Game
from ai_diplomacy.game_history import GameHistory
from ai_diplomacy.utils import get_valid_orders # Step 1: Import get_valid_orders

class TestMockedLLMCalls(unittest.IsolatedAsyncioTestCase):

    def _setup_common_mocks_and_objects(self):
        # Common GameConfig
        class TestArgs:
            def __init__(self):
                self.power_name = "FRANCE"
                self.model_ids = ["test_model"]
                self.num_players = 1
                self.game_id_prefix = "test_mock"
                self.game_id = "test_mock_123"
                self.log_level = "INFO"
                self.log_to_file = False
                self.log_dir = "./mock_test_logs"
                self.perform_planning_phase = False
                self.num_negotiation_rounds = 0
                self.negotiation_style = "simultaneous"
                self.fixed_models = ["test_model"] 
                self.randomize_fixed_models = False
                self.exclude_powers = None
                self.max_years = None
                self.test_powers = "FRANCE"
        args = TestArgs()
        config = GameConfig(args)

        game = Game()
        game.set_phase("S1901M") # Important for some internal logic
        
        # Mock GameHistory for get_valid_orders if needed, or use a real one
        game_history = MagicMock(spec=GameHistory)
        game_history.get_event_log_for_power.return_value = "Fake history log"
        game_history.get_full_event_log.return_value = "Fake full history log"


        coordinator = LocalLLMCoordinator()
        agent_interface = AgentLLMInterface(
            model_id="test_model",
            system_prompt="You are a helpful assistant for FRANCE.",
            coordinator=coordinator,
            power_name="FRANCE",
            game_id=config.game_id
        )
        return game, game_history, agent_interface, config

    @patch('ai_diplomacy.llm_coordinator.LocalLLMCoordinator.llm_call_internal')
    async def test_mock_agent_negotiation_diary_success(self, mock_llm_call_internal):
        game, game_history, agent_interface, config = self._setup_common_mocks_and_objects()

        mock_response_json_string = '{ "negotiation_summary": "Test summary", "updated_relationships": {"GERMANY": "Ally"}}'
        mock_llm_call_result = LLMCallResult(
            success=True, raw_response=mock_response_json_string, parsed_json=None, # Parsed JSON not used by llm_call_internal directly
            error_message=None, model_id="test_model", prompt_text="", system_prompt_text=""
        )
        mock_llm_call_internal.return_value = asyncio.Future()
        mock_llm_call_internal.return_value.set_result(mock_llm_call_result)

        # generate_negotiation_diary expects: game_phase, board_state_str, other_powers_messages
        result = await agent_interface.generate_negotiation_diary(
            game_phase="S1901M",
            board_state_str="dummy_board_state",
            other_powers_messages={"GERMANY": ["Hello from GERMANY"]}
        )

        mock_llm_call_internal.assert_called_once()
        expected_diary = { "negotiation_summary": "Test summary", "updated_relationships": {"GERMANY": "Ally"}}
        self.assertEqual(result, expected_diary)

    @patch('ai_diplomacy.llm_coordinator.LocalLLMCoordinator.llm_call_internal')
    async def test_mock_agent_negotiation_diary_json_fail(self, mock_llm_call_internal):
        game, game_history, agent_interface, config = self._setup_common_mocks_and_objects()

        mock_response_malformed_json_string = '{ "negotiation_summary": "Test summary", "updated_relationships": {"GERMANY": "Ally"' # Missing closing brace
        mock_llm_call_result = LLMCallResult(
            success=True, raw_response=mock_response_malformed_json_string, parsed_json=None,
            error_message=None, model_id="test_model", prompt_text="", system_prompt_text=""
        )
        mock_llm_call_internal.return_value = asyncio.Future()
        mock_llm_call_internal.return_value.set_result(mock_llm_call_result)

        result = await agent_interface.generate_negotiation_diary(
            game_phase="S1901M",
            board_state_str="dummy_board_state",
            other_powers_messages={"GERMANY": ["Hello from GERMANY"]}
        )
        
        mock_llm_call_internal.assert_called_once()
        # Expect an error-like dictionary or specific handling
        self.assertIn("error", result) 
        self.assertIn("Failed to parse LLM response for negotiation diary", result["error"])


    @patch('ai_diplomacy.llm_coordinator.LocalLLMCoordinator.llm_call_internal')
    async def test_mock_get_valid_orders_success(self, mock_llm_call_internal):
        game, game_history, _, config = self._setup_common_mocks_and_objects()
        power_name = "FRANCE"
        # Units for FRANCE in S1901M: A PAR, A MAR, F BRE
        game.set_units("FRANCE", ["A PAR", "A MAR", "F BRE"])
        possible_orders = game.get_all_possible_orders() 
        # Example: {'A PAR': ['A PAR H', 'A PAR M BUR', ...], ...}

        mock_response_json_string = '{"orders": ["A PAR H", "A MAR H", "F BRE H"]}'
        # llm_call_internal (mocked) returns LLMCallResult.
        # call_llm_with_json_parsing (used by get_valid_orders) receives this.
        # Its _extract_json_from_text method will use the raw_response from this result.
        mock_llm_call_result = LLMCallResult(
            success=True, raw_response=mock_response_json_string, parsed_json=None, # Parsed JSON is not set by llm_call_internal
            error_message=None, model_id="test_model", prompt_text="dummy_prompt", system_prompt_text="dummy_system_prompt"
        )
        mock_llm_call_internal.return_value = asyncio.Future()
        mock_llm_call_internal.return_value.set_result(mock_llm_call_result)

        orders = await get_valid_orders(
            game=game,
            model_id="test_model",
            agent_system_prompt="System prompt for FRANCE",
            board_state=game.get_state(),
            power_name=power_name,
            possible_orders=possible_orders, # Pass the real possible_orders
            game_history=game_history,
            game_id=config.game_id,
            agent_goals=["Goal 1"],
            agent_relationships={"GERMANY": "Neutral"},
            log_file_path="./mock_test_logs/orders.csv",
            phase="S1901M"
        )

        mock_llm_call_internal.assert_called_once()
        self.assertEqual(orders, ["A PAR H", "A MAR H", "F BRE H"])

    @patch('ai_diplomacy.llm_coordinator.LocalLLMCoordinator.llm_call_internal')
    async def test_mock_get_valid_orders_json_fail(self, mock_llm_call_internal):
        game, game_history, _, config = self._setup_common_mocks_and_objects()
        power_name = "FRANCE"
        game.set_units("FRANCE", ["A PAR", "A MAR", "F BRE"])
        # Define possible_orders to predict fallback
        # In S1901M, A PAR can hold or move to BUR, PIC, GAS. F BRE can hold or move to MAO, ENG, PIC. A MAR can hold or move to SPA, PIE, GAS, BUR.
        possible_orders_for_france = {
            loc: game.get_all_possible_orders()[loc] 
            for loc in game.get_orderable_locations(power_name)
        }
        # Fallback should be HOLD for all units if possible
        expected_fallback_orders = []
        for loc in game.get_orderable_locations(power_name):
            unit_type = loc.split()[0] # A or F
            unit_loc = loc.split()[1]
            hold_order = f"{unit_type} {unit_loc} H"
            if hold_order in possible_orders_for_france[loc]:
                 expected_fallback_orders.append(hold_order)
            elif possible_orders_for_france[loc]: # if no hold, take first possible
                expected_fallback_orders.append(possible_orders_for_france[loc][0])
        
        # Sort for consistent comparison
        expected_fallback_orders.sort()


        mock_response_malformed_json_string = '{"orders": ["A PAR H", "A MAR H", "F BRE H"' # Missing closing brace
        mock_llm_call_result = LLMCallResult(
            success=True, raw_response=mock_response_malformed_json_string, parsed_json=None,
            error_message=None, model_id="test_model", prompt_text="", system_prompt_text=""
        )
        mock_llm_call_internal.return_value = asyncio.Future()
        mock_llm_call_internal.return_value.set_result(mock_llm_call_result)

        orders = await get_valid_orders(
            game=game, model_id="test_model", agent_system_prompt="System prompt",
            board_state=game.get_state(), power_name=power_name,
            possible_orders=possible_orders_for_france, game_history=game_history, game_id=config.game_id
        )

        mock_llm_call_internal.assert_called_once()
        # Sort actual orders for consistent comparison
        orders.sort()
        self.assertEqual(orders, expected_fallback_orders)

    @patch('ai_diplomacy.llm_coordinator.LocalLLMCoordinator.llm_call_internal')
    async def test_mock_get_valid_orders_empty_response(self, mock_llm_call_internal):
        game, game_history, _, config = self._setup_common_mocks_and_objects()
        power_name = "FRANCE"
        game.set_units("FRANCE", ["A PAR", "A MAR", "F BRE"])
        possible_orders_for_france = {
            loc: game.get_all_possible_orders()[loc] 
            for loc in game.get_orderable_locations(power_name)
        }
        expected_fallback_orders = []
        for loc in game.get_orderable_locations(power_name):
            unit_type = loc.split()[0]
            unit_loc = loc.split()[1]
            hold_order = f"{unit_type} {unit_loc} H"
            if hold_order in possible_orders_for_france[loc]:
                 expected_fallback_orders.append(hold_order)
            elif possible_orders_for_france[loc]:
                expected_fallback_orders.append(possible_orders_for_france[loc][0])
        expected_fallback_orders.sort()

        mock_empty_response_string = ""
        mock_llm_call_result = LLMCallResult(
            success=True, raw_response=mock_empty_response_string, parsed_json=None,
            error_message=None, model_id="test_model", prompt_text="", system_prompt_text=""
        )
        mock_llm_call_internal.return_value = asyncio.Future()
        mock_llm_call_internal.return_value.set_result(mock_llm_call_result)

        orders = await get_valid_orders(
            game=game, model_id="test_model", agent_system_prompt="System prompt",
            board_state=game.get_state(), power_name=power_name,
            possible_orders=possible_orders_for_france, game_history=game_history, game_id=config.game_id
        )

        mock_llm_call_internal.assert_called_once()
        orders.sort()
        self.assertEqual(orders, expected_fallback_orders)


if __name__ == '__main__':
    unittest.main()
