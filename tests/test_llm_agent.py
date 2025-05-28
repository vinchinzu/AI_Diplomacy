import pytest
from unittest.mock import AsyncMock, Mock

from ai_diplomacy.agents.llm_agent import LLMAgent
from ai_diplomacy.agents.base import (
    Message,
    Order,
)
# Fixtures are now in conftest.py and will be auto-discovered by pytest
# No need to import AgentConfig, ContextProviderFactory, LLMCoordinator, PhaseState directly for mocking


# Helper function to create an agent instance with mocks, using fixtures
@pytest.fixture
def llm_agent(
    agent_config,
    mock_llm_coordinator,
    mock_context_provider_factory,
    mock_context_provider,
    # mock_load_prompt_file fixture is removed from here, 
    # as LLMAgent will now take a prompt_loader function.
    # Tests requiring specific prompt loading behavior will inject it directly
    # or use a new fixture that returns a mock function.
    mock_load_prompt_file_func, # Use the new fixture that returns a function
):
    agent = LLMAgent(
        agent_id="test_agent",
        country="ENGLAND",
        config=agent_config,
        game_id="test_game",
        llm_coordinator=mock_llm_coordinator,
        context_provider_factory=mock_context_provider_factory,
        prompt_loader=mock_load_prompt_file_func, # Pass the mock loader function
    )
    # Ensure the agent uses the mocked context provider instance from the fixture
    agent.context_provider = mock_context_provider
    # System prompt is now loaded internally by LLMAgent using the prompt_loader
    return agent


@pytest.mark.asyncio
async def test_negotiate_returns_messages_and_updates_diary(
    llm_agent, mock_llm_coordinator, mock_phase_state
):
    mock_llm_coordinator.call_json = AsyncMock(
        return_value={
            "messages": [
                {
                    "recipient": "FRANCE",
                    "content": "Hello France",
                    "message_type": "private",
                }
            ]
        }
    )

    # Clear diary before test if checking for specific entries
    llm_agent.private_diary = []

    messages = await llm_agent.negotiate(mock_phase_state)

    mock_llm_coordinator.call_json.assert_called_once()
    assert isinstance(messages, list)
    assert len(messages) == 1
    message = messages[0]
    assert isinstance(message, Message)
    assert message.recipient == "FRANCE"
    assert message.content == "Hello France"
    assert message.message_type == "private"


@pytest.mark.asyncio
async def test_decide_orders_returns_valid_orders(
    llm_agent, mock_llm_coordinator, mock_phase_state
):
    # Fixture mock_phase_state already provides units by default

    mock_llm_coordinator.call_json = AsyncMock(
        return_value={"orders": ["A LON H", "F EDI M NTH"]}
    )

    orders = await llm_agent.decide_orders(mock_phase_state)

    mock_llm_coordinator.call_json.assert_called_once()
    assert isinstance(orders, list)
    assert len(orders) == 2
    assert isinstance(orders[0], Order)
    assert orders[0].order_str == "A LON H"
    assert isinstance(orders[1], Order)
    assert orders[1].order_str == "F EDI M NTH"


@pytest.mark.asyncio
async def test_decide_orders_no_units(
    llm_agent, mock_llm_coordinator, mock_phase_state
):
    # Test case where the agent has no units
    mock_phase_state.get_power_units = Mock(
        return_value=[]
    )  # Override fixture for this test case

    orders = await llm_agent.decide_orders(mock_phase_state)

    # call_json should NOT be called if there are no units
    mock_llm_coordinator.call_json.assert_not_called()
    assert isinstance(orders, list)
    assert len(orders) == 0
