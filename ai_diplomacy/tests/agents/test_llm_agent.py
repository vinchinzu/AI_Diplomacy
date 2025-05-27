import unittest
from unittest.mock import MagicMock, AsyncMock, patch, call
from typing import List, Dict, Any, Optional

from ai_diplomacy.agents.llm_agent import LLMAgent
from ai_diplomacy.agents.base import Order, Message, PhaseState
from ai_diplomacy.agents.agent_state import DiplomacyAgentState
from ai_diplomacy.agents.llm_prompt_strategy import LLMPromptStrategy
from ai_diplomacy.services.llm_coordinator import LLMCoordinator
from ai_diplomacy.services.config import AgentConfig, ContextProviderType
from ai_diplomacy.services.context_provider import ContextProviderFactory, BaseContextProvider, ContextData


class TestLLMAgent(unittest.IsolatedAsyncioTestCase):

    @patch('ai_diplomacy.agents.llm_agent.llm_utils.load_prompt_file') # Corrected patch target
    @patch('ai_diplomacy.agents.llm_agent.ContextProviderFactory')
    @patch('ai_diplomacy.agents.llm_agent.LLMCoordinator')
    @patch('ai_diplomacy.agents.llm_agent.LLMPromptStrategy')
    @patch('ai_diplomacy.agents.llm_agent.DiplomacyAgentState')
    async def asyncSetUp(self, MockDiplomacyAgentState, MockLLMPromptStrategy, MockLLMCoordinator, MockContextProviderFactory, mock_load_prompt_file):
        # Store mocks for later use in tests
        self.MockDiplomacyAgentState = MockDiplomacyAgentState
        self.MockLLMPromptStrategy = MockLLMPromptStrategy
        self.MockLLMCoordinator = MockLLMCoordinator
        self.MockContextProviderFactory = MockContextProviderFactory
        self.mock_load_prompt_file = mock_load_prompt_file

        self.mock_agent_state = MockDiplomacyAgentState.return_value
        self.mock_prompt_strategy = MockLLMPromptStrategy.return_value
        self.mock_llm_coordinator = MockLLMCoordinator.return_value
        self.mock_context_provider_factory = MockContextProviderFactory.return_value
        
        self.mock_context_provider = AsyncMock(spec=BaseContextProvider)
        self.mock_context_provider.get_provider_type.return_value = ContextProviderType.DEFAULT
        self.mock_context_provider_factory.get_provider.return_value = self.mock_context_provider
        
        self.mock_load_prompt_file.return_value = "Default system prompt"

        self.agent_config = AgentConfig(
            agent_id="test_agent",
            power="FRANCE",
            model_id="test_model",
            context_provider_type="DEFAULT",
            log_to_gcp=False,
            log_to_file=False
        )
        
        self.agent = LLMAgent(
            agent_id="test_agent_007",
            country="FRANCE",
            config=self.agent_config,
            game_id="test_game",
            llm_coordinator=self.mock_llm_coordinator, # Pass the instance
            context_provider_factory=self.mock_context_provider_factory # Pass the instance
        )

    async def test_initialization(self):
        await self.asyncSetUp() # Call asyncSetUp manually for tests

        self.MockDiplomacyAgentState.assert_called_once_with(country="FRANCE")
        self.MockLLMPromptStrategy.assert_called_once()
        
        # Check if LLMCoordinator was used (if passed) or instantiated
        # In asyncSetUp, we pass an instance, so it should not be called to create a new one.
        # If we had passed None, then self.MockLLMCoordinator would have been called.
        # self.MockLLMCoordinator.assert_not_called() # This depends on how we structure the test if we want to test internal instantiation
        self.assertEqual(self.agent.llm_coordinator, self.mock_llm_coordinator)


        self.MockContextProviderFactory.assert_called_once()
        self.mock_context_provider_factory.get_provider.assert_called_once_with(ContextProviderType.DEFAULT)
        self.assertEqual(self.agent.context_provider, self.mock_context_provider)
        
        self.mock_agent_state.add_journal_entry.assert_called_once_with(
            f"Agent initialized with model {self.agent_config.model_id}, context provider: {ContextProviderType.DEFAULT}"
        )
        self.mock_load_prompt_file.assert_called_with("system_prompt.txt") # Default fallback

    async def test_load_system_prompt_power_specific(self):
        await self.asyncSetUp()
        self.mock_load_prompt_file.reset_mock()
        
        # Power-specific succeeds
        self.mock_load_prompt_file.side_effect = ["Power-specific prompt", "Default prompt"]
        prompt = self.agent._load_system_prompt()
        self.assertEqual(prompt, "Power-specific prompt")
        self.mock_load_prompt_file.assert_any_call("france_system_prompt.txt")
        # It shouldn't call for default if power-specific is found
        self.assertFalse(any(c == call('system_prompt.txt') for c in self.mock_load_prompt_file.call_args_list))


    async def test_load_system_prompt_default(self):
        await self.asyncSetUp()
        self.mock_load_prompt_file.reset_mock()

        # Power-specific fails, default succeeds
        self.mock_load_prompt_file.side_effect = [None, "Default prompt"]
        prompt = self.agent._load_system_prompt()
        self.assertEqual(prompt, "Default prompt")
        self.mock_load_prompt_file.assert_has_calls([
            call("france_system_prompt.txt"),
            call("system_prompt.txt")
        ])

    async def test_load_system_prompt_failure(self):
        await self.asyncSetUp()
        self.mock_load_prompt_file.reset_mock()
        
        self.mock_load_prompt_file.side_effect = [None, None] # Both fail
        prompt = self.agent._load_system_prompt()
        self.assertIsNone(prompt)
        self.mock_load_prompt_file.assert_has_calls([
            call("france_system_prompt.txt"),
            call("system_prompt.txt")
        ])

    async def test_decide_orders_no_units(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.get_power_units.return_value = []
        mock_phase_state.phase_name = "Spring1901"
        
        orders = await self.agent.decide_orders(mock_phase_state)
        self.assertEqual(orders, [])
        mock_phase_state.get_power_units.assert_called_once_with("FRANCE")

    async def test_decide_orders_successful(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.get_power_units.return_value = ["A PAR", "F BRE"]
        mock_phase_state.phase_name = "Spring1901"

        self.mock_context_provider.provide_context = AsyncMock(return_value={"context_text": "Test context", "tools_available": False})
        self.mock_prompt_strategy.build_order_prompt.return_value = "Test order prompt"
        self.mock_llm_coordinator.call_json = AsyncMock(return_value={"orders": ["A PAR H", "F BRE M MAR"]})
        
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
        self.mock_llm_coordinator.call_json.assert_called_once()
        mock_extract.assert_called_once_with({"orders": ["A PAR H", "F BRE M MAR"]}, ["A PAR", "F BRE"])
        self.assertEqual(len(orders), 2)
        self.assertIsInstance(orders[0], Order)

    async def test_decide_orders_llm_error(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.get_power_units.return_value = ["A PAR", "F BRE"]
        mock_phase_state.phase_name = "Spring1901"

        self.mock_context_provider.provide_context = AsyncMock(return_value={"context_text": "Test context"})
        self.mock_prompt_strategy.build_order_prompt.return_value = "Test order prompt"
        self.mock_llm_coordinator.call_json = AsyncMock(side_effect=Exception("LLM exploded"))

        orders = await self.agent.decide_orders(mock_phase_state)
        self.assertEqual(len(orders), 2)
        self.assertEqual(orders[0].order, "A PAR H")
        self.assertEqual(orders[1].order, "F BRE H")

    async def test_decide_orders_bad_llm_response(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.get_power_units.return_value = ["A PAR"]
        mock_phase_state.phase_name = "Spring1901"

        self.mock_context_provider.provide_context = AsyncMock(return_value={"context_text": "Test context"})
        self.mock_prompt_strategy.build_order_prompt.return_value = "Test order prompt"
        self.mock_llm_coordinator.call_json = AsyncMock(return_value={}) # Missing 'orders'

        # _extract_orders_from_response will handle this and return HOLD
        orders = await self.agent.decide_orders(mock_phase_state)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].order, "A PAR H")

    async def test_decide_orders_context_tools_available(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.get_power_units.return_value = ["A PAR"]
        mock_phase_state.phase_name = "S1901M"
        self.mock_context_provider.provide_context = AsyncMock(return_value={"context_text": "Ctx", "tools_available": True, "tools": [{"name": "tool1"}]})
        self.mock_prompt_strategy.build_order_prompt.return_value = "Prompt"
        self.mock_llm_coordinator.call_json = AsyncMock(return_value={"orders": ["A PAR H"]})
        
        with patch.object(self.agent, '_extract_orders_from_response', return_value=[Order("A PAR H")]):
            await self.agent.decide_orders(mock_phase_state)
        
        self.mock_prompt_strategy.build_order_prompt.assert_called_once()
        self.assertTrue(self.mock_prompt_strategy.build_order_prompt.call_args[1]['tools_available'])
        self.mock_llm_coordinator.call_json.assert_called_once()
        self.assertIsNotNone(self.mock_llm_coordinator.call_json.call_args[1]['tools'])


    async def test_decide_orders_context_empty_text(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.get_power_units.return_value = ["A PAR"]
        mock_phase_state.phase_name = "S1901M"
        self.mock_context_provider.provide_context = AsyncMock(return_value={"context_text": None, "tools_available": False})
        self.mock_prompt_strategy.build_order_prompt.return_value = "Prompt"
        self.mock_llm_coordinator.call_json = AsyncMock(return_value={"orders": ["A PAR H"]})

        with patch.object(self.agent, '_extract_orders_from_response', return_value=[Order("A PAR H")]):
            await self.agent.decide_orders(mock_phase_state)

        self.mock_prompt_strategy.build_order_prompt.assert_called_once_with(
            country="FRANCE",
            goals=self.mock_agent_state.goals,
            relationships=self.mock_agent_state.relationships,
            formatted_diary=self.mock_agent_state.format_private_diary_for_prompt.return_value,
            context_text="", # Expect empty string if None
            tools_available=False
        )

    async def test_decide_orders_context_provider_exception(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.get_power_units.return_value = ["A PAR"]
        mock_phase_state.phase_name = "S1901M"
        self.mock_context_provider.provide_context = AsyncMock(side_effect=Exception("Context provider failed"))

        orders = await self.agent.decide_orders(mock_phase_state)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].order, "A PAR H") # Fallback to HOLD

    def test_extract_orders_from_response(self):
        # No asyncSetUp needed as this is a synchronous method test
        my_units = ["A PAR", "F BRE"]
        
        # Valid
        response_valid = {"orders": ["A PAR H", "F BRE S A PAR H"]}
        extracted = self.agent._extract_orders_from_response(response_valid, my_units)
        self.assertEqual(len(extracted), 2)
        self.assertEqual(extracted[0].order, "A PAR H")

        # Missing 'orders'
        response_missing = {}
        extracted_missing = self.agent._extract_orders_from_response(response_missing, my_units)
        self.assertEqual(len(extracted_missing), 2)
        self.assertTrue(all(o.order.endswith("H") for o in extracted_missing))

        # 'orders' not a list
        response_not_list = {"orders": "A PAR H"}
        extracted_not_list = self.agent._extract_orders_from_response(response_not_list, my_units)
        self.assertEqual(len(extracted_not_list), 2)
        self.assertTrue(all(o.order.endswith("H") for o in extracted_not_list))

        # Empty list of orders
        response_empty_list = {"orders": []}
        extracted_empty_list = self.agent._extract_orders_from_response(response_empty_list, my_units)
        self.assertEqual(len(extracted_empty_list), 2)
        self.assertTrue(all(o.order.endswith("H") for o in extracted_empty_list))

        # Non-string / empty string orders
        response_bad_strings = {"orders": [123, "", "A PAR H"]}
        extracted_bad_strings = self.agent._extract_orders_from_response(response_bad_strings, my_units)
        self.assertEqual(len(extracted_bad_strings), 1) # Only "A PAR H" is valid
        self.assertEqual(extracted_bad_strings[0].order, "A PAR H")
        
        # No valid orders among bad strings
        response_no_valid = {"orders": [None, "   "]}
        extracted_no_valid = self.agent._extract_orders_from_response(response_no_valid, my_units)
        self.assertEqual(len(extracted_no_valid), 2) # Defaults to HOLD
        self.assertTrue(all(o.order.endswith("H") for o in extracted_no_valid))

    def test_extract_orders_edge_cases(self):
        # No asyncSetUp needed
        my_units = ["A PAR", "F LON", "F EDI"]
        # Syntactically plausible but semantically incorrect (method doesn't validate semantics)
        response_semantic = {"orders": ["A PAR M XXX", "F LON S F EDI M YYY", "F EDI H ZZZ"]}
        extracted_semantic = self.agent._extract_orders_from_response(response_semantic, my_units)
        self.assertEqual(len(extracted_semantic), 3)
        self.assertEqual(extracted_semantic[0].order, "A PAR M XXX")
        self.assertEqual(extracted_semantic[1].order, "F LON S F EDI M YYY")
        self.assertEqual(extracted_semantic[2].order, "F EDI H ZZZ")

        # Large number of orders (should pass them all)
        large_orders_list = [f"UNIT{i} H" for i in range(50)]
        response_large = {"orders": large_orders_list}
        # Need to mock units accordingly for default hold if this were to fail
        mock_large_units = [f"UNIT{i}" for i in range(50)]
        extracted_large = self.agent._extract_orders_from_response(response_large, mock_large_units)
        self.assertEqual(len(extracted_large), 50)
        self.assertEqual(extracted_large[0].order, "UNIT0 H")

    async def test_negotiate_successful(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.powers = ["FRANCE", "ENGLAND", "GERMANY"]
        mock_phase_state.is_power_eliminated.return_value = False
        mock_phase_state.phase_name = "Spring1901"

        self.mock_context_provider.provide_context = AsyncMock(return_value={"context_text": "Negotiation context"})
        self.mock_prompt_strategy.build_negotiation_prompt.return_value = "Test negotiation prompt"
        llm_response = {"messages": [{"recipient": "ENGLAND", "content": "Hello!", "message_type": "private"}]}
        self.mock_llm_coordinator.call_json = AsyncMock(return_value=llm_response)

        with patch.object(self.agent, '_extract_messages_from_response', return_value=[Message("ENGLAND", "Hello!", "private")]) as mock_extract:
            messages = await self.agent.negotiate(mock_phase_state)

        self.mock_context_provider.provide_context.assert_called_once()
        self.mock_prompt_strategy.build_negotiation_prompt.assert_called_once()
        self.mock_llm_coordinator.call_json.assert_called_once()
        mock_extract.assert_called_once_with(llm_response, mock_phase_state)
        self.assertEqual(len(messages), 1)
        self.assertIsInstance(messages[0], Message)

    async def test_negotiate_llm_error(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.phase_name = "Spring1901"
        self.mock_context_provider.provide_context = AsyncMock(return_value={"context_text": "Context"})
        self.mock_prompt_strategy.build_negotiation_prompt.return_value = "Prompt"
        self.mock_llm_coordinator.call_json = AsyncMock(side_effect=Exception("LLM error"))
        
        messages = await self.agent.negotiate(mock_phase_state)
        self.assertEqual(messages, [])

    async def test_negotiate_bad_llm_response(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.phase_name = "Spring1901"
        self.mock_context_provider.provide_context = AsyncMock(return_value={"context_text": "Context"})
        self.mock_prompt_strategy.build_negotiation_prompt.return_value = "Prompt"
        self.mock_llm_coordinator.call_json = AsyncMock(return_value={}) # Missing 'messages'

        messages = await self.agent.negotiate(mock_phase_state)
        self.assertEqual(messages, [])

    async def test_negotiate_context_tools_available(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.powers = ["FRANCE", "ENGLAND"]
        mock_phase_state.is_power_eliminated.return_value = False
        mock_phase_state.phase_name = "S1901M"

        self.mock_context_provider.provide_context = AsyncMock(return_value={"context_text": "Ctx", "tools_available": True, "tools": [{"name": "tool1"}]})
        self.mock_prompt_strategy.build_negotiation_prompt.return_value = "Prompt"
        self.mock_llm_coordinator.call_json = AsyncMock(return_value={"messages": []})

        with patch.object(self.agent, '_extract_messages_from_response', return_value=[]):
            await self.agent.negotiate(mock_phase_state)

        self.mock_prompt_strategy.build_negotiation_prompt.assert_called_once()
        self.assertTrue(self.mock_prompt_strategy.build_negotiation_prompt.call_args[1]['tools_available'])
        self.mock_llm_coordinator.call_json.assert_called_once()
        self.assertIsNotNone(self.mock_llm_coordinator.call_json.call_args[1]['tools'])


    async def test_negotiate_context_empty_text(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.powers = ["FRANCE", "ENGLAND"]
        mock_phase_state.is_power_eliminated.return_value = False
        mock_phase_state.phase_name = "S1901M"
        self.mock_context_provider.provide_context = AsyncMock(return_value={"context_text": None, "tools_available": False})
        self.mock_prompt_strategy.build_negotiation_prompt.return_value = "Prompt"
        self.mock_llm_coordinator.call_json = AsyncMock(return_value={"messages": []})

        with patch.object(self.agent, '_extract_messages_from_response', return_value=[]):
            await self.agent.negotiate(mock_phase_state)

        self.mock_prompt_strategy.build_negotiation_prompt.assert_called_once()
        self.assertEqual(self.mock_prompt_strategy.build_negotiation_prompt.call_args[1]['context_text'], "")


    async def test_negotiate_context_provider_exception(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.phase_name = "S1901M"
        self.mock_context_provider.provide_context = AsyncMock(side_effect=Exception("Context provider failed"))

        messages = await self.agent.negotiate(mock_phase_state)
        self.assertEqual(messages, [])


    def test_extract_messages_from_response(self):
        # No asyncSetUp needed
        mock_phase_state = MagicMock(spec=PhaseState)
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
        mock_phase_state = MagicMock(spec=PhaseState)
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
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.phase_name = "S1901M"
        mock_events = [{"type": "attack", "attacker": "GERMANY", "target": "FRANCE"}]

        # Mock methods called by update_state
        self.agent._generate_phase_diary_entry = AsyncMock()
        self.agent._analyze_and_update_goals = AsyncMock()
        # self.mock_agent_state._update_relationships_from_events is already a mock

        await self.agent.update_state(mock_phase_state, mock_events)

        self.agent._generate_phase_diary_entry.assert_called_once_with(mock_phase_state, mock_events)
        self.mock_agent_state._update_relationships_from_events.assert_called_once_with("FRANCE", mock_events)
        self.agent._analyze_and_update_goals.assert_called_once_with(mock_phase_state)

    async def test_generate_phase_diary_entry_successful(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.phase_name = "S1901M"
        mock_phase_state.get_power_units.return_value = ["A PAR"]
        mock_phase_state.get_power_centers.return_value = ["PARIS"]
        mock_phase_state.is_game_over = False
        mock_events = []

        self.mock_prompt_strategy.build_diary_generation_prompt.return_value = "Diary prompt"
        self.mock_llm_coordinator.call_json = AsyncMock(return_value={"diary_entry": "It was a good phase."})

        await self.agent._generate_phase_diary_entry(mock_phase_state, mock_events)

        self.mock_prompt_strategy.build_diary_generation_prompt.assert_called_once()
        self.mock_llm_coordinator.call_json.assert_called_once_with(
            prompt="Diary prompt",
            model_id=self.agent_config.model_id,
            agent_id=self.agent.agent_id,
            game_id=self.agent.game_id,
            phase=mock_phase_state.phase_name,
            system_prompt=self.agent.system_prompt,
            expected_fields=["diary_entry"]
        )
        self.mock_agent_state.add_diary_entry.assert_called_once_with("It was a good phase.", mock_phase_state.phase_name)
        # Verify exact values used from agent_state for the prompt
        args, kwargs = self.mock_prompt_strategy.build_diary_generation_prompt.call_args
        self.assertEqual(kwargs['goals'], self.mock_agent_state.goals)
        self.assertEqual(kwargs['relationships'], self.mock_agent_state.relationships)


    async def test_generate_phase_diary_entry_llm_error(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.phase_name = "F1901M"
        # ... (set up other PhaseState mocks as needed)
        mock_events = []

        self.mock_prompt_strategy.build_diary_generation_prompt.return_value = "Diary prompt"
        self.mock_llm_coordinator.call_json = AsyncMock(side_effect=Exception("LLM diary error"))

        await self.agent._generate_phase_diary_entry(mock_phase_state, mock_events)
        
        self.mock_agent_state.add_diary_entry.assert_called_once_with(
            f"Phase F1901M completed (diary generation failed).", "F1901M"
        )

    async def test_analyze_and_update_goals_change(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.get_center_count.return_value = 2 # Should trigger "Survive"
        mock_phase_state.powers = ["FRANCE", "GERMANY"]
        mock_phase_state.is_power_eliminated.return_value = False
        
        self.mock_agent_state.goals = ["Old goal"] # Current goals

        await self.agent._analyze_and_update_goals(mock_phase_state)

        self.assertEqual(self.mock_agent_state.goals, ["Survive and avoid elimination"])
        self.mock_agent_state.add_journal_entry.assert_called_once()
        # Check that the journal entry reflects the change
        args, kwargs = self.mock_agent_state.add_journal_entry.call_args
        self.assertEqual(args[0], "Goals updated from ['Old goal'] to ['Survive and avoid elimination']")


    async def test_analyze_and_update_goals_very_small(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.get_center_count.return_value = 1 # Very small
        mock_phase_state.powers = ["FRANCE", "GERMANY"]
        mock_phase_state.is_power_eliminated.return_value = False
        self.mock_agent_state.goals = ["Expand territory"]
        self.mock_agent_state.add_journal_entry.reset_mock()

        await self.agent._analyze_and_update_goals(mock_phase_state)
        self.assertEqual(self.mock_agent_state.goals, ["Survive and avoid elimination"])
        self.mock_agent_state.add_journal_entry.assert_called_once_with(
            "Goals updated from ['Expand territory'] to ['Survive and avoid elimination']"
        )

    async def test_analyze_and_update_goals_very_large(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.get_center_count.return_value = 15 # Very large
        mock_phase_state.powers = ["FRANCE", "GERMANY"]
        mock_phase_state.is_power_eliminated.return_value = False
        self.mock_agent_state.goals = ["Expand territory"]
        self.mock_agent_state.add_journal_entry.reset_mock()

        await self.agent._analyze_and_update_goals(mock_phase_state)
        self.assertEqual(self.mock_agent_state.goals, ["Consolidate position and prepare for victory"])
        self.mock_agent_state.add_journal_entry.assert_called_once_with(
            "Goals updated from ['Expand territory'] to ['Consolidate position and prepare for victory']"
        )

    async def test_analyze_and_update_goals_clear_leader(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.get_center_count.side_effect = lambda p: 5 if p == "FRANCE" else (12 if p == "GERMANY" else 3)
        mock_phase_state.powers = ["FRANCE", "GERMANY", "ITALY"]
        mock_phase_state.is_power_eliminated.return_value = False
        self.mock_agent_state.goals = ["Expand territory and gain supply centers"]
        self.mock_agent_state.add_journal_entry.reset_mock()

        await self.agent._analyze_and_update_goals(mock_phase_state)
        expected_goals = ["Expand territory and gain supply centers", "Form coalition against the leader"]
        self.assertEqual(self.mock_agent_state.goals, expected_goals)
        self.mock_agent_state.add_journal_entry.assert_called_once_with(
            "Goals updated from ['Expand territory and gain supply centers'] to "
            "['Expand territory and gain supply centers', 'Form coalition against the leader']"
        )
        
    async def test_analyze_and_update_goals_no_redundant_addition(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.get_center_count.return_value = 2 # "Survive"
        mock_phase_state.powers = ["FRANCE", "GERMANY"]
        mock_phase_state.is_power_eliminated.return_value = False
        
        # Goal already exists
        self.mock_agent_state.goals = ["Survive and avoid elimination"]
        self.mock_agent_state.add_journal_entry.reset_mock()

        await self.agent._analyze_and_update_goals(mock_phase_state)
        self.assertEqual(self.mock_agent_state.goals, ["Survive and avoid elimination"])
        self.mock_agent_state.add_journal_entry.assert_not_called()


    async def test_analyze_and_update_goals_no_change(self):
        await self.asyncSetUp()
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.get_center_count.return_value = 5 # "Expand"
        mock_phase_state.powers = ["FRANCE", "GERMANY"]
        mock_phase_state.is_power_eliminated.return_value = False
        
        # Set current goals to what they would be updated to
        self.mock_agent_state.goals = ["Expand territory and gain supply centers"]
        self.mock_agent_state.add_journal_entry.reset_mock() # Reset from init

        await self.agent._analyze_and_update_goals(mock_phase_state)

        self.assertEqual(self.mock_agent_state.goals, ["Expand territory and gain supply centers"])
        self.mock_agent_state.add_journal_entry.assert_not_called()
        # Verify that agent_state.goals was accessed for comparison
        self.assertTrue(self.mock_agent_state.goals is not None)


    async def test_get_agent_info(self):
        await self.asyncSetUp()
        # Setup specific values on the mock_agent_state
        self.mock_agent_state.goals = ["Test Goal"]
        self.mock_agent_state.relationships = {"GERMANY": "Enemy"}
        self.mock_agent_state.private_diary = ["Entry 1"]
        self.mock_agent_state.private_journal = ["Journal 1", "Journal 2"]
        
        expected_info = {
            "agent_id": self.agent.agent_id,
            "country": self.agent.country,
            "type": "LLMAgent",
            "model_id": self.agent_config.model_id,
            "goals": ["Test Goal"],
            "relationships": {"GERMANY": "Enemy"},
            "diary_entries": 1,
            "journal_entries": 2,
        }
        
        agent_info = self.agent.get_agent_info()
        self.assertEqual(agent_info, expected_info)

if __name__ == '__main__':
    unittest.main()
