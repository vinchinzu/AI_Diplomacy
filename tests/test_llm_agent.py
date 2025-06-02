import unittest
from typing import Callable, Optional
from unittest.mock import AsyncMock, MagicMock, call, patch

from ai_diplomacy import constants
from ai_diplomacy.agents.base import Message, Order, PhaseState
from ai_diplomacy.agents.factory import AgentFactory
from ai_diplomacy.agents.llm_agent import LLMAgent
from ai_diplomacy.llm_utils import load_prompt_file
from ai_diplomacy.services.config import AgentConfig
from ai_diplomacy.services.context_provider import ContextProvider


class TestLLMAgent(unittest.IsolatedAsyncioTestCase):
    def _create_mock_prompt_loader(self) -> Callable[[str], Optional[str]]:
        # Helper to create a new mock loader for each test if needed, or use a shared one
        return MagicMock(spec=Callable[[str], Optional[str]])

    @patch("ai_diplomacy.agents.llm_agent.ContextProviderFactory", autospec=True)
    @patch("ai_diplomacy.agents.llm_agent.LLMCoordinator", autospec=True)
    @patch("ai_diplomacy.agents.llm_agent.LLMPromptStrategy", autospec=True)
    @patch("ai_diplomacy.agents.llm_agent.DiplomacyAgentState", autospec=True)
    async def asyncSetUp(
        self,
        MockDiplomacyAgentState,
        MockLLMPromptStrategy,
        MockLLMCoordinator,
        MockContextProviderFactory,
    ):
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
        self.mock_agent_state.relationships = {
            "GERMANY": "Neutral",
            "ITALY": "Friendly",
        }
        self.mock_agent_state.format_private_diary_for_prompt = MagicMock(
            return_value="Formatted diary from mock"
        )
        self.mock_agent_state._update_relationships_from_events = (
            MagicMock()
        )  # If this method is called on the mock
        self.mock_agent_state.private_diary = []  # Initialize as empty list
        self.mock_agent_state.private_journal = []  # Initialize as empty list

        self.mock_context_provider = AsyncMock(
            spec=ContextProvider, autospec=True
        )  # Changed BaseContextProvider to ContextProvider
        self.mock_context_provider.get_provider_type.return_value = (
            "inline"  # Changed to string
        )
        self.mock_context_provider.provide_context = AsyncMock(
            return_value={
                "context_text": "Default context",
                "tools_available": False,
                "provider_type": "inline",
                "tools": [],
            }
        )  # Added provider_type and tools
        self.mock_context_provider_factory.get_provider.return_value = (
            self.mock_context_provider
        )

        self.mock_llm_caller_override = AsyncMock(
            return_value={"orders": ["A PAR H"]}
        )  # Changed to return dict

        self.mock_prompt_loader = self._create_mock_prompt_loader()
        self.mock_prompt_loader.return_value = "Default system prompt from loader"

        self.mock_agent_state.add_journal_entry.reset_mock()  # New position

        self.agent_config = AgentConfig(
            country="FRANCE",
            type="llm",
            model_id="test_model",
            context_provider="inline",
        )

        self.agent = LLMAgent(
            agent_id="test_agent_007",  # agent_id is used here
            country="FRANCE",
            config=self.agent_config,
            game_id="test_game",
            llm_coordinator=self.mock_llm_coordinator,
            context_provider_factory=self.mock_context_provider_factory,
            prompt_loader=self.mock_prompt_loader,
            llm_caller_override=None,  # Override typically set per test or not at all for most
        )
        self.agent.llm_caller_override = (
            self.mock_llm_caller_override
        )  # Assign after agent init for specific tests

    async def test_initialization(self):
        # Re-init agent without override for this specific test to avoid interference
        agent = LLMAgent(
            agent_id="test_agent_init",
            country="FRANCE",
            config=self.agent_config,
            game_id="test_game_init",
            llm_coordinator=self.mock_llm_coordinator,
            context_provider_factory=self.mock_context_provider_factory,
            prompt_loader=self.mock_prompt_loader,
            llm_caller_override=None,
        )
        self.MockDiplomacyAgentState.assert_called_with(country="FRANCE")
        self.MockLLMPromptStrategy.assert_called_once()
        self.assertEqual(agent.llm_coordinator, self.mock_llm_coordinator)
        self.mock_context_provider_factory.get_provider.assert_called_with("inline")
        self.assertEqual(agent.context_provider, self.mock_context_provider)
        self.mock_agent_state.add_journal_entry.assert_any_call(  # any_call due to multiple inits
            f"Agent initialized with model {self.agent_config.model_id}, context provider: inline"
        )
        self.mock_prompt_loader.assert_any_call("france_system_prompt.txt")
        found_default_call = False
        for c in self.mock_prompt_loader.call_args_list:
            if (
                c == call("system_prompt.txt")
                and self.mock_prompt_loader("france_system_prompt.txt") is None
            ):
                found_default_call = True
                break
        # This assertion depends on whether france_system_prompt.txt mock returns something.
        # If it returns the default prompt, then the default specific call should not happen.
        if self.mock_prompt_loader("france_system_prompt.txt") is not None:
            self.assertFalse(
                found_default_call,
                "Default prompt should not have been loaded if power-specific succeeded",
            )

    @patch("ai_diplomacy.agents.llm_agent.llm_utils.load_prompt_file", autospec=True)
    async def test_initialization_no_prompt_loader(
        self, mock_llm_utils_load_prompt_file
    ):
        mock_llm_utils_load_prompt_file.return_value = "Prompt from llm_utils"
        agent = LLMAgent(
            agent_id="test_agent_no_loader",
            country="FRANCE",
            config=self.agent_config,
            game_id="test_game_no_loader",
            llm_coordinator=self.mock_llm_coordinator,
            context_provider_factory=self.mock_context_provider_factory,
            prompt_loader=None,
            llm_caller_override=None,
        )
        self.assertIsNotNone(agent.system_prompt)
        mock_llm_utils_load_prompt_file.assert_any_call("france_system_prompt.txt")

    async def test_load_system_prompt_power_specific(self):
        await self.asyncSetUp()
        self.agent.llm_caller_override = (
            None  # Ensure no override for this part of init
        )
        self.mock_prompt_loader.reset_mock()
        self.mock_prompt_loader.side_effect = [
            "Power-specific prompt via loader",
            "Default prompt via loader",
        ]
        prompt = self.agent._load_system_prompt()
        self.assertEqual(prompt, "Power-specific prompt via loader")
        self.mock_prompt_loader.assert_any_call("france_system_prompt.txt")
        found_default_call = any(
            c == call("system_prompt.txt")
            for c in self.mock_prompt_loader.call_args_list
        )
        self.assertFalse(found_default_call)

    async def test_load_system_prompt_default(self):
        await self.asyncSetUp()
        self.agent.llm_caller_override = None
        self.mock_prompt_loader.reset_mock()
        self.mock_prompt_loader.side_effect = [None, "Default prompt via loader"]
        prompt = self.agent._load_system_prompt()
        self.assertEqual(prompt, "Default prompt via loader")
        self.mock_prompt_loader.assert_has_calls(
            [call("france_system_prompt.txt"), call("system_prompt.txt")],
            any_order=False,
        )  # any_order=False is default but good to be explicit

    async def test_load_system_prompt_failure(self):
        await self.asyncSetUp()
        self.agent.llm_caller_override = None
        self.mock_prompt_loader.reset_mock()
        self.mock_prompt_loader.side_effect = [None, None]
        prompt = self.agent._load_system_prompt()
        self.assertIsNone(prompt)
        self.mock_prompt_loader.assert_has_calls(
            [call("france_system_prompt.txt"), call("system_prompt.txt")],
            any_order=False,
        )

    async def test_decide_orders_no_units(self):
        await self.asyncSetUp()
        self.agent.llm_caller_override = None
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.get_power_units.return_value = []
        mock_phase_state.phase_name = "Spring1901"
        orders = await self.agent.decide_orders(mock_phase_state)
        self.assertEqual(orders, [])
        mock_phase_state.get_power_units.assert_called_once_with("FRANCE")

    async def test_decide_orders_successful(self):
        await self.asyncSetUp()
        self.agent.llm_caller_override = None  # Test regular LLM Coordinator path
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.get_power_units.return_value = ["A PAR", "F BRE"]
        mock_phase_state.phase_name = "Spring1901"
        self.mock_context_provider.provide_context = AsyncMock(
            return_value={
                "context_text": "Test context",
                "tools_available": False,
                "provider_type": "inline",
                "tools": [],
            }
        )
        self.mock_prompt_strategy.build_order_prompt.return_value = "Test order prompt"
        self.mock_llm_coordinator.call_json.return_value = {
            "orders": ["A PAR H", "F BRE M MAR"]
        }
        orders = await self.agent.decide_orders(mock_phase_state)
        self.mock_context_provider.provide_context.assert_called_once()
        self.mock_prompt_strategy.build_order_prompt.assert_called_once_with(
            country="FRANCE",
            goals=self.mock_agent_state.goals,
            relationships=self.mock_agent_state.relationships,
            formatted_diary=self.mock_agent_state.format_private_diary_for_prompt.return_value,
            context_text="Test context",
            tools_available=False,
        )
        self.mock_llm_coordinator.call_json.assert_called_once_with(
            prompt="Test order prompt",
            model_id=self.agent_config.model_id,
            agent_id=self.agent.agent_id,
            game_id=self.agent.game_id,
            phase=mock_phase_state.phase_name,
            system_prompt=self.agent.system_prompt,
            expected_fields=["orders"],
            tools=None,
        )
        self.assertEqual(len(orders), 2)
        self.assertEqual(orders[0], Order("A PAR H"))
        self.assertEqual(orders[1], Order("F BRE M MAR"))

    async def test_decide_orders_llm_error(self):
        await self.asyncSetUp()
        self.agent.llm_caller_override = None
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.get_power_units.return_value = ["A PAR", "F BRE"]
        mock_phase_state.phase_name = "Spring1901"
        self.mock_context_provider.provide_context = AsyncMock(
            return_value={
                "context_text": "Test context",
                "provider_type": "inline",
                "tools_available": False,
                "tools": [],
            }
        )
        self.mock_prompt_strategy.build_order_prompt.return_value = "Test order prompt"
        self.mock_llm_coordinator.call_json.side_effect = Exception("LLM exploded")
        orders = await self.agent.decide_orders(mock_phase_state)
        self.assertEqual(len(orders), 2)
        self.assertEqual(orders[0].order_text, "A PAR H")
        self.assertEqual(orders[1].order_text, "F BRE H")

    async def test_decide_orders_bad_llm_response(self):
        await self.asyncSetUp()
        self.agent.llm_caller_override = None
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.get_power_units.return_value = ["A PAR"]
        mock_phase_state.phase_name = "Spring1901"
        self.mock_context_provider.provide_context = AsyncMock(
            return_value={
                "context_text": "Test context",
                "provider_type": "inline",
                "tools_available": False,
                "tools": [],
            }
        )
        self.mock_prompt_strategy.build_order_prompt.return_value = "Test order prompt"
        self.mock_llm_coordinator.call_json.return_value = {}
        orders = await self.agent.decide_orders(mock_phase_state)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].order_text, "A PAR H")

    async def test_decide_orders_context_tools_available(self):
        await self.asyncSetUp()
        self.agent.llm_caller_override = None
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.get_power_units.return_value = ["A PAR"]
        mock_phase_state.phase_name = "Spring1901"
        mock_tools = [{"type": "function", "function": {"name": "test_tool"}}]
        self.mock_context_provider.provide_context = AsyncMock(
            return_value={
                "context_text": "Context with tools",
                "tools_available": True,
                "tools_definition": mock_tools,
                "provider_type": "inline",
                "tools": mock_tools,
            }
        )
        self.mock_prompt_strategy.build_order_prompt.return_value = "Prompt with tools"
        self.mock_llm_coordinator.call_json.return_value = {"orders": ["A PAR H"]}
        await self.agent.decide_orders(mock_phase_state)
        self.mock_prompt_strategy.build_order_prompt.assert_called_with(
            country="FRANCE",
            goals=self.mock_agent_state.goals,
            relationships=self.mock_agent_state.relationships,
            formatted_diary=self.mock_agent_state.format_private_diary_for_prompt.return_value,
            context_text="Context with tools",
            tools_available=True,
        )
        self.mock_llm_coordinator.call_json.assert_called_with(
            prompt="Prompt with tools",
            model_id=self.agent_config.model_id,
            agent_id=self.agent.agent_id,
            game_id=self.agent.game_id,
            phase=mock_phase_state.phase_name,
            system_prompt=self.agent.system_prompt,
            expected_fields=["orders"],
            tools=mock_tools,
        )

    async def test_decide_orders_context_empty_text(self):
        await self.asyncSetUp()
        self.agent.llm_caller_override = None
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.get_power_units.return_value = ["A PAR"]
        mock_phase_state.phase_name = "Spring1901"
        self.mock_context_provider.provide_context = AsyncMock(
            return_value={
                "context_text": "",
                "tools_available": False,
                "provider_type": "inline",
                "tools": [],
            }
        )
        self.mock_prompt_strategy.build_order_prompt.return_value = (
            "Prompt with empty context"
        )
        self.mock_llm_coordinator.call_json.return_value = {"orders": ["A PAR H"]}
        await self.agent.decide_orders(mock_phase_state)
        self.mock_prompt_strategy.build_order_prompt.assert_called_with(
            country="FRANCE",
            goals=self.mock_agent_state.goals,
            relationships=self.mock_agent_state.relationships,
            formatted_diary=self.mock_agent_state.format_private_diary_for_prompt.return_value,
            context_text="",
            tools_available=False,
        )
        self.mock_llm_coordinator.call_json.assert_called_with(
            prompt="Prompt with empty context",
            model_id=self.agent_config.model_id,
            agent_id=self.agent.agent_id,
            game_id=self.agent.game_id,
            phase=mock_phase_state.phase_name,
            system_prompt=self.agent.system_prompt,
            expected_fields=["orders"],
            tools=None,
        )

    async def test_decide_orders_context_provider_exception(self):
        await self.asyncSetUp()
        self.agent.llm_caller_override = None
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.get_power_units.return_value = ["A PAR"]
        mock_phase_state.phase_name = "Spring1901"
        self.mock_context_provider.provide_context = AsyncMock(
            side_effect=Exception("Context Provider Failed")
        )
        orders = await self.agent.decide_orders(mock_phase_state)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].order_text, "A PAR H")
        self.mock_llm_coordinator.call_json.assert_not_called()

    def test_extract_orders_from_response(self):
        # Create a minimal agent for this synchronous test
        temp_agent_config = AgentConfig(
            country="FRANCE",
            type="llm",
            model_id="dummy_model",
            context_provider="inline",
        )
        agent = LLMAgent(
            agent_id="dummy_agent_extract",
            country="FRANCE",
            config=temp_agent_config,
            game_id="dummy_game",
            llm_coordinator=MagicMock(),
            context_provider_factory=MagicMock(),
            prompt_loader=MagicMock(),
            llm_caller_override=None,
        )
        units = ["A PAR", "F BRE", "A MAR"]
        response = {"orders": ["A PAR H", "F BRE M MAR", "INVALID ORDER STRING"]}
        expected_orders = [
            Order("A PAR H"),
            Order("F BRE M MAR"),
            Order("INVALID ORDER STRING"),
        ]
        actual_orders = agent._extract_orders_from_response(response, units)
        self.assertEqual(actual_orders, expected_orders)
        response_dict_order = {
            "orders": [{"unit": "A PAR", "action": "H"}, "F BRE M MAR"]
        }
        expected_orders_dict = [Order("A PAR H"), Order("F BRE M MAR")]
        actual_orders_dict = agent._extract_orders_from_response(
            response_dict_order, units
        )
        self.assertEqual(actual_orders_dict, expected_orders_dict)
        response_all_dict_order = {
            "orders": [
                {"unit": "A PAR", "action": "H"},
                {"unit": "F BRE", "action": "M MAR"},
            ]
        }
        expected_all_dict_orders = [Order("A PAR H"), Order("F BRE M MAR")]
        actual_all_dict_orders = agent._extract_orders_from_response(
            response_all_dict_order, units
        )
        self.assertEqual(actual_all_dict_orders, expected_all_dict_orders)
        response_partial_dict = {
            "orders": [{"action": "H"}, {"unit": "F BRE"}, "A MAR H"]
        }
        expected_partial_dict_orders = [Order("A MAR H")]
        units_for_partial = ["X YZ", "F BRE", "A MAR"]
        actual_partial_dict_orders = agent._extract_orders_from_response(
            response_partial_dict, units_for_partial
        )
        self.assertEqual(actual_partial_dict_orders, expected_partial_dict_orders)

    def test_extract_orders_edge_cases(self):
        temp_agent_config = AgentConfig(
            country="FRANCE",
            type="llm",
            model_id="dummy_model",
            context_provider="inline",
        )
        agent = LLMAgent(
            agent_id="dummy_agent_extract_edge",
            country="FRANCE",
            config=temp_agent_config,
            game_id="dummy_game_edge",
            llm_coordinator=MagicMock(),
            context_provider_factory=MagicMock(),
            prompt_loader=MagicMock(),
            llm_caller_override=None,
        )
        units = ["A PAR"]
        # Method now returns default Hold orders for the units if response is None or malformed
        default_hold = [Order("A PAR H")]
        self.assertEqual(agent._extract_orders_from_response(None, units), default_hold)
        self.assertEqual(agent._extract_orders_from_response({}, units), default_hold)
        self.assertEqual(
            agent._extract_orders_from_response({"orders": None}, ["A PAR"]),
            default_hold,
        )  # provide units list
        self.assertEqual(
            agent._extract_orders_from_response({"orders": []}, ["A PAR"]), default_hold
        )  # provide units list
        self.assertEqual(
            agent._extract_orders_from_response({"orders": "not a list"}, units),
            default_hold,
        )
        self.assertEqual(
            agent._extract_orders_from_response({"orders": [123, True]}, units),
            default_hold,
        )  # No valid orders, defaults to hold
        self.assertEqual(
            agent._extract_orders_from_response({"orders": [{"unit": "A PAR"}]}, units),
            default_hold,
        )  # Missing action
        self.assertEqual(
            agent._extract_orders_from_response({"orders": [{"action": "H"}]}, units),
            default_hold,
        )  # Missing unit
        self.assertEqual(
            agent._extract_orders_from_response(
                {"orders": [{"unit": 123, "action": "H"}]}, units
            ),
            default_hold,
        )  # Invalid unit type
        self.assertEqual(
            agent._extract_orders_from_response(
                {"orders": [{"unit": "A PAR", "action": True}]}, units
            ),
            default_hold,
        )  # Invalid action type
        # Test with no units, should return empty list if orders are empty or invalid
        self.assertEqual(agent._extract_orders_from_response({"orders": []}, []), [])

    async def test_negotiate_successful(self):
        await self.asyncSetUp()
        self.agent.llm_caller_override = None
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        # Agent computes active_powers as: [p for p in phase.powers if not phase.is_power_eliminated(p) and p != self.country]
        mock_phase_state.powers = frozenset(["FRANCE", "ENGLAND", "GERMANY"])
        mock_phase_state.is_power_eliminated.side_effect = (
            lambda p: False
        )  # No one eliminated
        expected_active_powers = ["ENGLAND", "GERMANY"]  # FRANCE is self.country

        mock_phase_state.phase_name = "Spring1901Diplomacy"
        self.mock_context_provider.provide_context = AsyncMock(
            return_value={
                "context_text": "Negotiation context",
                "tools_available": False,
                "provider_type": "inline",
                "tools": [],
            }
        )
        self.mock_prompt_strategy.build_negotiation_prompt.return_value = (
            "Test negotiation prompt"
        )
        self.mock_llm_coordinator.call_json.return_value = {
            "messages": [{"recipient": "ENGLAND", "content": "Hello England"}]
        }
        messages = await self.agent.negotiate(mock_phase_state)
        self.mock_context_provider.provide_context.assert_called_once()
        self.mock_prompt_strategy.build_negotiation_prompt.assert_called_once()
        prompt_args = self.mock_prompt_strategy.build_negotiation_prompt.call_args[1]
        self.assertEqual(prompt_args["country"], "FRANCE")
        self.assertCountEqual(prompt_args["active_powers"], expected_active_powers)
        self.mock_llm_coordinator.call_json.assert_called_once_with(
            prompt="Test negotiation prompt",
            model_id=self.agent_config.model_id,
            agent_id=self.agent.agent_id,
            game_id=self.agent.game_id,
            phase=mock_phase_state.phase_name,
            system_prompt=self.agent.system_prompt,
            expected_fields=["messages"],
            tools=None,
        )
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            messages[0],
            Message(
                "ENGLAND",
                "Hello England",
                message_type=constants.MESSAGE_TYPE_BROADCAST,
            ),
        )

    async def test_negotiate_llm_error(self):
        await self.asyncSetUp()
        self.agent.llm_caller_override = None
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.phase_name = "TestNegotiateLLMErrorPhase"
        mock_phase_state.powers = frozenset(["FRANCE", "ENGLAND"])
        mock_phase_state.is_power_eliminated.return_value = False
        self.mock_context_provider.provide_context = AsyncMock(
            return_value={
                "context_text": "Context",
                "tools_available": False,
                "provider_type": "inline",
                "tools": [],
            }
        )
        self.mock_llm_coordinator.call_json.side_effect = Exception(
            "LLM negotiation error"
        )
        messages = await self.agent.negotiate(mock_phase_state)
        self.assertEqual(messages, [])

    async def test_negotiate_bad_llm_response(self):
        await self.asyncSetUp()
        self.agent.llm_caller_override = None
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.phase_name = "TestNegotiatePhase"
        mock_phase_state.powers = frozenset(["FRANCE", "ENGLAND"])
        mock_phase_state.is_power_eliminated.return_value = False
        self.mock_context_provider.provide_context = AsyncMock(
            return_value={
                "context_text": "Context",
                "tools_available": False,
                "provider_type": "inline",
                "tools": [],
            }
        )
        self.mock_llm_coordinator.call_json.return_value = {}
        messages = await self.agent.negotiate(mock_phase_state)
        self.assertEqual(messages, [])

    async def test_negotiate_context_tools_available(self):
        await self.asyncSetUp()
        self.agent.llm_caller_override = None
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.powers = frozenset(["FRANCE", "ENGLAND"])
        mock_phase_state.is_power_eliminated.side_effect = lambda p: False
        expected_active_powers = ["ENGLAND"]
        mock_phase_state.phase_name = "Spring1901Diplomacy"
        mock_tools = [{"type": "function", "function": {"name": "negotiation_tool"}}]
        self.mock_context_provider.provide_context = AsyncMock(
            return_value={
                "context_text": "Negotiation context with tools",
                "tools_available": True,
                "tools_definition": mock_tools,
                "provider_type": "inline",
                "tools": mock_tools,
            }
        )
        self.mock_prompt_strategy.build_negotiation_prompt.return_value = (
            "Negotiation prompt with tools"
        )
        self.mock_llm_coordinator.call_json.return_value = {
            "messages": [{"recipient": "ENGLAND", "content": "Tool talk"}]
        }
        await self.agent.negotiate(mock_phase_state)
        self.mock_prompt_strategy.build_negotiation_prompt.assert_called_with(
            country="FRANCE",
            active_powers=expected_active_powers,
            goals=self.mock_agent_state.goals,
            relationships=self.mock_agent_state.relationships,
            formatted_diary=self.mock_agent_state.format_private_diary_for_prompt.return_value,
            context_text="Negotiation context with tools",
            tools_available=True,
        )
        self.mock_llm_coordinator.call_json.assert_called_with(
            prompt="Negotiation prompt with tools",
            model_id=self.agent_config.model_id,
            agent_id=self.agent.agent_id,
            game_id=self.agent.game_id,
            phase=mock_phase_state.phase_name,
            system_prompt=self.agent.system_prompt,
            expected_fields=["messages"],
            tools=mock_tools,
        )

    async def test_negotiate_context_empty_text(self):
        await self.asyncSetUp()
        self.agent.llm_caller_override = None
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.powers = frozenset(["FRANCE", "ENGLAND"])
        mock_phase_state.is_power_eliminated.side_effect = lambda p: False
        expected_active_powers = ["ENGLAND"]
        mock_phase_state.phase_name = "Spring1901Diplomacy"
        self.mock_context_provider.provide_context = AsyncMock(
            return_value={
                "context_text": "",
                "tools_available": False,
                "provider_type": "inline",
                "tools": [],
            }
        )
        self.mock_prompt_strategy.build_negotiation_prompt.return_value = (
            "Negotiation prompt with empty context"
        )
        self.mock_llm_coordinator.call_json.return_value = {
            "messages": [{"recipient": "ENGLAND", "content": "Empty context talk"}]
        }
        await self.agent.negotiate(mock_phase_state)
        self.mock_prompt_strategy.build_negotiation_prompt.assert_called_with(
            country="FRANCE",
            active_powers=expected_active_powers,
            goals=self.mock_agent_state.goals,
            relationships=self.mock_agent_state.relationships,
            formatted_diary=self.mock_agent_state.format_private_diary_for_prompt.return_value,
            context_text="",
            tools_available=False,
        )
        self.mock_llm_coordinator.call_json.assert_called_with(
            prompt="Negotiation prompt with empty context",
            model_id=self.agent_config.model_id,
            agent_id=self.agent.agent_id,
            game_id=self.agent.game_id,
            phase=mock_phase_state.phase_name,
            system_prompt=self.agent.system_prompt,
            expected_fields=["messages"],
            tools=None,
        )

    async def test_negotiate_context_provider_exception(self):
        await self.asyncSetUp()
        self.agent.llm_caller_override = None
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.phase_name = "TestNegotiateContextErrorPhase"
        mock_phase_state.powers = frozenset(["FRANCE", "ENGLAND"])
        mock_phase_state.is_power_eliminated.return_value = False
        self.mock_context_provider.provide_context = AsyncMock(
            side_effect=Exception("Context Provider Failed")
        )
        messages = await self.agent.negotiate(mock_phase_state)
        self.assertEqual(messages, [])
        self.mock_llm_coordinator.call_json.assert_not_called()

    def test_extract_messages_from_response(self):
        temp_agent_config = AgentConfig(
            country="FRANCE",
            type="llm",
            model_id="dummy_model",
            context_provider="inline",
        )
        agent = LLMAgent(
            agent_id="dummy_agent_extract_msg",
            country="FRANCE",
            config=temp_agent_config,
            game_id="dummy_game_msg",
            llm_coordinator=MagicMock(),
            context_provider_factory=MagicMock(),
            prompt_loader=MagicMock(),
            llm_caller_override=None,
        )
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.powers = frozenset(["ENGLAND", "GERMANY", "ITALY", "FRANCE"])
        response = {
            "messages": [
                {"recipient": "ENGLAND", "content": "Hello England"},
                {
                    "recipient": "GERMANY",
                    "content": "Hi Germany",
                    "message_type": "SECRET",
                },
                {"recipient": "ITALY", "content": "Ciao Italy"},
            ]
        }
        expected_messages = [
            Message(
                "ENGLAND",
                "Hello England",
                message_type=constants.MESSAGE_TYPE_BROADCAST,
            ),
            Message("GERMANY", "Hi Germany", message_type="SECRET"),
            Message(
                "ITALY", "Ciao Italy", message_type=constants.MESSAGE_TYPE_BROADCAST
            ),
        ]
        actual_messages = agent._extract_messages_from_response(
            response, mock_phase_state
        )
        self.assertEqual(actual_messages, expected_messages)
        response_invalid_type = {
            "messages": [
                {
                    "recipient": "ENGLAND",
                    "content": "Type test",
                    "message_type": "INVALID_TYPE",
                }
            ]
        }
        expected_messages_invalid_type = [
            Message(
                "ENGLAND", "Type test", message_type=constants.MESSAGE_TYPE_BROADCAST
            )
        ]
        actual_messages_invalid_type = agent._extract_messages_from_response(
            response_invalid_type, mock_phase_state
        )
        self.assertEqual(actual_messages_invalid_type, expected_messages_invalid_type)

    def test_extract_messages_edge_cases(self):
        temp_agent_config = AgentConfig(
            country="FRANCE",
            type="llm",
            model_id="dummy_model",
            context_provider="inline",
        )
        agent = LLMAgent(
            agent_id="dummy_agent_extract_msg_edge",
            country="FRANCE",
            config=temp_agent_config,
            game_id="dummy_game_msg_edge",
            llm_coordinator=MagicMock(),
            context_provider_factory=MagicMock(),
            prompt_loader=MagicMock(),
            llm_caller_override=None,
        )
        mock_phase_state = MagicMock(spec=PhaseState)
        mock_phase_state.powers = frozenset(
            ["ENGLAND", "GERMANY", "ITALY", "RUSSIA", "AUSTRIA", "TURKEY", "FRANCE"]
        )
        self.assertEqual(
            agent._extract_messages_from_response(None, mock_phase_state), []
        )
        self.assertEqual(
            agent._extract_messages_from_response({}, mock_phase_state), []
        )
        self.assertEqual(
            agent._extract_messages_from_response({"messages": None}, mock_phase_state),
            [],
        )
        self.assertEqual(
            agent._extract_messages_from_response({"messages": []}, mock_phase_state),
            [],
        )
        self.assertEqual(
            agent._extract_messages_from_response(
                {"messages": "not a list"}, mock_phase_state
            ),
            [],
        )
        self.assertEqual(
            agent._extract_messages_from_response(
                {"messages": [123]}, mock_phase_state
            ),
            [],
        )
        self.assertEqual(
            agent._extract_messages_from_response({"messages": [{}]}, mock_phase_state),
            [],
        )
        self.assertEqual(
            agent._extract_messages_from_response(
                {"messages": [{"recipient": "ENGLAND"}]}, mock_phase_state
            ),
            [],
        )
        self.assertEqual(
            agent._extract_messages_from_response(
                {"messages": [{"content": "Hi"}]}, mock_phase_state
            ),
            [],
        )
        self.assertEqual(
            agent._extract_messages_from_response(
                {"messages": [{"recipient": 123, "content": "Hi"}]}, mock_phase_state
            ),
            [],
        )
        self.assertEqual(
            agent._extract_messages_from_response(
                {"messages": [{"recipient": "ENGLAND", "content": True}]},
                mock_phase_state,
            ),
            [],
        )
        self.assertEqual(
            agent._extract_messages_from_response(
                {"messages": [{"recipient": "SPAIN", "content": "Hola"}]},
                mock_phase_state,
            ),
            [],
        )
        response_non_string_type = {
            "messages": [
                {"recipient": "ENGLAND", "content": "Type test", "message_type": 123}
            ]
        }
        expected_msg_non_string_type = [
            Message(
                "ENGLAND", "Type test", message_type=constants.MESSAGE_TYPE_BROADCAST
            )
        ]
        actual_msg_non_string_type = agent._extract_messages_from_response(
            response_non_string_type, mock_phase_state
        )
        self.assertEqual(actual_msg_non_string_type, expected_msg_non_string_type)

    async def test_update_state(self):
        await self.asyncSetUp()
        self.agent.llm_caller_override = None  # Test standard path
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.country = "FRANCE"
        mock_phase_state.phase_name = "Spring1901Movement"
        mock_phase_state.get_power_units.return_value = ["A PAR", "F BRE"]
        mock_phase_state.get_power_centers.return_value = ["PAR", "BRE"]
        mock_phase_state.is_game_over.return_value = False
        mock_phase_state.powers = frozenset(["FRANCE", "GERMANY"])
        mock_phase_state.is_power_eliminated.return_value = False
        # Setup for rule-based goal update: FRANCE has 2 centers
        mock_phase_state.get_center_count.side_effect = (
            lambda p: 2 if p == "FRANCE" else (3 if p == "GERMANY" else 0)
        )
        mock_events = [{"type": "build", "power": "FRANCE", "details": "A PAR built"}]
        self.mock_llm_coordinator.call_json.return_value = {
            "diary_entry": "Test diary entry"
        }
        original_goals = ["Initial Test Goal"]
        self.mock_agent_state.goals = original_goals[:]
        self.mock_agent_state.add_journal_entry.reset_mock()
        self.mock_agent_state.add_diary_entry.reset_mock()
        await self.agent.update_state(mock_phase_state, mock_events)
        self.mock_agent_state.add_diary_entry.assert_called_once_with(
            "Test diary entry", "Spring1901Movement"
        )
        self.mock_agent_state._update_relationships_from_events.assert_called_once_with(
            "FRANCE", mock_events
        )
        expected_new_goals = ["Survive and avoid elimination"]
        self.assertEqual(self.mock_agent_state.goals, expected_new_goals)
        self.mock_agent_state.add_journal_entry.assert_any_call(
            f"Goals updated from {original_goals} to {expected_new_goals}"
        )
        self.mock_agent_state.add_journal_entry.assert_called()

    async def test_generate_phase_diary_entry_successful(self):
        await self.asyncSetUp()
        self.agent.llm_caller_override = None
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.phase_name = "TestPhase"
        mock_phase_state.get_power_units.return_value = ["U1"]
        mock_phase_state.get_power_centers.return_value = ["C1"]
        mock_phase_state.is_game_over.return_value = False
        mock_events = [{"event": "e1"}]
        self.mock_prompt_strategy.build_diary_generation_prompt.return_value = (
            "Diary prompt"
        )
        self.mock_llm_coordinator.call_json.return_value = {
            constants.LLM_RESPONSE_KEY_DIARY_ENTRY: "LLM diary entry"
        }
        return_value = await self.agent._generate_phase_diary_entry(
            mock_phase_state, mock_events
        )
        self.assertIsNone(return_value)
        self.mock_agent_state.add_diary_entry.assert_called_once_with(
            "LLM diary entry", mock_phase_state.phase_name
        )
        self.mock_prompt_strategy.build_diary_generation_prompt.assert_called_once()
        self.mock_llm_coordinator.call_json.assert_called_once_with(
            prompt="Diary prompt",
            model_id=self.agent_config.model_id,
            agent_id=self.agent.agent_id,
            game_id=self.agent.game_id,
            phase=mock_phase_state.phase_name,
            system_prompt=self.agent.system_prompt,
            expected_fields=[constants.LLM_RESPONSE_KEY_DIARY_ENTRY],
        )

    async def test_generate_phase_diary_entry_llm_error(self):
        await self.asyncSetUp()
        self.agent.llm_caller_override = None
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.phase_name = "TestPhaseError"
        mock_phase_state.get_power_units.return_value = []
        mock_phase_state.get_power_centers.return_value = []
        mock_phase_state.is_game_over.return_value = False
        self.mock_llm_coordinator.call_json.side_effect = Exception(
            "LLM error for diary"
        )
        mock_events = [{"type": "some_event"}]
        await self.agent._generate_phase_diary_entry(mock_phase_state, mock_events)
        self.mock_agent_state.add_diary_entry.assert_called_once_with(
            f"Phase {mock_phase_state.phase_name} completed (diary generation failed).",
            mock_phase_state.phase_name,
        )

    async def test_analyze_and_update_goals_change(self):
        # Test rule-based change
        await self.asyncSetUp()
        self.agent.llm_caller_override = None  # Rule-based, no LLM call
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.country = "FRANCE"
        mock_phase_state.powers = frozenset(["FRANCE", "GERMANY"])
        mock_phase_state.is_power_eliminated.return_value = False
        # Setup for rule: 2 centers -> "Survive and avoid elimination"
        mock_phase_state.get_center_count.side_effect = (
            lambda p: 2 if p == "FRANCE" else 5
        )

        initial_goals = [
            "Initial Goal To Be Changed Different From Rule"
        ]  # Make sure it's different
        self.mock_agent_state.goals = initial_goals[:]
        self.mock_agent_state.add_journal_entry.reset_mock()
        await self.agent._analyze_and_update_goals(mock_phase_state)
        expected_new_goals = ["Survive and avoid elimination"]
        self.assertEqual(self.mock_agent_state.goals, expected_new_goals)
        self.mock_agent_state.add_journal_entry.assert_called_once_with(
            f"Goals updated from {initial_goals} to {expected_new_goals}"
        )
        self.mock_llm_coordinator.call_json.assert_not_called()  # Verify no LLM call

    async def test_analyze_and_update_goals_clear_leader(self):
        # Test rule-based for many centers (but not 18 for specific win goal)
        await self.asyncSetUp()
        self.agent.llm_caller_override = None
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.country = "FRANCE"
        mock_phase_state.powers = frozenset(["FRANCE", "GERMANY"])
        # 10 centers -> "Consolidate position and prepare for victory"
        mock_phase_state.get_center_count.side_effect = (
            lambda p: 10 if p == "FRANCE" else 1
        )
        mock_phase_state.is_power_eliminated.return_value = False
        self.mock_agent_state.goals = ["Some old goal"]
        self.mock_agent_state.add_journal_entry.reset_mock()
        expected_goals = ["Consolidate position and prepare for victory"]
        await self.agent._analyze_and_update_goals(mock_phase_state)
        self.assertEqual(self.mock_agent_state.goals, expected_goals)
        self.mock_agent_state.add_journal_entry.assert_called_once_with(
            f"Goals updated from {['Some old goal']} to {expected_goals}"
        )
        self.mock_llm_coordinator.call_json.assert_not_called()

    async def test_analyze_and_update_goals_no_redundant_addition(self):
        # Test rule-based no change because goals already match rules
        await self.asyncSetUp()
        self.agent.llm_caller_override = None
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.country = "FRANCE"
        # 5 centers -> "Expand territory and gain supply centers"
        mock_phase_state.get_center_count.side_effect = (
            lambda p: 5 if p == "FRANCE" else 3
        )
        mock_phase_state.powers = frozenset(["FRANCE", "GERMANY"])
        mock_phase_state.is_power_eliminated.return_value = False
        # Set current goals to what rules would produce
        current_goals_matching_rules = ["Expand territory and gain supply centers"]
        self.mock_agent_state.goals = current_goals_matching_rules[:]
        self.mock_agent_state.add_journal_entry.reset_mock()
        await self.agent._analyze_and_update_goals(mock_phase_state)
        self.assertEqual(self.mock_agent_state.goals, current_goals_matching_rules)
        # Rule based _analyze_and_update_goals only adds journal entry if goals *change*.
        self.mock_agent_state.add_journal_entry.assert_not_called()
        self.mock_llm_coordinator.call_json.assert_not_called()

    async def test_analyze_and_update_goals_no_change(self):
        # Test rule-based no change
        await self.asyncSetUp()
        self.agent.llm_caller_override = None
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.country = "FRANCE"
        # 6 centers -> "Expand territory and gain supply centers"
        mock_phase_state.get_center_count.side_effect = (
            lambda p: 6 if p == "FRANCE" else 3
        )
        mock_phase_state.powers = frozenset(["FRANCE", "GERMANY"])
        mock_phase_state.is_power_eliminated.return_value = False
        current_goals = ["Expand territory and gain supply centers"]
        self.mock_agent_state.goals = current_goals[:]
        self.mock_agent_state.add_journal_entry.reset_mock()
        await self.agent._analyze_and_update_goals(mock_phase_state)
        self.assertEqual(self.mock_agent_state.goals, current_goals)
        self.mock_agent_state.add_journal_entry.assert_not_called()  # No journal entry if goals don't change
        self.mock_llm_coordinator.call_json.assert_not_called()

    async def test_get_agent_info(self):
        await self.asyncSetUp()
        self.agent.llm_caller_override = None
        self.mock_agent_state.private_diary = ["Entry 1", "Entry 2"]
        self.mock_agent_state.private_journal = ["Journal A"]
        expected_info = {
            "agent_id": self.agent.agent_id,
            "country": self.agent.country,
            "type": "LLMAgent",
            "model_id": self.agent.model_id,
            "context_provider_type": "inline",
            "goals": self.mock_agent_state.goals,
            "relationships": self.mock_agent_state.relationships,
            "diary_entries": 2,
            "journal_entries": 1,
        }
        # Need to re-initialize agent for this test if asyncSetUp always assigns override
        # or ensure override is None for this path.
        # The get_agent_info method itself doesn't use llm_caller_override, so it should be fine.
        self.assertEqual(self.agent.get_agent_info(), expected_info)

    async def test_llm_caller_override_usage(self):
        await self.asyncSetUp()
        # self.agent.llm_caller_override is already set to self.mock_llm_caller_override in asyncSetUp
        mock_phase_state = MagicMock(spec=PhaseState, autospec=True)
        mock_phase_state.get_power_units.return_value = ["A PAR"]
        mock_phase_state.phase_name = "OverrideTestPhase"

        self.mock_context_provider.provide_context = AsyncMock(
            return_value={
                "context_text": "Context for override",
                "tools_available": False,
                "provider_type": "inline",
                "tools": [],
            }
        )
        self.mock_prompt_strategy.build_order_prompt.return_value = (
            "Order prompt for override"
        )

        # self.mock_llm_caller_override is configured in asyncSetUp to return '{"orders": ["A PAR H"]}'
        orders = await self.agent.decide_orders(mock_phase_state)

        self.mock_llm_caller_override.assert_called_once()
        call_args_list = self.mock_llm_caller_override.call_args_list
        self.assertEqual(len(call_args_list), 1)
        args, kwargs = call_args_list[0]
        self.assertEqual(kwargs.get("prompt"), "Order prompt for override")
        self.assertEqual(kwargs.get("model_id"), self.agent_config.model_id)

        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].order_text, "A PAR H")
        self.mock_llm_coordinator.call_json.assert_not_called()  # Original coordinator should not be called if override is used

    async def test_agent_with_various_context_providers(self):
        """Test that agents work correctly with different context providers (from test_stage2)."""
        # This test is derived from test_agent_with_context_providers in the old test_stage2.py
        # It's kept separate as it tests factory and multi-agent context provider resolution.

        # Create agents with different context provider configs
        inline_config = AgentConfig(
            country="FRANCE",
            type="llm",
            model_id="gpt-4o-mini",
            context_provider="inline",
        )
        mcp_config = AgentConfig(
            country="GERMANY", type="llm", model_id="gpt-4o", context_provider="mcp"
        )
        auto_config = AgentConfig(
            country="ENGLAND",
            type="llm",
            model_id="claude-3-haiku",  # This is a non-tool model in default config
            context_provider="auto",
        )

        # Use a real factory, but we can mock what it uses if needed, or use real objects
        # For this test, using real factory and its dependencies is closer to integration.
        # However, LLMCoordinator is mocked in asyncSetUp, which factory might use.
        # For simplicity, we'll use the factory as is.
        factory = AgentFactory(
            llm_coordinator=self.mock_llm_coordinator,
            context_provider_factory=self.mock_context_provider_factory,
        )

        # Create agents
        # Provide a distinct game_id to avoid interference if tests run in parallel or state leaks
        game_id_context_test = "test_game_context_providers"
        inline_agent = factory.create_agent(
            "inline-test-ctx", "FRANCE", inline_config, game_id_context_test
        )
        mcp_agent = factory.create_agent(
            "mcp-test-ctx", "GERMANY", mcp_config, game_id_context_test
        )
        auto_agent = factory.create_agent(
            "auto-test-ctx", "ENGLAND", auto_config, game_id_context_test
        )

        # Check that agents have correct context providers
        self.assertIsInstance(inline_agent, LLMAgent)
        # In LLMAgent, resolved_context_provider_type comes from the actual provider's get_provider_type()
        # The factory sets up the agent with a provider. We check the type of that provider.
        self.assertEqual(inline_agent.context_provider.get_provider_type(), "inline")

        self.assertIsInstance(mcp_agent, LLMAgent)
        # MCPContextProvider is not available (no client), so factory's get_provider("mcp")
        # (called by resolve_context_provider via create_llm_agent) should fallback to InlineContextProvider.
        self.assertEqual(mcp_agent.context_provider.get_provider_type(), "inline")

        self.assertIsInstance(auto_agent, LLMAgent)
        # claude-3-haiku is not tool-capable by default, so 'auto' should resolve to 'inline'.
        self.assertEqual(auto_agent.context_provider.get_provider_type(), "inline")

        # Create test phase state
        phase_state = PhaseState(
            phase_name="S1901M_CTX",  # Distinct phase name
            year=1901,
            season="SPRING",
            phase_type="MOVEMENT",
            powers=frozenset(["FRANCE", "GERMANY", "ENGLAND"]),
            units={"FRANCE": ["A PAR"], "GERMANY": ["A BER"], "ENGLAND": ["F LON"]},
            supply_centers={"FRANCE": ["PAR"], "GERMANY": ["BER"], "ENGLAND": ["LON"]},
        )

        # Test that agents can call decide_orders with context providers
        # These mocks return dicts directly as per recent changes
        mock_llm_orders_dict_france = {"orders": ["A PAR H"]}
        expected_agent_orders_france = [Order("A PAR H")]

        mock_llm_orders_dict_germany = {"orders": ["A BER H"]}
        expected_agent_orders_germany = [Order("A BER H")]

        mock_llm_orders_dict_england = {"orders": ["F LON H"]}
        expected_agent_orders_england = [Order("F LON H")]

        # Test inline_agent (FRANCE)
        # Agent's llm_caller_override is used if set. It bypasses its internal llm_coordinator.
        mock_llm_override_inline = AsyncMock(return_value=mock_llm_orders_dict_france)
        inline_agent.llm_caller_override = mock_llm_override_inline
        orders_inline = await inline_agent.decide_orders(phase_state)
        self.assertEqual(orders_inline, expected_agent_orders_france)
        mock_llm_override_inline.assert_called_once()
        self.assertIsNotNone(mock_llm_override_inline.call_args)
        called_args_kwargs_inline = mock_llm_override_inline.call_args[1]
        prompt_text_inline = called_args_kwargs_inline.get("prompt")
        self.assertIn("Game Context and Relevant Information:", prompt_text_inline)
        # self.assertIn("=== YOUR POSSIBLE ORDERS ===", prompt_text_inline) # This is specific to InlineContextProvider's formatting

        # Test mcp_agent (GERMANY)
        mock_llm_override_mcp = AsyncMock(return_value=mock_llm_orders_dict_germany)
        mcp_agent.llm_caller_override = mock_llm_override_mcp
        orders_mcp = await mcp_agent.decide_orders(phase_state)
        self.assertEqual(orders_mcp, expected_agent_orders_germany)
        mock_llm_override_mcp.assert_called_once()
        self.assertIsNotNone(mock_llm_override_mcp.call_args)
        called_args_kwargs_mcp = mock_llm_override_mcp.call_args[1]
        prompt_text_mcp = called_args_kwargs_mcp.get("prompt")
        self.assertIn("Game Context and Relevant Information:", prompt_text_mcp)

        # Test auto_agent (ENGLAND)
        mock_llm_override_auto = AsyncMock(return_value=mock_llm_orders_dict_england)
        auto_agent.llm_caller_override = mock_llm_override_auto
        orders_auto = await auto_agent.decide_orders(phase_state)
        self.assertEqual(orders_auto, expected_agent_orders_england)
        mock_llm_override_auto.assert_called_once()
        self.assertIsNotNone(mock_llm_override_auto.call_args)
        called_args_kwargs_auto = mock_llm_override_auto.call_args[1]
        prompt_text_auto = called_args_kwargs_auto.get("prompt")
        self.assertIn("Game Context and Relevant Information:", prompt_text_auto)

    async def test_llm_agent_boundary(self):
        """Test that LLMAgent maintains clean boundaries (no direct game access)."""
        # This test is derived from test_clean_boundaries in the old test_stage1.py

        # Use a minimal config for this boundary test
        # self.agent_config is available from asyncSetUp, but we use a specific one here
        # We create a new agent instance to ensure it's clean for this specific test
        # and to avoid interference from mocks if they are not needed or configured differently.

        # We can use the existing self.mock_llm_coordinator and self.mock_context_provider_factory
        # if the agent initialization requires them.
        # The original test directly instantiated LLMAgent.

        agent_config_boundary = AgentConfig(country="AUSTRIA", type="llm", model_id="gpt-4o-mini-boundary")

        # Minimal agent for boundary check, some dependencies might need to be mocked/provided
        # if the constructor strictly requires them.
        # The original test used: LLMAgent("test", "FRANCE", config, prompt_loader=load_prompt_file)
        # The current LLMAgent constructor is:
        #    agent_id: str,
        #    country: str,
        #    config: AgentConfig,
        #    game_id: str = constants.DEFAULT_GAME_ID,
        #    llm_coordinator: Optional[LLMCoordinator] = None,
        #    context_provider_factory: Optional[ContextProviderFactory] = None,
        #    prompt_loader: Optional[Callable[[str], Optional[str]]] = None, # loader for system prompt
        #    llm_caller_override: Optional[Callable[..., Awaitable[Any]]] = None,

        # Use existing mocks from asyncSetUp for coordinator and factory if they are suitable
        # or create new minimal ones if needed.
        # For this test, we mostly care about the attributes *not* present.
        agent = LLMAgent(
            agent_id="boundary_test_agent",
            country="AUSTRIA",
            config=agent_config_boundary,
            game_id="boundary_test_game",
            llm_coordinator=self.mock_llm_coordinator, # Can use the one from setUp
            context_provider_factory=self.mock_context_provider_factory, # Can use the one from setUp
            prompt_loader=load_prompt_file # As in original test
        )

        # Verify agent doesn't have direct game access
        self.assertFalse(hasattr(agent, "game"))
        self.assertTrue(hasattr(agent, "config"))
        self.assertTrue(hasattr(agent, "llm_coordinator"))
        self.assertTrue(hasattr(agent, "context_provider")) # Added check, as it's a key component
