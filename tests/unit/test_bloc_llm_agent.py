import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch

from ai_diplomacy.agents.bloc_llm_agent import BlocLLMAgent
from ai_diplomacy.agents.base import Order
from ai_diplomacy.core.state import PhaseState # PowerState might not be directly used in mocks now
from ai_diplomacy.services.config import AgentConfig
from generic_llm_framework.llm_coordinator import LLMCoordinator as GenericLLMCoordinator # For type hinting
from generic_llm_framework.agent import GenericLLMAgent as FrameworkGenericLLMAgent # For mocking generic_agent
from generic_llm_framework.llm_utils import load_prompt_file # For default prompt_loader


@pytest.fixture
def default_agent_config():
    return AgentConfig(
        country="ENTENTE_BLOC",
        type="bloc_llm",
        model_id="test_model_bloc",
        temperature=0.7,
        max_tokens=1500,
        verbose_llm_debug=False,
        # Ensure prompt_strategy_config is present if LLMAgent's __init__ expects it via AgentConfig
        prompt_strategy_config=None
    )

@pytest.fixture
def mock_generic_llm_agent_instance():
    # This will be the mock for the self.generic_agent instance within LLMAgent (and thus BlocLLMAgent)
    mock_instance = AsyncMock(spec=FrameworkGenericLLMAgent)
    mock_instance.decide_action = AsyncMock()
    # Add other methods if BlocLLMAgent starts using them from generic_agent
    return mock_instance

@pytest.fixture
def bloc_agent_entente(default_agent_config, mock_generic_llm_agent_instance):
    # Mock LLMCoordinator passed to LLMAgent, which then passes it to its GenericLLMAgent
    mock_llm_coord = AsyncMock(spec=GenericLLMCoordinator)
    mock_context_factory = MagicMock() # Mock for ContextProviderFactory

    # We need to patch GenericLLMAgent's instantiation within LLMAgent,
    # or rely on LLMAgent to correctly create and use it.
    # The tests for LLMAgent already cover that it creates GenericLLMAgent.
    # Here, we assume BlocLLMAgent inherits LLMAgent, which has self.generic_agent.
    # We will mock this self.generic_agent after BlocLLMAgent is created.

    # Create real BlocLLMAgent, then replace its generic_agent with a mock
    # This ensures BlocLLMAgent's own __init__ logic runs.
    agent = BlocLLMAgent(
        agent_id="entente_test_id",
        bloc_name="ENTENTE",
        controlled_powers=["FRANCE", "ENGLAND"],
        config=default_agent_config,
        game_id="test_game_bloc",
        llm_coordinator=mock_llm_coord, # Passed to LLMAgent
        context_provider_factory=mock_context_factory, # Passed to LLMAgent
        prompt_loader=MagicMock(return_value="Mocked Bloc Order Jinja Template {{ bloc_name }}")
    )
    # Replace the created generic_agent with our mock for controlled testing of BlocLLMAgent's logic
    agent.generic_agent = mock_generic_llm_agent_instance
    return agent


@pytest.fixture
def phase_state_for_bloc():
    mock_phase = MagicMock(spec=PhaseState)
    mock_phase.phase_name = "S1901M" # Corrected from mock_phase.name
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
    # LLMAgent's get_agent_info now includes generic_agent_info. We test the parts BlocLLMAgent adds/overrides.
    info = bloc_agent_entente.get_agent_info()
    assert info["diplomacy_agent_type"] == "BlocLLMAgent" # Check override
    assert info["bloc_name"] == "ENTENTE"
    assert info["controlled_powers"] == ["FRANCE", "ENGLAND"]
    # The 'country' field in the base info from LLMAgent will be the representative_country ('FRANCE')
    # The 'agent_id' in generic_agent_info will be 'entente_test_id'
    assert info["country"] == "FRANCE"
    assert info["generic_agent_info"]["agent_id"] == "entente_test_id"


