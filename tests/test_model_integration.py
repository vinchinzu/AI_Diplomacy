import pytest
import llm
import asyncio
from ai_diplomacy.llm_interface import AgentLLMInterface
from ai_diplomacy.llm_coordinator import LocalLLMCoordinator

MODEL_ID = "gemma3:latest" # Or your specific model

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

class DummyCoordinator(LocalLLMCoordinator):
    async def request(self, model_id, prompt_text, system_prompt_text, request_identifier="request"):
        # Simulate a successful LLM response
        return "This is a dummy LLM response."

def test_agent_llm_interface_llm_call(monkeypatch):
    """
    Test that AgentLLMInterface can make an LLM call using a dummy coordinator, mimicking agent usage.
    """
    model_id = "dummy/model"
    system_prompt = "You are a test agent."
    power_name = "FRANCE"
    dummy_coordinator = DummyCoordinator()
    interface = AgentLLMInterface(model_id, system_prompt, dummy_coordinator, power_name)

    async def run():
        result = await interface._make_llm_call(
            prompt_text="Say something clever.",
            log_file_path="/tmp/llm_test_log.csv",
            game_phase="S1901M",
            response_type_for_logging="test",
            expect_json=False
        )
        assert result == "This is a dummy LLM response."

    asyncio.run(run()) 