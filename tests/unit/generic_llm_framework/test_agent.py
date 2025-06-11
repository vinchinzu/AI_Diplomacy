import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
import logging

from generic_llm_framework.agent import GenericLLMAgent
from generic_llm_framework.core import (
    GenericLLMAgentInterface,
)  # To ensure it implements
from generic_llm_framework.llm_coordinator import LLMCoordinator
from generic_llm_framework.prompt_strategy import BasePromptStrategy
from generic_llm_framework import constants as generic_constants


@pytest.fixture
def mock_llm_coordinator():
    coordinator = AsyncMock(spec=LLMCoordinator)
    coordinator.call_json = AsyncMock()
    return coordinator


@pytest.fixture
def mock_prompt_strategy():
    strategy = MagicMock(spec=BasePromptStrategy)
    strategy.build_prompt = MagicMock()
    # Mock the system_prompt_template attribute that GenericLLMAgent might access
    strategy.system_prompt_template = "Default strategy system prompt"
    return strategy


@pytest.fixture
def minimal_agent_config():
    return {"model_id": "test_model_123"}


@pytest.fixture
def agent(minimal_agent_config, mock_llm_coordinator, mock_prompt_strategy):
    return GenericLLMAgent(
        agent_id="test_agent_001",
        config=minimal_agent_config,
        llm_coordinator=mock_llm_coordinator,
        prompt_strategy=mock_prompt_strategy,
    )


