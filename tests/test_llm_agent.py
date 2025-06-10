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
        self.mock_context_provider.provide_context.return_value = {"context_text": "Ctx", "tools_available": False, "tools": []}
        self.mock_generic_agent_instance.decide_action.return_value = {diplomacy_constants.LLM_RESPONSE_KEY_ORDERS: ["A PAR H"]}

        orders = await self.agent.decide_orders(mock_phase_state)
        self.mock_generic_agent_instance.decide_action.assert_called_once()
        passed_state = self.mock_generic_agent_instance.decide_action.call_args[1]['state']
        self.assertEqual(passed_state['country'], "FRANCE")
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

    async def test_negotiate_successful(self):
        mock_phase_state = MagicMock(spec=PhaseState); mock_phase_state.powers = frozenset(["FRANCE", "ENGLAND"])
        mock_phase_state.is_power_eliminated.return_value = False; mock_phase_state.phase_name="S1901D"
        self.mock_context_provider.provide_context.return_value = {"context_text": "CtxNego"}
        self.mock_generic_agent_instance.generate_communication.return_value = {diplomacy_constants.LLM_RESPONSE_KEY_MESSAGES: [{"recipient": "ENGLAND", "content": "Hi"}]}

        messages = await self.agent.negotiate(mock_phase_state)
        self.mock_generic_agent_instance.generate_communication.assert_called_once()
        passed_state = self.mock_generic_agent_instance.generate_communication.call_args[1]['state']
        self.assertEqual(passed_state['country'], "FRANCE")
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

    async def test_update_state(self):
        mock_phase = MagicMock(spec=PhaseState); mock_phase.phase_name="S1901M"; mock_phase.country="FRANCE"
        mock_phase.get_power_units.return_value = []; mock_phase.get_power_centers.return_value = []
        mock_phase.is_game_over=False; mock_phase.powers=["FRANCE"]; mock_phase.is_power_eliminated.return_value=False
        mock_phase.get_center_count.return_value=1
        mock_events = [{"type":"event"}]
        self.mock_generic_agent_instance.decide_action.side_effect = [
            {diplomacy_constants.LLM_RESPONSE_KEY_DIARY_ENTRY: "Diary"},
            {diplomacy_constants.LLM_RESPONSE_KEY_UPDATED_GOALS: ["Goal"], diplomacy_constants.LLM_RESPONSE_KEY_REASONING: "Reason"}
        ]
        await self.agent.update_state(mock_phase, mock_events)
        self.mock_generic_agent_instance.update_internal_state.assert_called_once_with(state=mock_phase, events=mock_events)
        self.mock_agent_state.add_diary_entry.assert_called_with("Diary", "S1901M")
        self.mock_agent_state._update_relationships_from_events.assert_called_with(self.agent.power_name, mock_events)
        self.assertEqual(self.mock_generic_agent_instance.decide_action.call_count, 2)

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
