import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch

from ai_diplomacy.agents.bloc_llm_agent import BlocLLMAgent
from ai_diplomacy.agents.base import Order
from ai_diplomacy.core.state import PhaseState, PowerState
from ai_diplomacy.services.config import AgentConfig
# LLMCoordinator and ContextProviderFactory might be needed if not fully mocked out


@pytest.fixture
def default_agent_config():
    # Create a default AgentConfig for testing
    return AgentConfig(
        country="ENTENTE_BLOC",  # Bloc name as country for AgentConfig
        type="bloc_llm",
        model_id="test_model_bloc",
        temperature=0.7,
        max_tokens=1500,
        verbose_llm_debug=False,
    )


@pytest.fixture
def bloc_agent_entente(default_agent_config):
    mock_llm_coordinator = (
        MagicMock()
    )  # Simple mock, can be AsyncMock if methods are async
    mock_llm_coordinator.get_completion = AsyncMock()

    mock_context_provider_factory = MagicMock()

    return BlocLLMAgent(
        agent_id="entente_test_id",
        bloc_name="ENTENTE",
        controlled_powers=["FRANCE", "ENGLAND"],
        config=default_agent_config,
        game_id="test_game_bloc",
        llm_coordinator=mock_llm_coordinator,
        context_provider_factory=mock_context_provider_factory,
        prompt_loader=MagicMock(
            return_value="Mocked Bloc Order Prompt Template Content {{ bloc_name }}"
        ),  # Mock prompt_loader
    )


@pytest.fixture
def phase_state_for_bloc():
    mock_phase = MagicMock(spec=PhaseState)
    mock_phase.name = "S1901M"
    mock_phase.year = 1901
    mock_phase.season = "SPRING"
    mock_phase.scs = {"PAR": "FRANCE", "LON": "ENGLAND", "BER": "GERMANY"}
    mock_phase.state = {  # Simplified raw state for phase_key generation
        "locations": {"FRANCE": ["A PAR", "F MAR"], "ENGLAND": ["F LON", "A LVP"]}
    }
    mock_phase.history = "Some game history."

    # Mock PowerState for FRANCE
    ps_france = MagicMock(spec=PowerState)
    ps_france.units = ["A PAR", "F MAR"]
    ps_france.centers = ["PAR", "MAR"]
    ps_france.orders = []

    # Mock PowerState for ENGLAND
    ps_england = MagicMock(spec=PowerState)
    ps_england.units = ["F LON", "A LVP"]
    ps_england.centers = ["LON", "LVP", "EDI"]
    ps_england.orders = []

    def get_power_state_side_effect(power_name):
        if power_name == "FRANCE":
            return ps_france
        elif power_name == "ENGLAND":
            return ps_england
        return None

    mock_phase.get_power_state = MagicMock(side_effect=get_power_state_side_effect)
    return mock_phase


def test_bloc_agent_initialization(bloc_agent_entente):
    assert bloc_agent_entente.bloc_name == "ENTENTE"
    assert bloc_agent_entente.controlled_powers == ["FRANCE", "ENGLAND"]
    assert bloc_agent_entente.country == "ENTENTE"  # own identity
    assert bloc_agent_entente.model_id == "test_model_bloc"
    # Check superclass was initialized with representative country
    # The superclass LLMAgent stores its 'country' as self._country for LLMPromptStrategy
    # This test requires peeking into LLMAgent's internals or asserting behavior based on it.
    # For now, let's assume __init__ logic for representative_country is correct.
    # Accessing super().country is not direct; self.prompt_strategy._power_name might hold it.

    info = bloc_agent_entente.get_agent_info()
    assert info["type"] == "BlocLLMAgent"
    assert info["bloc_name"] == "ENTENTE"
    assert info["controlled_powers"] == ["FRANCE", "ENGLAND"]
    assert info["country"] == "ENTENTE"  # From self.country


@pytest.mark.asyncio
async def test_bloc_agent_decide_orders_prompt_construction(
    bloc_agent_entente, phase_state_for_bloc
):
    # Test that the prompt is constructed (mocking LLM call)
    # Use a valid JSON string for the mock response to avoid JSONDecodeError in the tested code
    bloc_agent_entente.llm_coordinator.get_completion.return_value = json.dumps(
        {}
    )  # Empty JSON

    with patch(
        "ai_diplomacy.agents.bloc_llm_agent.PromptConstructor"
    ) as MockPromptConstructor:
        mock_renderer_instance = MockPromptConstructor.return_value
        mock_renderer_instance.render = MagicMock(
            return_value="Test Constructed Prompt"
        )

        await bloc_agent_entente.decide_orders(phase_state_for_bloc)

        MockPromptConstructor.assert_called_once_with(
            template_string="Mocked Bloc Order Prompt Template Content {{ bloc_name }}"
        )
        mock_renderer_instance.render.assert_called_once()
        # TODO: Deeper assertion on context passed to render if possible by inspecting call_args


