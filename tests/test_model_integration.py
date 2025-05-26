import pytest
import llm
import asyncio
# AgentLLMInterface was removed in refactor
from ai_diplomacy.services.llm_coordinator import LLMCoordinator

MODEL_ID = "gemma3:latest" # Or your specific model

@pytest.mark.integration
@pytest.mark.skipif(
    MODEL_ID not in llm.get_model_aliases(), 
    reason=f"Local model {MODEL_ID} not installed or not found by llm library"
)
def test_get_model_and_prompt():
    """
    Tests if the specified LLM model can be loaded and can respond to a simple prompt.
    """
    try:
        model = llm.get_model(MODEL_ID)
    except llm.UnknownModelError as e:
        pytest.fail(f"Failed to get model '{MODEL_ID}'. Is it installed and configured correctly? Error: {e}")
    except Exception as e:
        pytest.fail(f"An unexpected error occurred while getting the model: {e}")

    assert model is not None, f"Model '{MODEL_ID}' could not be loaded."

    # Test a simple synchronous prompt
    try:
        response = model.prompt("Say 'test'")
        assert response is not None, "Model returned a None response."
        assert response.text().strip().lower() == "test", f"Model did not respond as expected. Response: '{response.text()}'"
        print(f"Synchronous prompt successful with {MODEL_ID}. Response: {response.text()}")
    except AttributeError as e:
        if "async_prompt" in str(e) or "prompt" not in dir(model):
             pytest.fail(f"The model object for '{MODEL_ID}' does not have a `prompt` method. Available methods: {dir(model)}. Error: {e}")
        else:
            pytest.fail(f"AttributeError during synchronous prompt: {e}")
    except Exception as e:
        pytest.fail(f"An error occurred during synchronous prompt with '{MODEL_ID}': {e}")

    # Test a simple asynchronous prompt if the synchronous one worked
    # Note: We'll need an event loop to run this part of the test if it's not already managed by pytest-asyncio
    # For now, let's assume the main issue is with model loading or the basic prompt method.
    # If `model.prompt` works, `await model.prompt(...)` should also work in an async context. 

class DummyCoordinator(LLMCoordinator):
    async def request(self, model_id, prompt_text, system_prompt_text, game_id="test_game", agent_name="test_agent", phase_str="test_phase", request_identifier="request"):
        # Simulate a successful LLM response
        return "This is a dummy LLM response." 