@pytest.mark.asyncio
@patch("jinja2.Template") # Patch Jinja2's Template class
async def test_bloc_agent_decide_orders_prompt_construction(
    MockJinjaTemplate, bloc_agent_entente, phase_state_for_bloc
):
    # Mock the behavior of the Jinja2 template rendering
    mock_template_instance = MockJinjaTemplate.return_value
    mock_template_instance.render = MagicMock(return_value="Rendered Jinja Prompt")

    # Mock the generic_agent's decide_action to prevent actual LLM call & check passed prompt
    bloc_agent_entente.generic_agent.decide_action = AsyncMock(return_value={}) # Return empty dict for successful call

    await bloc_agent_entente.decide_orders(phase_state_for_bloc)

    # Check prompt_loader was called (done by BlocLLMAgent's __init__ to load the template string)
    bloc_agent_entente.prompt_loader.assert_called_once_with("bloc_order_prompt.j2")

    # Check Jinja2 Template was instantiated with the loaded template string
    MockJinjaTemplate.assert_called_once_with("Mocked Bloc Order Jinja Template {{ bloc_name }}")

    # Check render was called on the template instance
    mock_template_instance.render.assert_called_once()
    render_context = mock_template_instance.render.call_args[0][0]
    assert render_context["bloc_name"] == "ENTENTE"
    assert render_context["controlled_powers_list"] == ["FRANCE", "ENGLAND"]
    assert render_context["phase"] == phase_state_for_bloc

    # Check that generic_agent.decide_action was called with the rendered prompt
    bloc_agent_entente.generic_agent.decide_action.assert_called_once()
    call_args = bloc_agent_entente.generic_agent.decide_action.call_args[1] # kwargs
    passed_state_to_generic_agent = call_args['state']
    assert passed_state_to_generic_agent["prompt_content"] == "Rendered Jinja Prompt"
    assert passed_state_to_generic_agent["action_type"] == "decide_bloc_orders"


@pytest.mark.asyncio
async def test_bloc_agent_decide_orders_parsing_and_caching(
    bloc_agent_entente, phase_state_for_bloc
):
    mock_response_json = {
        "FRANCE": ["A PAR HLD", "F MAR SUP A PAR"],
        "ENGLAND": ["F LON HLD", "A LVP S F LON"],
    }
    # Mock generic_agent.decide_action to return the LLM response
    bloc_agent_entente.generic_agent.decide_action = AsyncMock(return_value=mock_response_json)

    # Call once to populate cache
    returned_orders_france = await bloc_agent_entente.decide_orders(phase_state_for_bloc)

    # Verify generic_agent.decide_action was called once
    bloc_agent_entente.generic_agent.decide_action.assert_called_once()

    assert len(returned_orders_france) == 2
    assert Order("A PAR HLD") in returned_orders_france

    phase_key = bloc_agent_entente._cached_bloc_orders_phase_key
    assert phase_key is not None
    cached_orders_all = bloc_agent_entente.get_all_bloc_orders_for_phase(phase_key)
    assert "FRANCE" in cached_orders_all and "ENGLAND" in cached_orders_all
    assert Order("A LVP S F LON") in cached_orders_all["ENGLAND"]

    # Call again, generic_agent.decide_action should not be called (cache hit)
    bloc_agent_entente.generic_agent.decide_action.reset_mock()
    returned_orders_france_cached = await bloc_agent_entente.decide_orders(phase_state_for_bloc)
    bloc_agent_entente.generic_agent.decide_action.assert_not_called()
    assert returned_orders_france_cached == returned_orders_france


@pytest.mark.asyncio
async def test_bloc_agent_decide_orders_generic_agent_error(
    bloc_agent_entente, phase_state_for_bloc
):
    # Simulate generic_agent.decide_action returning an error dictionary
    bloc_agent_entente.generic_agent.decide_action = AsyncMock(
        return_value={"error": "GenericLLMAgent failed", "details": "..."}
    )

    orders = await bloc_agent_entente.decide_orders(phase_state_for_bloc)
    assert orders == []

    phase_key = bloc_agent_entente._cached_bloc_orders_phase_key
    assert phase_key is not None
    cached_orders = bloc_agent_entente.get_all_bloc_orders_for_phase(phase_key)
    assert cached_orders == {}


@pytest.mark.asyncio
async def test_bloc_agent_decide_orders_controlled_power_mismatch(
    bloc_agent_entente, phase_state_for_bloc
):
    mock_response_json = {
        "FRANCE": ["A PAR HLD"],
        "GERMANY": ["A BER HLD"], # Germany is not controlled
    }
    bloc_agent_entente.generic_agent.decide_action = AsyncMock(return_value=mock_response_json)

    returned_orders = await bloc_agent_entente.decide_orders(phase_state_for_bloc)
    assert Order("A PAR HLD") in returned_orders

    phase_key = bloc_agent_entente._cached_bloc_orders_phase_key
    cached_orders = bloc_agent_entente.get_all_bloc_orders_for_phase(phase_key)
    assert "FRANCE" in cached_orders
    assert "GERMANY" not in cached_orders


# Helper for mocking async JSON response, if needed without full AsyncMock
# This is not strictly necessary if AsyncMock is used correctly for get_completion.
# class FutureJSONResponse:
#     def __init__(self, text_data):
#         self.text_data = text_data
#     async def __call__(self, *args, **kwargs): # Make it callable like get_completion
#         return self.text_data