@pytest.mark.asyncio
async def test_bloc_agent_decide_orders_parsing_and_caching(
    bloc_agent_entente, phase_state_for_bloc
):
    mock_response_json = {
        "FRANCE": ["A PAR HLD", "F MAR SUP A PAR"],
        "ENGLAND": ["F LON HLD", "A LVP S F LON"],
    }
    # Simulate LLMCoordinator returning the JSON string
    bloc_agent_entente.llm_coordinator.get_completion.return_value = json.dumps(
        mock_response_json
    )

    # Call once to populate cache
    returned_orders_france = await bloc_agent_entente.decide_orders(
        phase_state_for_bloc
    )

    # Verify LLM was called once
    bloc_agent_entente.llm_coordinator.get_completion.assert_called_once()

    # Verify temporary return for the first power (FRANCE)
    assert len(returned_orders_france) == 2
    assert Order("A PAR HLD") in returned_orders_france
    assert Order("F MAR SUP A PAR") in returned_orders_france

    # Verify cache content (using the new get_all_bloc_orders_for_phase method)
    phase_key = (
        bloc_agent_entente._cached_bloc_orders_phase_key
    )  # Get the key used by agent
    assert phase_key is not None, "Phase key was not set in cache"

    cached_orders_all = bloc_agent_entente.get_all_bloc_orders_for_phase(phase_key)
    assert "FRANCE" in cached_orders_all
    assert "ENGLAND" in cached_orders_all
    assert len(cached_orders_all["FRANCE"]) == 2
    assert Order("A LVP S F LON") in cached_orders_all["ENGLAND"]

    # Call again, LLM should not be called (cache hit)
    bloc_agent_entente.llm_coordinator.get_completion.reset_mock()
    returned_orders_france_cached = await bloc_agent_entente.decide_orders(
        phase_state_for_bloc
    )
    bloc_agent_entente.llm_coordinator.get_completion.assert_not_called()
    assert returned_orders_france_cached == returned_orders_france


@pytest.mark.asyncio
async def test_bloc_agent_decide_orders_json_decode_error(
    bloc_agent_entente, phase_state_for_bloc
):
    bloc_agent_entente.llm_coordinator.get_completion.return_value = "This is not JSON"

    orders = await bloc_agent_entente.decide_orders(phase_state_for_bloc)
    assert orders == []  # Should return empty list for the representative power

    phase_key = bloc_agent_entente._cached_bloc_orders_phase_key
    assert phase_key is not None, (
        "Phase key should still be set on error to cache the failure"
    )
    cached_orders = bloc_agent_entente.get_all_bloc_orders_for_phase(phase_key)
    assert cached_orders == {}  # Cache should be empty


@pytest.mark.asyncio
async def test_bloc_agent_decide_orders_controlled_power_mismatch(
    bloc_agent_entente, phase_state_for_bloc
):
    mock_response_json = {
        "FRANCE": ["A PAR HLD"],
        "GERMANY": [
            "A BER HLD"
        ],  # Germany is not in bloc_agent_entente.controlled_powers
    }
    bloc_agent_entente.llm_coordinator.get_completion.return_value = json.dumps(
        mock_response_json
    )

    returned_orders = await bloc_agent_entente.decide_orders(phase_state_for_bloc)
    assert Order("A PAR HLD") in returned_orders

    phase_key = bloc_agent_entente._cached_bloc_orders_phase_key
    cached_orders = bloc_agent_entente.get_all_bloc_orders_for_phase(phase_key)
    assert "FRANCE" in cached_orders
    assert "GERMANY" not in cached_orders  # Germany's orders should be ignored


# Helper for mocking async JSON response, if needed without full AsyncMock
# This is not strictly necessary if AsyncMock is used correctly for get_completion.
# class FutureJSONResponse:
#     def __init__(self, text_data):
#         self.text_data = text_data
#     async def __call__(self, *args, **kwargs): # Make it callable like get_completion
#         return self.text_data
