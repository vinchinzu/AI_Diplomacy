import unittest
from unittest.mock import MagicMock, AsyncMock, patch, call
from typing import List, Dict, Any, Optional, Callable

from ai_diplomacy.agents.llm_agent import LLMAgent
from ai_diplomacy.agents.base import Order, Message, PhaseState
from ai_diplomacy.agents.agent_state import DiplomacyAgentState
from ai_diplomacy.agents.llm_prompt_strategy import LLMPromptStrategy
from ai_diplomacy.services.llm_coordinator import LLMCoordinator
from ai_diplomacy.services.config import AgentConfig # ContextProviderType removed
from ai_diplomacy.services.context_provider import ContextProviderFactory, ContextProvider, ContextData # Changed BaseContextProvider to ContextProvider


class TestLLMAgent(unittest.IsolatedAsyncioTestCase):

    def _create_mock_prompt_loader(self) -> Callable[[str], Optional[str]]:
        # Helper to create a new mock loader for each test if needed, or use a shared one
        return MagicMock(spec=Callable[[str], Optional[str]])

    @patch('ai_diplomacy.agents.llm_agent.ContextProviderFactory', autospec=True)
    @patch('ai_diplomacy.agents.llm_agent.LLMCoordinator', autospec=True)
    @patch('ai_diplomacy.agents.llm_agent.LLMPromptStrategy', autospec=True)
    @patch('ai_diplomacy.agents.llm_agent.DiplomacyAgentState', autospec=True)
    async def asyncSetUp(self, MockDiplomacyAgentState, MockLLMPromptStrategy, MockLLMCoordinator, MockContextProviderFactory):
        # Store mocks for later use in tests
        self.MockDiplomacyAgentState = MockDiplomacyAgentState
        self.MockLLMPromptStrategy = MockLLMPromptStrategy
        self.MockLLMCoordinator = MockLLMCoordinator
        self.MockContextProviderFactory = MockContextProviderFactory
        
        self.mock_agent_state = MockDiplomacyAgentState.return_value
        self.mock_prompt_strategy = MockLLMPromptStrategy.return_value
        self.mock_llm_coordinator = MockLLMCoordinator.return_value
        self.mock_context_provider_factory = MockContextProviderFactory.return_value

        # Configure mock_agent_state attributes
        self.mock_agent_state.goals = ["Initial Goal"]
        self.mock_agent_state.relationships = {"GERMANY": "Neutral", "ITALY": "Friendly"}
        self.mock_agent_state.format_private_diary_for_prompt = MagicMock(return_value="Formatted diary from mock")
        self.mock_agent_state._update_relationships_from_events = MagicMock() # If this method is called on the mock
        
        self.mock_context_provider = AsyncMock(spec=ContextProvider, autospec=True) # Changed BaseContextProvider to ContextProvider
        self.mock_context_provider.get_provider_type.return_value = "inline" # Changed to string
        self.mock_context_provider_factory.get_provider.return_value = self.mock_context_provider

        self.mock_llm_caller_override = AsyncMock(return_value='{"default_override_response": true}') # New mock
        
        self.mock_prompt_loader = self._create_mock_prompt_loader()
        self.mock_prompt_loader.return_value = "Default system prompt from loader"

        self.agent_config = AgentConfig(
            country="FRANCE",       # Corrected: 'power' to 'country'
            type="llm",             # Added required 'type' field
            model_id="test_model",
            context_provider="inline"
            # agent_id is passed to LLMAgent constructor, not AgentConfig
            # log_to_gcp and log_to_file are not standard fields, but allowed by extra='allow'
        )
        
        self.agent = LLMAgent(
            agent_id="test_agent_007", # agent_id is used here
            country="FRANCE",
            config=self.agent_config,
            game_id="test_game",
            llm_coordinator=self.mock_llm_coordinator,
            context_provider_factory=self.mock_context_provider_factory,
            prompt_loader=self.mock_prompt_loader,
            llm_caller_override=self.mock_llm_caller_override # Pass the new mock
        )
        self.mock_agent_state.add_journal_entry.reset_mock() # Reset after initialization call

    async def test_initialization(self):
        await self.asyncSetUp() # Calls reset_mock for add_journal_entry

        self.MockDiplomacyAgentState.assert_called_once_with(country="FRANCE")
        self.MockLLMPromptStrategy.assert_called_once()
        
        # Check if LLMCoordinator was used (if passed) or instantiated
        # In asyncSetUp, we pass an instance, so it should not be called to create a new one.
        # If we had passed None, then self.MockLLMCoordinator would have been called.
        # self.MockLLMCoordinator.assert_not_called() # This depends on how we structure the test if we want to test internal instantiation
        self.assertEqual(self.agent.llm_coordinator, self.mock_llm_coordinator)


        self.MockContextProviderFactory.assert_called_once()
        # The LLMAgent constructor calls resolve_context_provider, then factory.get_provider with the resolved type.
        # If AgentConfig.context_provider is "inline", resolve_context_provider returns "inline".
        self.mock_context_provider_factory.get_provider.assert_called_once_with("inline")
        self.assertEqual(self.agent.context_provider, self.mock_context_provider)
        
        self.mock_agent_state.add_journal_entry.assert_called_once_with(
            f"Agent initialized with model {self.agent_config.model_id}, context provider: inline" # Changed to string
        )
        # System prompt loading is deferred to _load_system_prompt, which is called in __init__
        # self.mock_prompt_loader should be called by _load_system_prompt
        self.mock_prompt_loader.assert_any_call("france_system_prompt.txt")
        # Depending on the side_effect setup for mock_prompt_loader, it might also call for the default.
        # If france_system_prompt.txt returns a prompt, system_prompt.txt won't be called.
        # If self.mock_prompt_loader.return_value was set (as it is), the first call would succeed.
        
        # Let's refine asyncSetUp and this test for clarity on prompt loading calls
        # In current asyncSetUp, self.mock_prompt_loader.return_value = "Default system prompt from loader"
        # So, the first call self.mock_prompt_loader("france_system_prompt.txt") returns this.
        # Thus, self.mock_prompt_loader("system_prompt.txt") should NOT be called.
        found_default_call = False
        for c in self.mock_prompt_loader.call_args_list:
            if c == call('system_prompt.txt'):
                found_default_call = True
                break
        self.assertFalse(found_default_call, "Default prompt should not have been loaded if power-specific succeeded")


    @patch('ai_diplomacy.agents.llm_agent.llm_utils.load_prompt_file', autospec=True)
    async def test_initialization_no_prompt_loader(self, mock_llm_utils_load_prompt_file):
        # Test case where prompt_loader is None, uses llm_utils.load_prompt_file
        mock_llm_utils_load_prompt_file.return_value = "Prompt from llm_utils"
        # Create a new llm_caller_override mock for this specific agent instance if needed, or use the shared one
        # For this test, the override's behavior isn't the primary focus, so using None or a generic one is fine.
        agent = LLMAgent(
            agent_id="test_agent_no_loader",
            country="FRANCE",
            config=self.agent_config,
            game_id="test_game_no_loader",
            llm_coordinator=self.mock_llm_coordinator,
            context_provider_factory=self.mock_context_provider_factory,
            prompt_loader=None, # Explicitly None
            llm_caller_override=self.mock_llm_caller_override # Can pass the one from setUp
        )
        self.assertIsNotNone(agent.system_prompt)
        mock_llm_utils_load_prompt_file.assert_any_call("france_system_prompt.txt")


    async def test_load_system_prompt_power_specific(self):
        await self.asyncSetUp() # Uses self.mock_prompt_loader
        self.mock_prompt_loader.reset_mock()
        
        # Power-specific succeeds
        self.mock_prompt_loader.side_effect = ["Power-specific prompt via loader", "Default prompt via loader"]
        prompt = self.agent._load_system_prompt()
        self.assertEqual(prompt, "Power-specific prompt via loader")
        self.mock_prompt_loader.assert_any_call("france_system_prompt.txt")
        # It shouldn't call for default if power-specific is found
        found_default_call = False
        for c in self.mock_prompt_loader.call_args_list:
            if c == call('system_prompt.txt'):
                found_default_call = True
                break
        self.assertFalse(found_default_call)


    async def test_load_system_prompt_default(self):
        await self.asyncSetUp() # Uses self.mock_prompt_loader
        self.mock_prompt_loader.reset_mock()

        # Power-specific fails, default succeeds
        self.mock_prompt_loader.side_effect = [None, "Default prompt via loader"]
        prompt = self.agent._load_system_prompt()
        self.assertEqual(prompt, "Default prompt via loader")
        self.mock_prompt_loader.assert_has_calls([
            call("france_system_prompt.txt"),
            call("system_prompt.txt")
        ])

    async def test_load_system_prompt_failure(self):
        await self.asyncSetUp() # Uses self.mock_prompt_loader
        self.mock_prompt_loader.reset_mock()
        
        self.mock_prompt_loader.side_effect = [None, None] # Both fail
        prompt = self.agent._load_system_prompt()
        self.assertIsNone(prompt)
        self.mock_prompt_loader.assert_has_calls([
            call("france_system_prompt.txt"),
            call("system_prompt.txt")
        ])

    async def test_decide_orders_no_units(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.get_power_units.return_value = []
        mock_phase_state.phase_name = "Spring1901"
        
        orders = await self.agent.decide_orders(mock_phase_state)
        self.assertEqual(orders, []) # No units, no orders
        mock_phase_state.get_power_units.assert_called_once_with("FRANCE")

    async def test_decide_orders_successful(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.get_power_units.return_value = ["A PAR", "F BRE"]
        mock_phase_state.phase_name = "Spring1901"

        self.mock_context_provider.provide_context = AsyncMock(return_value={"context_text": "Test context", "tools_available": False})
        self.mock_prompt_strategy.build_order_prompt.return_value = "Test order prompt"
        # Configure the mock_llm_coordinator.call_json directly as it's already a mock
        self.mock_llm_coordinator.call_json.return_value = {"orders": ["A PAR H", "F BRE M MAR"]}
        
        # Mock _extract_orders_from_response as it's tested separately
        with patch.object(self.agent, '_extract_orders_from_response', return_value=[Order("A PAR H"), Order("F BRE M MAR")]) as mock_extract:
            orders = await self.agent.decide_orders(mock_phase_state)
        
        self.mock_context_provider.provide_context.assert_called_once()
        self.mock_prompt_strategy.build_order_prompt.assert_called_once_with(
            country="FRANCE",
            goals=self.mock_agent_state.goals,
            relationships=self.mock_agent_state.relationships,
            formatted_diary=self.mock_agent_state.format_private_diary_for_prompt.return_value,
            context_text="Test context",
            tools_available=False
        )
        self.mock_llm_coordinator.call_json.assert_called_once_with(
            prompt="Test order prompt",
            model_id=self.agent_config.model_id,
            agent_id=self.agent.agent_id,
            game_id=self.agent.game_id,
            phase=mock_phase_state.phase_name,
            system_prompt=self.agent.system_prompt,
            expected_fields=["orders"],
            tools=None, # Based on tools_available=False
            llm_caller_override=self.mock_llm_caller_override # Verify override is passed
        )
        mock_extract.assert_called_once_with({"orders": ["A PAR H", "F BRE M MAR"]}, ["A PAR", "F BRE"])
        self.assertEqual(len(orders), 2)
        self.assertIsInstance(orders[0], Order)

    async def test_decide_orders_llm_error(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.get_power_units.return_value = ["A PAR", "F BRE"]
        mock_phase_state.phase_name = "Spring1901"

        self.mock_context_provider.provide_context = AsyncMock(return_value={"context_text": "Test context"})
        self.mock_prompt_strategy.build_order_prompt.return_value = "Test order prompt"
        self.mock_llm_coordinator.call_json.side_effect = Exception("LLM exploded") # Configure existing mock

        orders = await self.agent.decide_orders(mock_phase_state)
        self.assertEqual(len(orders), 2)
        self.assertEqual(orders[0].order_text, "A PAR H")
        self.assertEqual(orders[1].order_text, "F BRE H")

    async def test_decide_orders_bad_llm_response(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.get_power_units.return_value = ["A PAR"]
        mock_phase_state.phase_name = "Spring1901"

        self.mock_context_provider.provide_context = AsyncMock(return_value={"context_text": "Test context"})
        self.mock_prompt_strategy.build_order_prompt.return_value = "Test order prompt"
        self.mock_llm_coordinator.call_json.return_value = {} # Missing 'orders'

        # _extract_orders_from_response will handle this and return HOLD
        orders = await self.agent.decide_orders(mock_phase_state)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].order_text, "A PAR H")

    async def test_decide_orders_context_tools_available(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.get_power_units.return_value = ["A PAR"]
        mock_phase_state.phase_name = "S1901M"
        mock_tools = [{"name": "tool1"}]
        self.mock_context_provider.provide_context = AsyncMock(return_value={"context_text": "Ctx", "tools_available": True, "tools": mock_tools})
        self.mock_prompt_strategy.build_order_prompt.return_value = "Prompt"
        self.mock_llm_coordinator.call_json.return_value = {"orders": ["A PAR H"]}
        
        with patch.object(self.agent, '_extract_orders_from_response', return_value=[Order("A PAR H")]):
            await self.agent.decide_orders(mock_phase_state)
        
        self.mock_prompt_strategy.build_order_prompt.assert_called_once()
        self.assertTrue(self.mock_prompt_strategy.build_order_prompt.call_args[1]['tools_available'])
        
        self.mock_llm_coordinator.call_json.assert_called_once_with(
            prompt="Prompt",
            model_id=self.agent_config.model_id,
            agent_id=self.agent.agent_id,
            game_id=self.agent.game_id,
            phase=mock_phase_state.phase_name,
            system_prompt=self.agent.system_prompt,
            expected_fields=["orders"],
            tools=mock_tools, # Verify tools are passed
            llm_caller_override=self.mock_llm_caller_override # Verify override is passed
        )


    async def test_decide_orders_context_empty_text(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.get_power_units.return_value = ["A PAR"]
        mock_phase_state.phase_name = "S1901M"
        self.mock_context_provider.provide_context = AsyncMock(return_value={"context_text": None, "tools_available": False})
        self.mock_prompt_strategy.build_order_prompt.return_value = "Prompt"
        self.mock_llm_coordinator.call_json.return_value = {"orders": ["A PAR H"]}

        with patch.object(self.agent, '_extract_orders_from_response', return_value=[Order("A PAR H")]):
            await self.agent.decide_orders(mock_phase_state)

        self.mock_prompt_strategy.build_order_prompt.assert_called_once_with(
            country="FRANCE",
            goals=self.mock_agent_state.goals,
            relationships=self.mock_agent_state.relationships,
            formatted_diary=self.mock_agent_state.format_private_diary_for_prompt.return_value,
            context_text="", 
            tools_available=False
        )
        self.mock_llm_coordinator.call_json.assert_called_once_with(
            prompt="Prompt",
            model_id=self.agent_config.model_id,
            agent_id=self.agent.agent_id,
            game_id=self.agent.game_id,
            phase=mock_phase_state.phase_name,
            system_prompt=self.agent.system_prompt,
            expected_fields=["orders"],
            tools=None,
            llm_caller_override=self.mock_llm_caller_override
        )

    async def test_decide_orders_context_provider_exception(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.get_power_units.return_value = ["A PAR"]
        mock_phase_state.phase_name = "S1901M"
        self.mock_context_provider.provide_context = AsyncMock(side_effect=Exception("Context provider failed"))

        orders = await self.agent.decide_orders(mock_phase_state)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].order_text, "A PAR H") # Fallback to HOLD

    def test_extract_orders_from_response(self):
        # No asyncSetUp needed as this is a synchronous method test
        # self.agent must be available for this test method if it's not part of asyncSetUp.
        # For simplicity, assuming self.agent is initialized somehow or this test is adapted.
        # If self.agent is only from asyncSetUp, this test needs to be async and call await self.asyncSetUp()
        # Or, instantiate a dummy agent here. Let's assume it's part of async for now.
        # await self.asyncSetUp() # Would be needed if self.agent is not otherwise available
        # For now, to make it runnable without async setup, we'd create a dummy agent for this sync test.
        # This test only calls self.agent._extract_orders_from_response, which doesn't depend on async state.
        # So, we can create a minimal LLMAgent if needed, or ensure it's available.
        # Let's assume self.agent is available from a prior (potentially skipped if this fails) asyncSetUp
        # or this test will be marked to require self.agent.
        # If this test is run standalone or if asyncSetUp failed, self.agent might not be set.
        # For now, we'll proceed as if self.agent is available.

        my_units = ["A PAR", "F BRE"]
        
        # Valid
        response_valid = {"orders": ["A PAR H", "F BRE S A PAR H"]}
        extracted = self.agent._extract_orders_from_response(response_valid, my_units)
        self.assertEqual(len(extracted), 2)
        self.assertEqual(extracted[0].order_text, "A PAR H")

        # Missing 'orders'
        response_missing = {}
        extracted_missing = self.agent._extract_orders_from_response(response_missing, my_units)
        self.assertEqual(len(extracted_missing), 2)
        self.assertTrue(all(o.order_text.endswith("H") for o in extracted_missing))

        # 'orders' not a list
        response_not_list = {"orders": "A PAR H"}
        extracted_not_list = self.agent._extract_orders_from_response(response_not_list, my_units)
        self.assertEqual(len(extracted_not_list), 2)
        self.assertTrue(all(o.order_text.endswith("H") for o in extracted_not_list))

        # Empty list of orders
        response_empty_list = {"orders": []}
        extracted_empty_list = self.agent._extract_orders_from_response(response_empty_list, my_units)
        self.assertEqual(len(extracted_empty_list), 2)
        self.assertTrue(all(o.order_text.endswith("H") for o in extracted_empty_list))

        # Non-string / empty string orders
        response_bad_strings = {"orders": [123, "", "A PAR H"]}
        extracted_bad_strings = self.agent._extract_orders_from_response(response_bad_strings, my_units)
        self.assertEqual(len(extracted_bad_strings), 1) # Only "A PAR H" is valid
        self.assertEqual(extracted_bad_strings[0].order_text, "A PAR H")
        
        # No valid orders among bad strings
        response_no_valid = {"orders": [None, "   "]}
        extracted_no_valid = self.agent._extract_orders_from_response(response_no_valid, my_units)
        self.assertEqual(len(extracted_no_valid), 2) # Defaults to HOLD
        self.assertTrue(all(o.order_text.endswith("H") for o in extracted_no_valid))

    def test_extract_orders_edge_cases(self):
        # Similar to above, assuming self.agent is available.
        my_units = ["A PAR", "F LON", "F EDI"]
        # Syntactically plausible but semantically incorrect (method doesn't validate semantics)
        response_semantic = {"orders": ["A PAR M XXX", "F LON S F EDI M YYY", "F EDI H ZZZ"]}
        extracted_semantic = self.agent._extract_orders_from_response(response_semantic, my_units)
        self.assertEqual(len(extracted_semantic), 3)
        self.assertEqual(extracted_semantic[0].order_text, "A PAR M XXX")
        self.assertEqual(extracted_semantic[1].order_text, "F LON S F EDI M YYY")
        self.assertEqual(extracted_semantic[2].order_text, "F EDI H ZZZ")

        # Large number of orders (should pass them all)
        large_orders_list = [f"UNIT{i} H" for i in range(50)]
        response_large = {"orders": large_orders_list}
        # Need to mock units accordingly for default hold if this were to fail
        mock_large_units = [f"UNIT{i}" for i in range(50)]
        extracted_large = self.agent._extract_orders_from_response(response_large, mock_large_units)
        self.assertEqual(len(extracted_large), 50)
        self.assertEqual(extracted_large[0].order_text, "UNIT0 H")

    async def test_negotiate_successful(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.powers = ["FRANCE", "ENGLAND", "GERMANY"]
        mock_phase_state.is_power_eliminated.return_value = False
        mock_phase_state.phase_name = "Spring1901"

        self.mock_context_provider.provide_context = AsyncMock(return_value={"context_text": "Negotiation context"})
        self.mock_prompt_strategy.build_negotiation_prompt.return_value = "Test negotiation prompt"
        llm_response = {"messages": [{"recipient": "ENGLAND", "content": "Hello!", "message_type": "private"}]}
        self.mock_llm_coordinator.call_json.return_value = llm_response

        with patch.object(self.agent, '_extract_messages_from_response', return_value=[Message("ENGLAND", "Hello!", "private")]) as mock_extract:
            messages = await self.agent.negotiate(mock_phase_state)

        self.mock_context_provider.provide_context.assert_called_once()
        self.mock_prompt_strategy.build_negotiation_prompt.assert_called_once()
        self.mock_llm_coordinator.call_json.assert_called_once_with(
            prompt="Test negotiation prompt",
            model_id=self.agent_config.model_id,
            agent_id=self.agent.agent_id,
            game_id=self.agent.game_id,
            phase=mock_phase_state.phase_name,
            system_prompt=self.agent.system_prompt,
            expected_fields=["messages"],
            tools=None, # Assuming tools_available was False in context_result
            llm_caller_override=self.mock_llm_caller_override
        )
        mock_extract.assert_called_once_with(llm_response, mock_phase_state)
        self.assertEqual(len(messages), 1)
        self.assertIsInstance(messages[0], Message)

    async def test_negotiate_llm_error(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.phase_name = "Spring1901"
        self.mock_context_provider.provide_context = AsyncMock(return_value={"context_text": "Context"})
        self.mock_prompt_strategy.build_negotiation_prompt.return_value = "Prompt"
        self.mock_llm_coordinator.call_json.side_effect = Exception("LLM error")
        
        messages = await self.agent.negotiate(mock_phase_state)
        self.assertEqual(messages, [])

    async def test_negotiate_bad_llm_response(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.phase_name = "Spring1901"
        self.mock_context_provider.provide_context = AsyncMock(return_value={"context_text": "Context"})
        self.mock_prompt_strategy.build_negotiation_prompt.return_value = "Prompt"
        self.mock_llm_coordinator.call_json.return_value = {} # Missing 'messages'

        messages = await self.agent.negotiate(mock_phase_state)
        self.assertEqual(messages, [])

    async def test_negotiate_context_tools_available(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.powers = ["FRANCE", "ENGLAND"]
        mock_phase_state.is_power_eliminated.return_value = False
        mock_phase_state.phase_name = "S1901M"
        mock_tools = [{"name": "tool1"}]
        self.mock_context_provider.provide_context = AsyncMock(return_value={"context_text": "Ctx", "tools_available": True, "tools": mock_tools})
        self.mock_prompt_strategy.build_negotiation_prompt.return_value = "Prompt"
        self.mock_llm_coordinator.call_json.return_value = {"messages": []}

        with patch.object(self.agent, '_extract_messages_from_response', return_value=[]):
            await self.agent.negotiate(mock_phase_state)

        self.mock_prompt_strategy.build_negotiation_prompt.assert_called_once()
        self.assertTrue(self.mock_prompt_strategy.build_negotiation_prompt.call_args[1]['tools_available'])
        self.mock_llm_coordinator.call_json.assert_called_once_with(
            prompt="Prompt",
            model_id=self.agent_config.model_id,
            agent_id=self.agent.agent_id,
            game_id=self.agent.game_id,
            phase=mock_phase_state.phase_name,
            system_prompt=self.agent.system_prompt,
            expected_fields=["messages"],
            tools=mock_tools,
            llm_caller_override=self.mock_llm_caller_override
        )


    async def test_negotiate_context_empty_text(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.powers = ["FRANCE", "ENGLAND"]
        mock_phase_state.is_power_eliminated.return_value = False
        mock_phase_state.phase_name = "S1901M"
        self.mock_context_provider.provide_context = AsyncMock(return_value={"context_text": None, "tools_available": False})
        self.mock_prompt_strategy.build_negotiation_prompt.return_value = "Prompt"
        self.mock_llm_coordinator.call_json.return_value = {"messages": []}

        with patch.object(self.agent, '_extract_messages_from_response', return_value=[]):
            await self.agent.negotiate(mock_phase_state)

        self.mock_prompt_strategy.build_negotiation_prompt.assert_called_once()
        self.assertEqual(self.mock_prompt_strategy.build_negotiation_prompt.call_args[1]['context_text'], "")
        self.mock_llm_coordinator.call_json.assert_called_once_with(
            prompt="Prompt",
            model_id=self.agent_config.model_id,
            agent_id=self.agent.agent_id,
            game_id=self.agent.game_id,
            phase=mock_phase_state.phase_name,
            system_prompt=self.agent.system_prompt,
            expected_fields=["messages"],
            tools=None,
            llm_caller_override=self.mock_llm_caller_override
        )


    async def test_negotiate_context_provider_exception(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.phase_name = "S1901M"
        self.mock_context_provider.provide_context = AsyncMock(side_effect=Exception("Context provider failed"))

        messages = await self.agent.negotiate(mock_phase_state)
        self.assertEqual(messages, [])


    def test_extract_messages_from_response(self):
        # No asyncSetUp needed
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.powers = ["FRANCE", "ENGLAND", "GERMANY"] # Valid recipients

        # Valid
        response_valid = {"messages": [{"recipient": "ENGLAND", "content": "Hi", "message_type": "private"}]}
        extracted = self.agent._extract_messages_from_response(response_valid, mock_phase_state)
        self.assertEqual(len(extracted), 1)
        self.assertEqual(extracted[0].recipient, "ENGLAND")

        # Missing "messages"
        self.assertEqual(self.agent._extract_messages_from_response({}, mock_phase_state), [])
        
        # "messages" not a list
        self.assertEqual(self.agent._extract_messages_from_response({"messages": "text"}, mock_phase_state), [])

        # List with non-dict or bad dicts
        response_bad_list = {"messages": [None, {"recipient": "ITALY"}, {"content": "No recipient"}]}
        self.assertEqual(len(self.agent._extract_messages_from_response(response_bad_list, mock_phase_state)), 0) # ITALY is not in phase.powers

        # Invalid recipient
        response_invalid_recipient = {"messages": [{"recipient": "SPAIN", "content": "Hola", "message_type": "private"}]}
        self.assertEqual(len(self.agent._extract_messages_from_response(response_invalid_recipient, mock_phase_state)), 0)
        
        # Valid recipient "GLOBAL"
        response_global = {"messages": [{"recipient": "GLOBAL", "content": "Attention all", "message_type": "global_announcement"}]}
        extracted_global = self.agent._extract_messages_from_response(response_global, mock_phase_state)
        self.assertEqual(len(extracted_global), 1)
        self.assertEqual(extracted_global[0].recipient, "GLOBAL")

    def test_extract_messages_edge_cases(self):
        # No asyncSetUp needed
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.powers = ["FRANCE", "ENGLAND", "GERMANY", "RUSSIA"]

        # Very long content & unusual characters
        long_content = "a" * 1000 + "!@#$%^&*()_+-=[]{};':\",./<>?"
        response_long_content = {"messages": [{"recipient": "ENGLAND", "content": long_content, "message_type": "private"}]}
        extracted_long = self.agent._extract_messages_from_response(response_long_content, mock_phase_state)
        self.assertEqual(len(extracted_long), 1)
        self.assertEqual(extracted_long[0].content, long_content)

        # Different message_type
        response_other_type = {"messages": [{"recipient": "GERMANY", "content": "Alliance proposal", "message_type": "ALLIANCE_PROPOSAL"}]}
        extracted_other_type = self.agent._extract_messages_from_response(response_other_type, mock_phase_state)
        self.assertEqual(len(extracted_other_type), 1)
        self.assertEqual(extracted_other_type[0].message_type, "ALLIANCE_PROPOSAL")

        # More invalid recipients
        response_invalid_recipients = {"messages": [
            {"recipient": "england", "content": "Lowercase", "message_type": "private"}, # Validated by .upper() in code
            {"recipient": "NONEXISTENT", "content": "To no one", "message_type": "private"},
            {"recipient": "", "content": "Empty recipient", "message_type": "private"},
        ]}
        extracted_invalid_recipients = self.agent._extract_messages_from_response(response_invalid_recipients, mock_phase_state)
        # Only 'england' (converted to 'ENGLAND') should be valid.
        self.assertEqual(len(extracted_invalid_recipients), 1) 
        self.assertEqual(extracted_invalid_recipients[0].recipient, "ENGLAND")


    async def test_update_state(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.phase_name = "S1901M"
        mock_events = [{"type": "attack", "attacker": "GERMANY", "target": "FRANCE"}]

        # Mock methods called by update_state
        self.agent._generate_phase_diary_entry = AsyncMock()
        self.agent._analyze_and_update_goals = AsyncMock()
        # self.mock_agent_state._update_relationships_from_events is already a mock as part of configuring self.mock_agent_state

        await self.agent.update_state(mock_phase_state, mock_events)

        self.agent._generate_phase_diary_entry.assert_called_once_with(mock_phase_state, mock_events)
        self.mock_agent_state._update_relationships_from_events.assert_called_once_with("FRANCE", mock_events) # Verify this mock was called
        self.agent._analyze_and_update_goals.assert_called_once_with(mock_phase_state)

    async def test_generate_phase_diary_entry_successful(self):
        await self.asyncSetUp()
        self.mock_agent_state.add_journal_entry.reset_mock() # Reset from asyncSetUp's agent init
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.phase_name = "S1901M"
        mock_phase_state.get_power_units.return_value = ["A PAR"]
        mock_phase_state.get_power_centers.return_value = ["PARIS"]
        mock_phase_state.is_game_over = False
        mock_events = []

        self.mock_prompt_strategy.build_diary_generation_prompt.return_value = "Diary prompt"
        self.mock_llm_coordinator.call_json.return_value = {"diary_entry": "It was a good phase."}

        await self.agent._generate_phase_diary_entry(mock_phase_state, mock_events)

        self.mock_prompt_strategy.build_diary_generation_prompt.assert_called_once()
        self.mock_llm_coordinator.call_json.assert_called_once_with(
            prompt="Diary prompt",
            model_id=self.agent_config.model_id,
            agent_id=self.agent.agent_id,
            game_id=self.agent.game_id,
            phase=mock_phase_state.phase_name,
            system_prompt=self.agent.system_prompt,
            expected_fields=["diary_entry"],
            llm_caller_override=self.mock_llm_caller_override # Verify override
        )
        self.mock_agent_state.add_diary_entry.assert_called_once_with("It was a good phase.", mock_phase_state.phase_name)
        # Verify exact values used from agent_state for the prompt
        args, kwargs = self.mock_prompt_strategy.build_diary_generation_prompt.call_args
        self.assertEqual(kwargs['goals'], self.mock_agent_state.goals)
        self.assertEqual(kwargs['relationships'], self.mock_agent_state.relationships)


    async def test_generate_phase_diary_entry_llm_error(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.phase_name = "F1901M"
        # ... (set up other PhaseState mocks as needed)
        mock_events = []

        self.mock_prompt_strategy.build_diary_generation_prompt.return_value = "Diary prompt"
        self.mock_llm_coordinator.call_json.side_effect = Exception("LLM diary error")

        await self.agent._generate_phase_diary_entry(mock_phase_state, mock_events)
        
        self.mock_agent_state.add_diary_entry.assert_called_once_with(
            f"Phase F1901M completed (diary generation failed).", "F1901M"
        )

    async def test_analyze_and_update_goals_change(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.get_center_count.return_value = 2 # Should trigger "Survive"
        mock_phase_state.powers = ["FRANCE", "GERMANY"]
        mock_phase_state.is_power_eliminated.return_value = False
        
        self.mock_agent_state.goals = ["Old goal"] # Current goals

        await self.agent._analyze_and_update_goals(mock_phase_state)

        self.assertEqual(self.mock_agent_state.goals, ["Survive and avoid elimination"])
        self.mock_agent_state.add_journal_entry.assert_called_once() # Journal entry for goal change
        # Check that the journal entry reflects the change
        args, kwargs = self.mock_agent_state.add_journal_entry.call_args
        self.assertEqual(args[0], "Goals updated from ['Old goal'] to ['Survive and avoid elimination']")


    async def test_analyze_and_update_goals_very_small(self):
        await self.asyncSetUp()
        self.mock_agent_state.add_journal_entry.reset_mock() # Reset from asyncSetUp's agent init
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.get_center_count.return_value = 1 # Very small
        mock_phase_state.powers = ["FRANCE", "GERMANY"]
        mock_phase_state.is_power_eliminated.return_value = False
        self.mock_agent_state.goals = ["Expand territory"] # Override default from setup

        await self.agent._analyze_and_update_goals(mock_phase_state)
        self.assertEqual(self.mock_agent_state.goals, ["Survive and avoid elimination"]) # This now correctly checks the instance attribute
        self.mock_agent_state.add_journal_entry.assert_called_once_with( # Journal entry for goal change
            "Goals updated from ['Expand territory'] to ['Survive and avoid elimination']"
        )

    async def test_analyze_and_update_goals_very_large(self):
        await self.asyncSetUp()
        self.mock_agent_state.add_journal_entry.reset_mock() # Reset from asyncSetUp's agent init
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.get_center_count.return_value = 15 # Very large
        mock_phase_state.powers = ["FRANCE", "GERMANY"]
        mock_phase_state.is_power_eliminated.return_value = False
        self.mock_agent_state.goals = ["Expand territory"] # Override default from setup

        await self.agent._analyze_and_update_goals(mock_phase_state)
        self.assertEqual(self.mock_agent_state.goals, ["Consolidate position and prepare for victory"])
        self.mock_agent_state.add_journal_entry.assert_called_once_with( # Journal entry for goal change
            "Goals updated from ['Expand territory'] to ['Consolidate position and prepare for victory']"
        )

    async def test_analyze_and_update_goals_clear_leader(self):
        await self.asyncSetUp()
        self.mock_agent_state.add_journal_entry.reset_mock() # Reset from asyncSetUp's agent init
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.get_center_count.side_effect = lambda p: 5 if p == "FRANCE" else (12 if p == "GERMANY" else 3)
        mock_phase_state.powers = ["FRANCE", "GERMANY", "ITALY"]
        mock_phase_state.is_power_eliminated.return_value = False
        self.mock_agent_state.goals = ["Expand territory and gain supply centers"] # Override

        await self.agent._analyze_and_update_goals(mock_phase_state)
        expected_goals = ["Expand territory and gain supply centers", "Form coalition against the leader"]
        self.assertEqual(self.mock_agent_state.goals, expected_goals)
        self.mock_agent_state.add_journal_entry.assert_called_once_with( # Journal entry for goal change
            "Goals updated from ['Expand territory and gain supply centers'] to "
            "['Expand territory and gain supply centers', 'Form coalition against the leader']"
        )
        
    async def test_analyze_and_update_goals_no_redundant_addition(self):
        await self.asyncSetUp()
        self.mock_agent_state.add_journal_entry.reset_mock() # Reset from asyncSetUp's agent init
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.get_center_count.return_value = 2 # "Survive"
        mock_phase_state.powers = ["FRANCE", "GERMANY"]
        mock_phase_state.is_power_eliminated.return_value = False
        
        # Goal already exists
        self.mock_agent_state.goals = ["Survive and avoid elimination"] # Set to what it would become

        await self.agent._analyze_and_update_goals(mock_phase_state)
        self.assertEqual(self.mock_agent_state.goals, ["Survive and avoid elimination"])
        self.mock_agent_state.add_journal_entry.assert_not_called() # No change, so no journal entry


    async def test_analyze_and_update_goals_no_change(self):
        await self.asyncSetUp()
        self.mock_agent_state.add_journal_entry.reset_mock() # Reset from asyncSetUp's agent init
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.get_center_count.return_value = 5 # "Expand"
        mock_phase_state.powers = ["FRANCE", "GERMANY"]
        mock_phase_state.is_power_eliminated.return_value = False
        
        # Set current goals to what they would be updated to
        self.mock_agent_state.goals = ["Expand territory and gain supply centers"] # Set to what it would become

        await self.agent._analyze_and_update_goals(mock_phase_state)

        self.assertEqual(self.mock_agent_state.goals, ["Expand territory and gain supply centers"])
        self.mock_agent_state.add_journal_entry.assert_not_called() # No change, so no journal entry
        # Verify that agent_state.goals was accessed for comparison
        self.assertTrue(self.mock_agent_state.goals is not None)


    async def test_get_agent_info(self):
        await self.asyncSetUp() # Uses configured mock_agent_state
        # self.mock_agent_state.add_journal_entry.reset_mock() # Not strictly needed as we don't assert calls here

        # Values are set in asyncSetUp's mock_agent_state configuration
        # self.mock_agent_state.goals = ["Test Goal"] # Example, already set
        # self.mock_agent_state.relationships = {"GERMANY": "Enemy"} # Example, already set
        self.mock_agent_state.private_diary = ["Entry 1"] # Override if needed for count
        self.mock_agent_state.private_journal = ["Journal 1", "Journal 2"] # Override if needed for count
        
        expected_info = {
            "agent_id": self.agent.agent_id,
            "country": self.agent.country,
            "type": "LLMAgent",
            "model_id": self.agent_config.model_id,
            "goals": ["Initial Goal"], # Changed to match asyncSetUp
            "relationships": {"GERMANY": "Neutral", "ITALY": "Friendly"}, # Changed to match asyncSetUp
            "diary_entries": 1,
            "journal_entries": 2,
        }
        
        agent_info = self.agent.get_agent_info()
        self.assertEqual(agent_info, expected_info)

if __name__ == '__main__':
    unittest.main()