class TestGenericLLMAgent:
    def test_agent_initialization(
        self, agent, mock_llm_coordinator, mock_prompt_strategy, minimal_agent_config
    ):
        """Test that GenericLLMAgent initializes correctly."""
        assert isinstance(agent, GenericLLMAgentInterface)
        assert agent.agent_id == "test_agent_001"
        assert agent.config == minimal_agent_config
        assert agent.llm_coordinator == mock_llm_coordinator
        assert agent.prompt_strategy == mock_prompt_strategy
        assert agent._internal_state == {}  # Initial internal state is empty

    @pytest.mark.asyncio
    async def test_decide_action_success(
        self, agent, mock_llm_coordinator, mock_prompt_strategy
    ):
        """Test decide_action successfully calls dependencies and returns response."""
        mock_state = {"current_turn": 5, "board": "data"}
        mock_possible_actions = ["action1", "action2"]
        expected_prompt = "Prompt for deciding action"
        mock_prompt_strategy.build_prompt.return_value = expected_prompt

        expected_llm_response = {"action": "action1", "confidence": 0.9}
        mock_llm_coordinator.call_json.return_value = expected_llm_response

        # Agent config for this call
        agent.config["model_id"] = "decision_model"
        agent.config["system_prompt"] = "System prompt for decisions"
        agent.config["game_id"] = "game_alpha"
        agent.config["phase"] = "strategy_phase"
        agent.config["verbose_llm_debug"] = True

        actual_response = await agent.decide_action(mock_state, mock_possible_actions)

        expected_prompt_context = {
            "possible_actions": mock_possible_actions,
            "internal_state": agent._internal_state,
        }
        expected_prompt_context.update(mock_state)

        mock_prompt_strategy.build_prompt.assert_called_once_with(
            action_type="decide_action",
            context=expected_prompt_context,
        )
        mock_llm_coordinator.call_json.assert_called_once_with(
            prompt=expected_prompt,
            model_id="decision_model",
            agent_id=agent.agent_id,
            game_id="game_alpha",
            phase="strategy_phase",
            system_prompt="System prompt for decisions",
            verbose_llm_debug=True,
        )
        assert actual_response == expected_llm_response

    @pytest.mark.asyncio
    async def test_decide_action_no_model_id_in_config(
        self, agent, mock_prompt_strategy, caplog
    ):
        """Test decide_action handles missing model_id in config."""
        agent.config = {}  # Empty config, no model_id
        mock_state = {"current_turn": 1}
        mock_possible_actions = ["wait"]

        with caplog.at_level(logging.ERROR):
            response = await agent.decide_action(mock_state, mock_possible_actions)

        assert response == {"error": "Missing model_id in agent configuration"}
        assert f"Agent {agent.agent_id}: model_id not found in config." in caplog.text
        mock_prompt_strategy.build_prompt.assert_not_called()  # Should not proceed to build prompt

    @pytest.mark.asyncio
    async def test_decide_action_llm_call_failure(
        self, agent, mock_llm_coordinator, mock_prompt_strategy
    ):
        """Test decide_action handles exceptions from llm_coordinator."""
        mock_state = {"current_turn": 2}
        mock_possible_actions = ["attack"]
        mock_prompt_strategy.build_prompt.return_value = "prompt_data"

        mock_llm_coordinator.call_json.side_effect = Exception("LLM API is down")
        agent.config["model_id"] = "some_model"  # Ensure model_id is present

        response = await agent.decide_action(mock_state, mock_possible_actions)

        assert "error" in response
        assert response["error"] == "LLM API is down"
        assert response["details"] == "Failed to decide action via LLM."
        mock_prompt_strategy.build_prompt.assert_called_once()  # Prompt should have been built
        mock_llm_coordinator.call_json.assert_called_once()  # LLM call should have been attempted

    @pytest.mark.asyncio
    async def test_generate_communication_success(
        self, agent, mock_llm_coordinator, mock_prompt_strategy
    ):
        """Test generate_communication successfully calls dependencies."""
        mock_state = {"weather": "sunny"}
        mock_recipients = "TeamAlpha"
        expected_prompt = "Prompt for generating communication"
        mock_prompt_strategy.build_prompt.return_value = expected_prompt

        expected_llm_response = {"message": "Hello TeamAlpha!"}
        mock_llm_coordinator.call_json.return_value = expected_llm_response

        agent.config["model_id"] = "comm_model"
        # Use default system prompt from strategy if not in agent.config
        agent.config.pop("system_prompt", None)
        agent.config["game_id"] = generic_constants.DEFAULT_GAME_ID  # Use default
        agent.config["phase"] = "communication_phase"

        actual_response = await agent.generate_communication(
            mock_state, mock_recipients
        )
        expected_prompt_context = {
            "recipients": mock_recipients,
            "internal_state": agent._internal_state,
        }
        expected_prompt_context.update(mock_state)

        mock_prompt_strategy.build_prompt.assert_called_once_with(
            action_type="generate_communication",
            context=expected_prompt_context,
        )
        mock_llm_coordinator.call_json.assert_called_once_with(
            prompt=expected_prompt,
            model_id="comm_model",
            agent_id=agent.agent_id,
            game_id=generic_constants.DEFAULT_GAME_ID,
            phase="communication_phase",
            system_prompt=mock_prompt_strategy.system_prompt_template,  # Should use strategy's default
            verbose_llm_debug=False,  # Default from minimal_config not overriding
        )
        assert actual_response == expected_llm_response

    @pytest.mark.asyncio
    async def test_generate_communication_llm_failure(
        self, agent, mock_llm_coordinator, mock_prompt_strategy
    ):
        """Test generate_communication handles LLM call failures."""
        mock_state = {"board_state": {}}
        mock_recipients = ["ally1", "neutral1"]
        mock_prompt_strategy.build_prompt.return_value = "some_comm_prompt"

        mock_llm_coordinator.call_json.side_effect = ConnectionError("Network issue")
        agent.config["model_id"] = "comm_model_fail"  # Ensure model_id

        response = await agent.generate_communication(mock_state, mock_recipients)

        assert "error" in response
        assert response["error"] == "Network issue"
        assert response["details"] == "Failed to generate communication via LLM."

    @pytest.mark.asyncio
    async def test_update_internal_state(self, agent, caplog):
        """Test update_internal_state logs and updates the internal state dictionary."""
        mock_env_state = {"turn": 10, "score": 100}
        mock_events = [{"event_type": "new_message", "sender": "PlayerA"}]

        with caplog.at_level(logging.INFO):
            await agent.update_internal_state(
                mock_env_state, mock_events
            )  # It's async

        assert (
            f"Agent {agent.agent_id}: Updating internal state. Current env state: {mock_env_state}, Events: {mock_events}"
            in caplog.text
        )
        assert agent._internal_state["last_env_state"] == mock_env_state
        assert agent._internal_state["recent_events"] == mock_events
        assert (
            "last_updated" in agent._internal_state
        )  # Check that timestamp/version key exists

    def test_get_agent_info(self, agent, mock_prompt_strategy, mock_llm_coordinator):
        """Test get_agent_info returns expected dictionary."""
        agent.config["model_id"] = "info_model_xyz"
        agent._internal_state = {"key1": "value1", "key2": [1, 2]}

        info = agent.get_agent_info()

        assert info["agent_id"] == agent.agent_id
        assert info["agent_class"] == "GenericLLMAgent"
        assert info["model_id"] == "info_model_xyz"
        assert info["prompt_strategy_class"] == mock_prompt_strategy.__class__.__name__
        assert info["llm_coordinator_class"] == mock_llm_coordinator.__class__.__name__
        assert "internal_state_summary" in info
        assert info["internal_state_summary"] == {"key1": "str", "key2": "list"}

    def test_get_agent_info_no_model_id(self, agent):
        """Test get_agent_info handles missing model_id in config gracefully."""
        agent.config = {}  # No model_id
        info = agent.get_agent_info()
        assert info["model_id"] == "N/A"

    @pytest.mark.asyncio
    async def test_decide_action_uses_default_constants(
        self, agent, mock_llm_coordinator, mock_prompt_strategy
    ):
        """Test decide_action uses default game_id and phase from generic_constants if not in config."""
        mock_state = {}
        mock_possible_actions = []
        mock_prompt_strategy.build_prompt.return_value = "prompt"
        mock_llm_coordinator.call_json.return_value = {"action": "default"}

        # Ensure these are not in agent's config for this test
        agent.config = {"model_id": "test_model"}

        await agent.decide_action(mock_state, mock_possible_actions)

        call_args = mock_llm_coordinator.call_json.call_args
        assert call_args is not None
        assert call_args.kwargs.get("game_id") == generic_constants.DEFAULT_GAME_ID
        # The phase for decide_action in GenericLLMAgent defaults to 'decide_action' string, not DEFAULT_PHASE_NAME
        assert call_args.kwargs.get("phase") == "decide_action"
        # System prompt should default to the one from prompt_strategy
        assert (
            call_args.kwargs.get("system_prompt")
            == mock_prompt_strategy.system_prompt_template
        )
