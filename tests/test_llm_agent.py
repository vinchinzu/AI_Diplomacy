import unittest
from unittest.mock import MagicMock, AsyncMock, patch, call
from typing import Optional, Callable, List, Dict, Any
import logging

from ai_diplomacy import constants as diplomacy_constants
from generic_llm_framework import constants as generic_constants
from ai_diplomacy.agents.llm_agent import LLMAgent
from ai_diplomacy.agents.base import Order, Message, PhaseState
from ai_diplomacy.services.config import AgentConfig
from ai_diplomacy.services.context_provider import ContextProvider, ContextData # Added ContextData
from ai_diplomacy.agents.factory import AgentFactory # For test_agent_with_various_context_providers

# Updated patch paths
from generic_llm_framework.llm_coordinator import LLMCoordinator as GenericLLMCoordinator
from generic_llm_framework.prompt_strategy import DiplomacyPromptStrategy # Renamed, not aliased here for clarity in patches
from generic_llm_framework.agent import GenericLLMAgent as FrameworkGenericLLMAgent


class TestLLMAgent(unittest.IsolatedAsyncioTestCase):
    def _create_mock_prompt_loader(self) -> Callable[[str], Optional[str]]:
        return MagicMock(spec=Callable[[str], Optional[str]])

    @patch("ai_diplomacy.agents.llm_agent.ContextProviderFactory", autospec=True)
    @patch("ai_diplomacy.agents.llm_agent.GenericLLMAgent", autospec=True)
    @patch("ai_diplomacy.agents.llm_agent.DiplomacyPromptStrategy", autospec=True)
    @patch("ai_diplomacy.agents.llm_agent.DiplomacyAgentState", autospec=True)
    @patch("ai_diplomacy.agents.llm_agent.load_prompt_file", autospec=True) # Patches the imported generic load_prompt_file
    async def asyncSetUp(
        self,
        mock_load_prompt_file,
        MockDiplomacyAgentState,
        MockDiplomacyPromptStrategy,
        MockGenericLLMAgent,
        MockContextProviderFactory,
    ):
        self.MockDiplomacyAgentState = MockDiplomacyAgentState
        self.MockDiplomacyPromptStrategy = MockDiplomacyPromptStrategy
        self.MockGenericLLMAgent = MockGenericLLMAgent
        self.MockContextProviderFactory = MockContextProviderFactory
        self.mock_load_prompt_file = mock_load_prompt_file # This is the one used by LLMAgent for its _load_system_prompt

        self.mock_agent_state = self.MockDiplomacyAgentState.return_value
        self.mock_diplomacy_prompt_strategy_instance = self.MockDiplomacyPromptStrategy.return_value

        self.mock_generic_agent_instance = self.MockGenericLLMAgent.return_value
        self.mock_generic_agent_instance.decide_action = AsyncMock()
        self.mock_generic_agent_instance.generate_communication = AsyncMock()
        self.mock_generic_agent_instance.update_internal_state = AsyncMock()
        self.mock_generic_agent_instance.get_agent_info = MagicMock(return_value={"generic_key": "generic_value"})

        self.mock_llm_coordinator = AsyncMock(spec=GenericLLMCoordinator) # LLMAgent takes this
        self.mock_context_provider_factory_instance = MockContextProviderFactory.return_value # Renamed for clarity

        self.mock_agent_state.goals = ["Initial Goal"]
        self.mock_agent_state.relationships = {"GERMANY": "Neutral", "ITALY": "Friendly"}
        self.mock_agent_state.format_private_diary_for_prompt = MagicMock(return_value="Formatted diary from mock")
        self.mock_agent_state._update_relationships_from_events = MagicMock()
        self.mock_agent_state.private_diary = []
        self.mock_agent_state.private_journal = []

        self.mock_context_provider = AsyncMock(spec=ContextProvider, autospec=True)
        self.mock_context_provider.get_provider_type.return_value = "inline"
        self.mock_context_provider.provide_context = AsyncMock(
            return_value={"context_text": "Default context", "tools_available": False, "provider_type": "inline", "tools": []}
        )
        self.mock_context_provider_factory_instance.get_provider.return_value = self.mock_context_provider # Corrected factory usage

        self.mock_load_prompt_file.return_value = "Default system prompt from loader"

        self.mock_agent_state.add_journal_entry.reset_mock()

        self.agent_config = AgentConfig(
            country="FRANCE", type="llm", model_id="test_model", context_provider="inline",
            prompt_strategy_config=None
        )

        self.agent = LLMAgent(
            agent_id="test_agent_007", country="FRANCE", config=self.agent_config, game_id="test_game",
            llm_coordinator=self.mock_llm_coordinator,
            context_provider_factory=self.mock_context_provider_factory_instance, # Use instance
            prompt_loader=self.mock_load_prompt_file,
            llm_caller_override=None,
        )

    async def test_initialization(self):
        self.MockDiplomacyAgentState.assert_called_with(country="FRANCE")
        self.MockDiplomacyPromptStrategy.assert_called_with(config=self.agent_config.prompt_strategy_config)
        self.MockGenericLLMAgent.assert_called_once()
        generic_agent_args = self.MockGenericLLMAgent.call_args[1]
        self.assertEqual(generic_agent_args['agent_id'], "test_agent_007")
        self.assertEqual(generic_agent_args['config']['model_id'], "test_model")
        self.assertEqual(generic_agent_args['config']['system_prompt'], "Default system prompt from loader")
        self.assertEqual(generic_agent_args['llm_coordinator'], self.mock_llm_coordinator)
        self.assertEqual(generic_agent_args['prompt_strategy'], self.mock_diplomacy_prompt_strategy_instance)
        self.assertEqual(self.agent.resolved_context_provider_type, "inline")
        self.mock_agent_state.add_journal_entry.assert_any_call(
            f"Agent initialized with model {self.agent_config.model_id}, context provider: inline"
        )
        self.mock_load_prompt_file.assert_any_call("france_system_prompt.txt")

    @patch("ai_diplomacy.agents.llm_agent.load_prompt_file", autospec=True)
    async def test_initialization_no_prompt_loader_uses_direct_import(self, mock_direct_load_p_file):
        mock_direct_load_p_file.return_value = "Prompt from direct llm_utils"
        with patch("ai_diplomacy.agents.llm_agent.GenericLLMAgent", autospec=True) as MockGenericAgentForThisTest:
            mock_generic_instance_local = MockGenericAgentForThisTest.return_value
            agent = LLMAgent(
                agent_id="test_agent_no_loader", country="FRANCE", config=self.agent_config,
                game_id="test_game_no_loader", llm_coordinator=self.mock_llm_coordinator,
                context_provider_factory=self.mock_context_provider_factory_instance,
                prompt_loader=None, llm_caller_override=None,
            )
            self.assertIsNotNone(agent.system_prompt)
            mock_direct_load_p_file.assert_any_call("france_system_prompt.txt")
            self.assertNotEqual(agent.generic_agent, self.mock_generic_agent_instance)
            self.assertEqual(agent.generic_agent, mock_generic_instance_local)

    async def test_load_system_prompt_power_specific(self):
        self.mock_load_prompt_file.reset_mock(side_effect=True)
        self.mock_load_prompt_file.side_effect = ["Power-specific prompt", "Default prompt"]
        prompt = self.agent._load_system_prompt()
        self.assertEqual(prompt, "Power-specific prompt")
        self.mock_load_prompt_file.assert_any_call("france_system_prompt.txt")
        was_default_called = any(c == call(diplomacy_constants.DEFAULT_SYSTEM_PROMPT_FILENAME) for c in self.mock_load_prompt_file.call_args_list)
        self.assertFalse(was_default_called, "Default prompt should not have been loaded.")

    async def test_load_system_prompt_default(self):
        self.mock_load_prompt_file.reset_mock(side_effect=True)
        self.mock_load_prompt_file.side_effect = [None, "Default prompt from loader"]
        prompt = self.agent._load_system_prompt()
        self.assertEqual(prompt, "Default prompt from loader")
        self.mock_load_prompt_file.assert_has_calls([
            call("france_system_prompt.txt"), call(diplomacy_constants.DEFAULT_SYSTEM_PROMPT_FILENAME)], any_order=False)

    async def test_load_system_prompt_failure(self):
        self.mock_load_prompt_file.reset_mock(side_effect=True)
        self.mock_load_prompt_file.side_effect = [None, None]
        prompt = self.agent._load_system_prompt()
        self.assertIsNone(prompt)

    async def test_decide_orders_no_units(self):
        mock_phase_state = MagicMock(spec=PhaseState); mock_phase_state.get_power_units.return_value = []
        orders = await self.agent.decide_orders(mock_phase_state)
        self.assertEqual(orders, [])
        self.mock_generic_agent_instance.decide_action.assert_not_called()

    async def test_decide_orders_successful(self):
        mock_phase_state = MagicMock(spec=PhaseState); mock_phase_state.get_power_units.return_value = ["A PAR"]
        mock_phase_state.phase_name="S1901M"; mock_phase_state.get_all_possible_orders.return_value = {}
        mock_phase_state.get_power_centers.return_value = ["PAR"]
        mock_possible_orders = {"A PAR": ["A PAR H", "A PAR M MAR"]}
        mock_phase_state.get_all_possible_orders.return_value = mock_possible_orders
        mock_phase_state.get_power_centers.return_value = ["PAR"]

        context_provider_return_value = {"context_text": "Ctx", "tools_available": False, "tools": ["tool1", "tool2"]}
        self.mock_context_provider.provide_context.return_value = context_provider_return_value
        self.mock_generic_agent_instance.decide_action.return_value = {diplomacy_constants.LLM_RESPONSE_KEY_ORDERS: ["A PAR H"]}

        # Clear previous config if any, to ensure we test the update
        self.agent.generic_agent.config.pop("phase", None)
        self.agent.generic_agent.config.pop("tools", None)

        orders = await self.agent.decide_orders(mock_phase_state)

        self.mock_generic_agent_instance.decide_action.assert_called_once()
        call_args = self.mock_generic_agent_instance.decide_action.call_args
        passed_state = call_args[1]['state']
        passed_possible_actions = call_args[1]['possible_actions']

        # Assertions for state keys and values
        self.assertEqual(passed_state['country'], "FRANCE")
        self.assertEqual(passed_state['goals'], self.mock_agent_state.goals)
        self.assertEqual(passed_state['relationships'], self.mock_agent_state.relationships)
        self.assertEqual(passed_state['formatted_diary'], self.mock_agent_state.format_private_diary_for_prompt.return_value)
        self.assertEqual(passed_state['context_text'], "Ctx")
        self.assertEqual(passed_state['tools_available'], False) # from context_provider_return_value
        self.assertEqual(passed_state['phase_name'], "S1901M")
        self.assertEqual(passed_state['power_units'], ["A PAR"])
        self.assertEqual(passed_state['power_centers'], ["PAR"])

        # Verify possible_actions argument
        self.assertEqual(passed_possible_actions, mock_possible_orders)

        # Verify generic_agent.config updates
        self.assertEqual(self.agent.generic_agent.config.get("phase"), "S1901M")
        self.assertEqual(self.agent.generic_agent.config.get("tools"), context_provider_return_value["tools"])

        self.assertEqual(orders, [Order("A PAR H")])

    async def test_decide_orders_generic_agent_error(self):
        mock_phase_state = MagicMock(spec=PhaseState); mock_phase_state.get_power_units.return_value = ["A PAR"]
        self.mock_generic_agent_instance.decide_action.return_value = {"error": "Exploded"}
        with self.assertRaisesRegex(ValueError, "GenericAgent reported error deciding orders: Exploded"):
            await self.agent.decide_orders(mock_phase_state)

    async def test_decide_orders_bad_llm_response_from_generic_agent(self):
        mock_phase_state = MagicMock(spec=PhaseState); mock_phase_state.get_power_units.return_value = ["A PAR"]
        self.mock_generic_agent_instance.decide_action.return_value = {"other_key": "val"}
        with self.assertRaisesRegex(ValueError, f"No valid '{diplomacy_constants.LLM_RESPONSE_KEY_ORDERS}' field"):
            await self.agent.decide_orders(mock_phase_state)

    async def test_decide_orders_context_provider_exception(self):
        mock_phase_state = MagicMock(spec=PhaseState); mock_phase_state.get_power_units.return_value = ["A PAR"]
        self.mock_context_provider.provide_context.side_effect = Exception("CtxFail")
        with self.assertRaisesRegex(RuntimeError, "Unexpected error deciding orders: CtxFail"):
            await self.agent.decide_orders(mock_phase_state)

    def test_extract_orders_from_response(self):
        agent = LLMAgent("id", "FRANCE", self.agent_config, llm_coordinator=self.mock_llm_coordinator, context_provider_factory=self.mock_context_provider_factory_instance, prompt_loader=self.mock_load_prompt_file)
        with self.assertRaises(ValueError): agent._extract_orders_from_response(None, ["A PAR"])
        with self.assertRaises(ValueError): agent._extract_orders_from_response("text", ["A PAR"])
        with self.assertRaises(ValueError): agent._extract_orders_from_response([], ["A PAR"]) # Empty orders with units
        self.assertEqual(agent._extract_orders_from_response([], []), []) # Empty orders, no units
        self.assertEqual(agent._extract_orders_from_response(["A PAR H"], []), []) # Orders but no units

    def test_extract_orders_from_response_varied_inputs(self):
        agent = LLMAgent("id_extract_orders", "FRANCE", self.agent_config, llm_coordinator=self.mock_llm_coordinator,
                         context_provider_factory=self.mock_context_provider_factory_instance,
                         prompt_loader=self.mock_load_prompt_file)

        # Mock power units for these tests
        power_units_france = ["A PAR", "F MAR", "A BUD", "A VIE", "A TRI"]

        # 1. Already covered by test_extract_orders_from_response for None, "not a list"

        # 2. Empty list of orders (with units)
        self.assertEqual(agent._extract_orders_from_response([], power_units_france), [])

        # 3. List with mixed valid string orders and invalid items
        mixed_input = ["A PAR H", None, "F MAR S A PAR", 123, {"order": "A BUD H"}, "", "  A VIE H  ", "A CON H"] # A CON not in power_units
        expected_mixed = [Order("A PAR H"), Order("F MAR S A PAR"), Order("A VIE H")] # A BUD H from dict is ignored, A CON H ignored
        self.assertEqual(agent._extract_orders_from_response(mixed_input, power_units_france), expected_mixed)

        # 4. List with dictionary orders (some valid, some not)
        dict_input = [
            {"unit": "A PAR", "action": "H"},                                      # Valid
            {"unit": "F MAR", "action": "S A PAR"},                                # Valid
            {"unit": "A VIE"},                                                      # Missing 'action'
            {"action": "H BUD"},                                                    # Missing 'unit'
            {"unit": "A TRI", "action": None},                                      # 'action' is None
            {"unit": None, "action": "M VEN"},                                      # 'unit' is None
            {"unit": "A BUD", "action": ["H", "M TYR"]},                            # 'action' is a list
            {"unit": "A ROM", "action": "H"},                                      # Unit 'A ROM' not in power_units_france
            {"unit": 123, "action": "H"},                                           # unit is not string
            {"unit": "A BRE", "action": 456},                                       # action is not string
        ]
        # A BRE is not in power_units_france, but this test focuses on structure first.
        # The filtering by power_units is tested in scenario 5 & implicitly by A ROM H.
        expected_dict = [Order("A PAR H"), Order("F MAR S A PAR")]
        self.assertEqual(agent._extract_orders_from_response(dict_input, power_units_france), expected_dict)

        # 5. Orders for units the power does not possess
        foreign_orders_input = ["A ROM H", "F NAP M ION", "A PAR H"] # A PAR H is a valid own unit
        power_units_minimal = ["A PAR"]
        expected_foreign = [Order("A PAR H")]
        self.assertEqual(agent._extract_orders_from_response(foreign_orders_input, power_units_minimal), expected_foreign)
        self.assertEqual(agent._extract_orders_from_response(["A ROM H"], power_units_minimal), [])


        # 6. Strings with only whitespace (and mixed with valid)
        whitespace_input = ["A PAR H", "   ", "\t\n", "  F MAR H  "]
        expected_whitespace = [Order("A PAR H"), Order("F MAR H")]
        self.assertEqual(agent._extract_orders_from_response(whitespace_input, power_units_france), expected_whitespace)
        self.assertEqual(agent._extract_orders_from_response(["   ", "\t\n"], power_units_france), [])


    async def test_negotiate_successful(self):
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.powers = frozenset(["FRANCE", "ENGLAND", "GERMANY"])
        mock_phase_state.get_power_units.return_value = ["A PAR"] # Example units
        mock_phase_state.get_power_centers.return_value = ["PAR"] # Example centers
        mock_phase_state.phase_name="S1901D"

        # Mock is_power_eliminated to control which powers are "living"
        def mock_is_power_eliminated(power_name):
            if power_name == "GERMANY":
                return True # Germany is eliminated
            return False # France and England are not
        mock_phase_state.is_power_eliminated.side_effect = mock_is_power_eliminated

        context_provider_return_value = {"context_text": "CtxNego", "tools_available": True, "tools": ["nego_tool"]}
        self.mock_context_provider.provide_context.return_value = context_provider_return_value
        self.mock_generic_agent_instance.generate_communication.return_value = {
            diplomacy_constants.LLM_RESPONSE_KEY_MESSAGES: [{"recipient": "ENGLAND", "content": "Hi"}]
        }

        # Clear previous config if any
        self.agent.generic_agent.config.pop("phase", None)
        self.agent.generic_agent.config.pop("tools", None)

        messages = await self.agent.negotiate(mock_phase_state)

        self.mock_generic_agent_instance.generate_communication.assert_called_once()
        call_args = self.mock_generic_agent_instance.generate_communication.call_args
        passed_state = call_args[1]['state']
        passed_recipients = call_args[1]['recipients']

        # Assertions for state keys and values
        self.assertEqual(passed_state['country'], "FRANCE")
        self.assertEqual(passed_state['goals'], self.mock_agent_state.goals)
        self.assertEqual(passed_state['relationships'], self.mock_agent_state.relationships)
        self.assertEqual(passed_state['formatted_diary'], self.mock_agent_state.format_private_diary_for_prompt.return_value)
        self.assertEqual(passed_state['context_text'], "CtxNego")
        self.assertEqual(passed_state['tools_available'], True) # from context_provider_return_value
        self.assertEqual(passed_state['phase_name'], "S1901D")
        self.assertEqual(passed_state['power_units'], ["A PAR"])
        self.assertEqual(passed_state['power_centers'], ["PAR"])
        self.assertEqual(passed_state['all_powers'], list(mock_phase_state.powers))
        self.assertEqual(passed_state['living_powers'], ["FRANCE", "ENGLAND"]) # Based on mock_is_power_eliminated

        # Verify recipients argument
        self.assertEqual(passed_recipients, ["ENGLAND"]) # Only ENGLAND is living and not FRANCE

        # Verify generic_agent.config updates
        self.assertEqual(self.agent.generic_agent.config.get("phase"), "S1901D")
        self.assertEqual(self.agent.generic_agent.config.get("tools"), context_provider_return_value["tools"])

        self.assertEqual(messages[0], Message("ENGLAND", "Hi", message_type=diplomacy_constants.MESSAGE_TYPE_BROADCAST))

    async def test_negotiate_generic_agent_error(self):
        mock_phase_state = MagicMock(spec=PhaseState); mock_phase_state.powers = frozenset(["FRANCE", "ENGLAND"]); mock_phase_state.is_power_eliminated.return_value = False
        self.mock_generic_agent_instance.generate_communication.return_value = {"error": "CommExploded"}
        messages = await self.agent.negotiate(mock_phase_state)
        self.assertEqual(messages, [])

    async def test_negotiate_bad_llm_response_from_generic_agent(self):
        mock_phase_state = MagicMock(spec=PhaseState); mock_phase_state.powers = frozenset(["FRANCE", "ENGLAND"]); mock_phase_state.is_power_eliminated.return_value = False
        self.mock_generic_agent_instance.generate_communication.return_value = {"other": "data"}
        messages = await self.agent.negotiate(mock_phase_state)
        self.assertEqual(messages, [])

    async def test_negotiate_context_provider_exception(self):
        mock_phase_state = MagicMock(spec=PhaseState); mock_phase_state.powers = frozenset(["FRANCE", "ENGLAND"]); mock_phase_state.is_power_eliminated.return_value = False
        self.mock_context_provider.provide_context.side_effect = Exception("CtxFailNego")
        messages = await self.agent.negotiate(mock_phase_state)
        self.assertEqual(messages, [])
        self.mock_generic_agent_instance.generate_communication.assert_not_called()

    def test_extract_messages_from_response(self):
        agent = LLMAgent("id", "FRANCE", self.agent_config, llm_coordinator=self.mock_llm_coordinator, context_provider_factory=self.mock_context_provider_factory_instance, prompt_loader=self.mock_load_prompt_file)
        mock_phase = MagicMock(spec=PhaseState); mock_phase.powers = ["ENGLAND"]
        self.assertEqual(agent._extract_messages_from_response(None, mock_phase), [])
        self.assertEqual(agent._extract_messages_from_response({}, mock_phase), [])
        self.assertEqual(agent._extract_messages_from_response({diplomacy_constants.LLM_RESPONSE_KEY_MESSAGES: "text"}, mock_phase), [])

    def test_extract_messages_from_response_varied_inputs(self):
        agent = LLMAgent("id_extract_msgs", "FRANCE", self.agent_config, llm_coordinator=self.mock_llm_coordinator,
                         context_provider_factory=self.mock_context_provider_factory_instance,
                         prompt_loader=self.mock_load_prompt_file)

        mock_phase = MagicMock(spec=PhaseState)
        mock_phase.powers = frozenset(["FRANCE", "ENGLAND", "GERMANY", "ITALY"])

        # 1. Test with None, not a list, or empty list for llm_response_messages
        self.assertEqual(agent._extract_messages_from_response(None, mock_phase), [])
        self.assertEqual(agent._extract_messages_from_response("not a list", mock_phase), [])
        self.assertEqual(agent._extract_messages_from_response([], mock_phase), [])

        # 2. List of message dicts with various issues
        messages_input = [
            {"recipient": "ENGLAND", "content": "Hello England!", "message_type": "BROADCAST"},  # Valid
            {"recipient": "GERMANY", "content": "Secret proposal", "message_type": "SECRET_PROPOSAL"},  # Valid
            {"recipient": "ITALY", "content": "Public?", "message_type": "PUBLIC_PROPOSAL"},  # Valid
            {"recipient": 123, "content": "Invalid recipient type"},  # Recipient not a string
            {"recipient": "", "content": "Empty recipient string"},  # Recipient is empty string
            {"recipient": "RUSSIA", "content": "Recipient not in phase.powers"},  # Recipient not in mock_phase.powers
            {"recipient": "ENGLAND"},  # Missing 'content'
            {"recipient": "GERMANY", "content": None},  # Non-string 'content'
            {"recipient": "ITALY", "content": "Invalid type", "message_type": "INVALID_TYPE"}, # Invalid 'message_type' (falls back to BROADCAST)
            {"recipient": "ENGLAND", "content": "Case insensitive type", "message_type": "broadcast"}, # Valid (processed as BROADCAST)
            {"recipient": "FRANCE", "content": "Message to self"},  # Recipient is self
            {},  # Empty dictionary
            "just a string",  # Item in list is not a dict
            None,  # Item in list is None
            {"recipient": "GERMANY", "content": ""}, # Empty content string (should be valid)
            {"recipient": "ITALY", "content": "  "}, # Whitespace content string (should be valid)
        ]

        expected_messages = [
            Message("ENGLAND", "Hello England!", message_type=diplomacy_constants.MESSAGE_TYPE_BROADCAST),
            Message("GERMANY", "Secret proposal", message_type=diplomacy_constants.MESSAGE_TYPE_SECRET_PROPOSAL),
            Message("ITALY", "Public?", message_type=diplomacy_constants.MESSAGE_TYPE_PUBLIC_PROPOSAL),
            # INVALID_TYPE falls back to BROADCAST because of .get(..., diplomacy_constants.MESSAGE_TYPE_BROADCAST)
            Message("ITALY", "Invalid type", message_type=diplomacy_constants.MESSAGE_TYPE_BROADCAST),
            Message("ENGLAND", "Case insensitive type", message_type=diplomacy_constants.MESSAGE_TYPE_BROADCAST),
            Message("GERMANY", "", message_type=diplomacy_constants.MESSAGE_TYPE_BROADCAST),
            Message("ITALY", "  ", message_type=diplomacy_constants.MESSAGE_TYPE_BROADCAST),
        ]

        actual_messages = agent._extract_messages_from_response({diplomacy_constants.LLM_RESPONSE_KEY_MESSAGES: messages_input}, mock_phase)

        # Using assertCountEqual because order might not be guaranteed, though current implementation preserves it.
        self.assertCountEqual(actual_messages, expected_messages)

        # Verify specific cases for clarity
        # Case: recipient is self (FRANCE) - should be filtered
        self.assertNotIn(Message("FRANCE", "Message to self", diplomacy_constants.MESSAGE_TYPE_BROADCAST), actual_messages)

        # Case: recipient not in phase.powers (RUSSIA) - should be filtered
        self.assertFalse(any(msg.recipient == "RUSSIA" for msg in actual_messages))

        # Case: Empty recipient string - should be filtered
        self.assertFalse(any(msg.recipient == "" for msg in actual_messages))

    async def test_update_state_diary_and_goals_success(self):
        mock_phase = MagicMock(spec=PhaseState)
        mock_phase.phase_name = "S1901M"
        # Note: mock_phase.country is not standard. Power name is obtained via self.agent.power_name
        mock_phase.get_power_units.return_value = ["A PAR", "M MAR"]
        mock_phase.get_power_centers.return_value = ["PAR", "MAR"]
        mock_phase.is_game_over = False
        mock_phase.powers = ["FRANCE", "ENGLAND"]
        mock_phase.is_power_eliminated.return_value = False # No one eliminated for this test
        mock_phase.get_center_count.return_value = 2 # Matches get_power_centers

        mock_events = [{"type": "event1"}, {"type": "event2"}]

        # Reset mocks for decide_action to handle multiple calls with different args
        self.mock_generic_agent_instance.decide_action.reset_mock()
        self.mock_generic_agent_instance.decide_action.side_effect = [
            {diplomacy_constants.LLM_RESPONSE_KEY_DIARY_ENTRY: "Test Diary Entry"},
            {
                diplomacy_constants.LLM_RESPONSE_KEY_UPDATED_GOALS: ["New Goal 1"],
                diplomacy_constants.LLM_RESPONSE_KEY_REASONING: "Because reasons"
            }
        ]
        # Reset mock for update_internal_state
        self.mock_generic_agent_instance.update_internal_state.reset_mock()

        await self.agent.update_state(mock_phase, mock_events)

        # 1. Verify arguments to update_internal_state
        self.mock_generic_agent_instance.update_internal_state.assert_called_once()
        update_internal_state_call_args = self.mock_generic_agent_instance.update_internal_state.call_args
        self.assertEqual(update_internal_state_call_args[1]['state'], mock_phase)
        self.assertEqual(update_internal_state_call_args[1]['events'], mock_events)

        # 2. Verify relationship update call
        self.mock_agent_state._update_relationships_from_events.assert_called_with(self.agent.power_name, mock_events)

        # 3. Verify decide_action calls (diary and goals)
        self.assertEqual(self.mock_generic_agent_instance.decide_action.call_count, 2)
        diary_call_args = self.mock_generic_agent_instance.decide_action.call_args_list[0]
        goal_call_args = self.mock_generic_agent_instance.decide_action.call_args_list[1]

        # 4. For Diary Generation part:
        self.assertEqual(diary_call_args[1]['action_type'], diplomacy_constants.LLM_ACTION_DIARY)
        diary_state_arg = diary_call_args[1]['state']
        diary_context_arg = diary_state_arg['diary_context']

        self.assertEqual(diary_context_arg['country'], self.agent.power_name)
        self.assertEqual(diary_context_arg['phase_name'], mock_phase.phase_name)
        self.assertEqual(diary_context_arg['units'], mock_phase.get_power_units.return_value)
        self.assertEqual(diary_context_arg['centers'], mock_phase.get_power_centers.return_value)
        self.assertEqual(diary_context_arg['is_game_over'], mock_phase.is_game_over)
        self.assertEqual(diary_context_arg['events'], mock_events)
        self.assertEqual(diary_context_arg['goals'], self.mock_agent_state.goals)
        self.assertEqual(diary_context_arg['relationships'], self.mock_agent_state.relationships)
        # Check that the generic agent's config was updated for the diary call
        self.assertEqual(self.agent.generic_agent.config.get("phase"), mock_phase.phase_name)


        # Check diary entry was added
        self.mock_agent_state.add_diary_entry.assert_called_with("Test Diary Entry", mock_phase.phase_name)

        # (Goal Analysis part will be detailed further in the next steps)
        # For now, just check it was called with the right action_type
        self.assertEqual(goal_call_args[1]['action_type'], diplomacy_constants.LLM_ACTION_GOAL_ANALYSIS)
        # And that agent state was updated with new goals
        self.assertEqual(self.mock_agent_state.goals, ["New Goal 1"])
        self.mock_agent_state.add_journal_entry.assert_any_call(
            f"Goals updated by LLM. Reasoning: Because reasons. New goals: {['New Goal 1']}"
        )

        # Further checks for goal analysis call state (as per plan item 3.Goal Analysis part)
        goal_state_arg = goal_call_args[1]['state']
        goal_context_arg = goal_state_arg['goal_analysis_context']
        self.assertEqual(goal_context_arg['country'], self.agent.power_name)
        self.assertEqual(goal_context_arg['phase_name'], mock_phase.phase_name)
        self.assertEqual(goal_context_arg['units'], mock_phase.get_power_units.return_value)
        self.assertEqual(goal_context_arg['centers'], mock_phase.get_power_centers.return_value)
        self.assertEqual(goal_context_arg['is_game_over'], mock_phase.is_game_over)
        self.assertEqual(goal_context_arg['events'], mock_events)
        # For goal analysis, 'current_goals' is self.mock_agent_state.goals *before* the update
        # In this test, decide_action for goals is the second call, so goals might have been updated by a hypothetical first call
        # However, our mock_agent_state.goals is reset in setup. So, the 'Initial Goal' is correct here.
        self.assertEqual(goal_context_arg['current_goals'], ["Initial Goal"]) # Assuming this was the state before this update_state call
        self.assertEqual(goal_context_arg['relationships'], self.mock_agent_state.relationships)
        self.assertEqual(goal_context_arg['private_diary'], self.mock_agent_state.format_private_diary_for_prompt.return_value)
        # Check that the generic agent's config was updated for the goal call as well
        self.assertEqual(self.agent.generic_agent.config.get("phase"), mock_phase.phase_name)


    async def test_update_state_diary_errors(self):
        mock_phase = MagicMock(spec=PhaseState)
        mock_phase.phase_name = "F1901M"
        mock_phase.get_power_units.return_value = []
        mock_phase.get_power_centers.return_value = []
        mock_phase.is_game_over = False
        mock_phase.powers = ["FRANCE"]
        mock_phase.is_power_eliminated.return_value = False
        mock_phase.get_center_count.return_value = 0
        mock_events = [{"type": "event_diary_error"}]

        # Reset relevant mocks
        self.mock_generic_agent_instance.decide_action.reset_mock()
        self.mock_agent_state.add_diary_entry.reset_mock()
        self.mock_agent_state.add_journal_entry.reset_mock() # For logging warnings

        # Scenario 1: decide_action returns an error for diary
        self.mock_generic_agent_instance.decide_action.side_effect = [
            {"error": "Diary explosion"}, # Error for diary
            {diplomacy_constants.LLM_RESPONSE_KEY_UPDATED_GOALS: ["Goal after diary error"], "reasoning": "Test"} # Successful goal update
        ]
        with self.assertLogs(level='WARNING') as log_capture:
            await self.agent.update_state(mock_phase, mock_events)
        self.mock_agent_state.add_diary_entry.assert_not_called()
        self.assertIn("Error generating diary entry: Diary explosion", log_capture.output[0])
        # Check that goal update still happened
        self.assertEqual(self.mock_agent_state.goals, ["Goal after diary error"])


        # Scenario 2: LLM_RESPONSE_KEY_DIARY_ENTRY is missing
        self.mock_generic_agent_instance.decide_action.reset_mock()
        self.mock_agent_state.add_diary_entry.reset_mock()
        self.mock_agent_state.goals = ["Initial Goal"] # Reset goals
        self.mock_generic_agent_instance.decide_action.side_effect = [
            {"unexpected_key": "No diary here"}, # Missing diary key
            {diplomacy_constants.LLM_RESPONSE_KEY_UPDATED_GOALS: ["Goal after missing key"], "reasoning": "Test"}
        ]
        with self.assertLogs(level='WARNING') as log_capture:
            await self.agent.update_state(mock_phase, mock_events)
        self.mock_agent_state.add_diary_entry.assert_not_called()
        self.assertIn(f"LLM response for diary generation missing '{diplomacy_constants.LLM_RESPONSE_KEY_DIARY_ENTRY}'", log_capture.output[0])
        self.assertEqual(self.mock_agent_state.goals, ["Goal after missing key"])


        # Scenario 3: LLM_RESPONSE_KEY_DIARY_ENTRY is not a string
        self.mock_generic_agent_instance.decide_action.reset_mock()
        self.mock_agent_state.add_diary_entry.reset_mock()
        self.mock_agent_state.goals = ["Initial Goal"] # Reset goals
        self.mock_generic_agent_instance.decide_action.side_effect = [
            {diplomacy_constants.LLM_RESPONSE_KEY_DIARY_ENTRY: 12345}, # Diary entry is not a string
            {diplomacy_constants.LLM_RESPONSE_KEY_UPDATED_GOALS: ["Goal after non-string diary"], "reasoning": "Test"}
        ]
        with self.assertLogs(level='WARNING') as log_capture:
            await self.agent.update_state(mock_phase, mock_events)
        self.mock_agent_state.add_diary_entry.assert_not_called()
        self.assertIn(f"Diary entry from LLM is not a string: 12345", log_capture.output[0])
        self.assertEqual(self.mock_agent_state.goals, ["Goal after non-string diary"])


    async def test_update_state_goal_analysis_errors_and_edge_cases(self):
        mock_phase = MagicMock(spec=PhaseState)
        mock_phase.phase_name = "S1902M_goal_errors"
        mock_phase.get_power_units.return_value = ["A VIE"]
        mock_phase.get_power_centers.return_value = ["VIE"]
        mock_phase.is_game_over = False
        mock_phase.powers = ["AUSTRIA"] # Assuming agent is AUSTRIA for this test
        mock_phase.is_power_eliminated.return_value = False
        mock_phase.get_center_count.return_value = 1
        mock_events = [{"type": "event_goal_error"}]

        initial_goals = ["Initial Goal for error testing"]
        self.agent.power_name = "AUSTRIA" # Align agent power with mock_phase
        self.mock_agent_state.country = "AUSTRIA"
        self.mock_agent_state.goals = list(initial_goals) # Use a copy

        # Common setup for decide_action: first call (diary) is successful, second (goals) is where we test errors
        successful_diary_response = {diplomacy_constants.LLM_RESPONSE_KEY_DIARY_ENTRY: "Diary entry during goal error tests"}

        # Reset mocks before each scenario
        def reset_mocks_for_scenario():
            self.mock_generic_agent_instance.decide_action.reset_mock()
            self.mock_agent_state.add_diary_entry.reset_mock()
            self.mock_agent_state.add_journal_entry.reset_mock()
            self.mock_agent_state.goals = list(initial_goals) # Reset goals

        # Scenario 1: decide_action returns an error for goals
        reset_mocks_for_scenario()
        self.mock_generic_agent_instance.decide_action.side_effect = [
            successful_diary_response,
            {"error": "Goal explosion"}
        ]
        with self.assertLogs(level='WARNING') as log_capture:
            await self.agent.update_state(mock_phase, mock_events)
        self.assertEqual(self.mock_agent_state.goals, initial_goals) # Goals unchanged
        # Check that add_journal_entry was not called for goal updates (it might be called for other reasons like init)
        self.assertFalse(any("Goals updated by LLM" in call.args[0] for call in self.mock_agent_state.add_journal_entry.call_args_list))
        self.assertIn("Error analyzing goals: Goal explosion", log_capture.output[0])
        self.mock_agent_state.add_diary_entry.assert_called_once() # Diary should still be processed

        # Scenario 2: LLM_RESPONSE_KEY_UPDATED_GOALS is missing
        reset_mocks_for_scenario()
        self.mock_generic_agent_instance.decide_action.side_effect = [
            successful_diary_response,
            {diplomacy_constants.LLM_RESPONSE_KEY_REASONING: "No goals here"} # Missing UPDATED_GOALS
        ]
        with self.assertLogs(level='WARNING') as log_capture:
            await self.agent.update_state(mock_phase, mock_events)
        self.assertEqual(self.mock_agent_state.goals, initial_goals)
        self.assertFalse(any("Goals updated by LLM" in call.args[0] for call in self.mock_agent_state.add_journal_entry.call_args_list))
        self.assertIn(f"LLM response for goal analysis missing '{diplomacy_constants.LLM_RESPONSE_KEY_UPDATED_GOALS}'", log_capture.output[0])

        # Scenario 3: LLM_RESPONSE_KEY_UPDATED_GOALS is not a list
        reset_mocks_for_scenario()
        self.mock_generic_agent_instance.decide_action.side_effect = [
            successful_diary_response,
            {diplomacy_constants.LLM_RESPONSE_KEY_UPDATED_GOALS: "Not a list", diplomacy_constants.LLM_RESPONSE_KEY_REASONING: "Test"}
        ]
        with self.assertLogs(level='WARNING') as log_capture:
            await self.agent.update_state(mock_phase, mock_events)
        self.assertEqual(self.mock_agent_state.goals, initial_goals)
        self.assertFalse(any("Goals updated by LLM" in call.args[0] for call in self.mock_agent_state.add_journal_entry.call_args_list))
        self.assertIn(f"Updated goals from LLM is not a list: Not a list", log_capture.output[0])

        # Scenario 4: Goals haven't actually changed
        reset_mocks_for_scenario()
        self.mock_generic_agent_instance.decide_action.side_effect = [
            successful_diary_response,
            {diplomacy_constants.LLM_RESPONSE_KEY_UPDATED_GOALS: list(initial_goals), diplomacy_constants.LLM_RESPONSE_KEY_REASONING: "Goals are fine"}
        ]
        await self.agent.update_state(mock_phase, mock_events)
        self.assertEqual(self.mock_agent_state.goals, initial_goals)
        # add_journal_entry should NOT be called for "Goals updated by LLM..."
        # It might be called for other things like "Agent initialized..." or "Diary entry added..."
        # So, we check specifically that the goal update message is absent.
        found_goal_update_log = False
        for call_args in self.mock_agent_state.add_journal_entry.call_args_list:
            if "Goals updated by LLM" in call_args[0][0]:
                found_goal_update_log = True
                break
        self.assertFalse(found_goal_update_log, "add_journal_entry should not be called for unchanged goals.")
        # Ensure no warnings were logged for this specific scenario
        # (Need to be careful if other parts of update_state log warnings)

        # Restore original agent power_name if it was changed
        self.agent.power_name = "FRANCE"
        self.mock_agent_state.country = "FRANCE"


    async def test_get_agent_info(self):
        self.mock_generic_agent_instance.get_agent_info.return_value = {"gid": "gen_agent", "g_model": "gen_model"}
        info = self.agent.get_agent_info()
        self.assertEqual(info["diplomacy_agent_id"], self.agent.agent_id)
        self.assertEqual(info["generic_agent_info"]["gid"], "gen_agent")

    async def test_agent_with_various_context_providers(self):
        # This test is more of an integration test, ensure mocks are correctly passed or real objects used carefully.
        # Using self.mock_context_provider_factory_instance which is already set up in asyncSetUp
        factory = AgentFactory(llm_coordinator=self.mock_llm_coordinator, context_provider_factory=self.mock_context_provider_factory_instance)
        inline_config = AgentConfig(country="FRANCE", type="llm", model_id="model1", context_provider="inline")

        # We need to mock what GenericLLMAgent's constructor is called with if we create a new agent
        # Or, use self.agent and reconfigure it if possible.
        # For simplicity, let's assume the factory correctly uses the mocked GenericLLMAgent from asyncSetUp for new agents too.
        # This requires that the AgentFactory is patched or uses the same mocks.
        # The current AgentFactory constructor will create a NEW LLMCoordinator if not provided.
        # And LLMAgent will create a NEW GenericLLMAgent if not patched at the class level.
        # This test might be better as an integration test or needs more complex patching.

        # Let's re-patch GenericLLMAgent for agents created by the factory in this test
        with patch("ai_diplomacy.agents.llm_agent.GenericLLMAgent", return_value=self.mock_generic_agent_instance) as PatchedGenericAgent:
            inline_agent = factory.create_agent("inline-test", "FRANCE", inline_config, "game_ctx_test")
            self.assertEqual(inline_agent.resolved_context_provider_type, "inline")

            mock_phase_state = MagicMock(spec=PhaseState); mock_phase_state.get_power_units.return_value = ["A PAR"]
            mock_phase_state.phase_name="S1901M_CTX"; mock_phase_state.get_all_possible_orders.return_value = {}
            mock_phase_state.get_power_centers.return_value = []

            self.mock_generic_agent_instance.decide_action.return_value = {diplomacy_constants.LLM_RESPONSE_KEY_ORDERS: ["A PAR H"]}
            await inline_agent.decide_orders(mock_phase_state)
            PatchedGenericAgent.return_value.decide_action.assert_called()


if __name__ == "__main__":
    unittest.main()
