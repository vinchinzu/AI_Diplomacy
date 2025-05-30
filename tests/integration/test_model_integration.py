import pytest
import llm

# AgentLLMInterface was removed in refactor
# from ai_diplomacy.services.llm_coordinator import LLMCoordinator # No longer needed directly if FakeLLMCoordinator is used
from tests.fakes import FakeLLMCoordinator # Added import

MODEL_ID = "gemma3:latest"  # Or your specific model


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skipif(
    MODEL_ID not in llm.get_model_aliases(),
    reason=f"Local model {MODEL_ID} not installed or not found by llm library",
)
def test_get_model_and_prompt():
    """
    Tests if the specified LLM model can be loaded and can respond to a simple prompt.
    """
    _fail = pytest.fail  # Local alias for pytest.fail
    try:
        model = llm.get_model(MODEL_ID)
    except llm.UnknownModelError as e:
        _fail(
            f"Failed to get model '{MODEL_ID}'. Is it installed and configured correctly? Error: {e}"
        )
    except Exception as e:
        _fail(f"An unexpected error occurred while getting the model: {e}")

    assert model is not None, f"Model '{MODEL_ID}' could not be loaded."

    # Test a simple synchronous prompt
    try:
        response = model.prompt("Say 'test'")
        assert response is not None, "Model returned a None response."
        assert response.text().strip().lower() == "test", (
            f"Model did not respond as expected. Response: '{response.text()}'"
        )
        print(
            f"Synchronous prompt successful with {MODEL_ID}. Response: {response.text()}"
        )
    except AttributeError as e:
        if "async_prompt" in str(e) or "prompt" not in dir(model):
            _fail(
                f"The model object for '{MODEL_ID}' does not have a `prompt` method. Available methods: {dir(model)}. Error: {e}"
            )
        else:
            _fail(f"AttributeError during synchronous prompt: {e}")
    except Exception as e:
        _fail(f"An error occurred during synchronous prompt with '{MODEL_ID}': {e}")

    # Test a simple asynchronous prompt if the synchronous one worked
    # Note: We'll need an event loop to run this part of the test if it's not already managed by pytest-asyncio
    # For now, let's assume the main issue is with model loading or the basic prompt method.
    # If `model.prompt` works, `await model.prompt(...)` should also work in an async context.

# Removed DummyCoordinator class definition
# It has been moved to tests._diplomacy_fakes.py and renamed to FakeLLMCoordinator
