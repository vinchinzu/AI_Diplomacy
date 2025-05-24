import asyncio
import os
import logging
from typing import Optional # Added for type hinting

import llm # Assuming this is the llm library by Simon Willison

logger = logging.getLogger(__name__)
_local_llm_lock = asyncio.Lock()

# Case-insensitive check will be applied to these prefixes
SERIAL_ACCESS_PREFIXES = ["ollama/", "llamacpp/"] # llama.cpp server can also be hit hard
SERIALIZE_LOCAL_LLMS_ENV_VAR = "SERIALIZE_LOCAL_LLMS" # Users can set this to "true"

class LocalLLMCoordinator:
    """
    Coordinates requests to local LLMs, allowing for serialization of requests
    to specific model types (e.g., Ollama, Llama.cpp server) if configured.
    """

    def __init__(self):
        """
        Initializes the LocalLLMCoordinator.
        Currently, no specific initialization is needed.
        """
        pass

    async def request(
        self, 
        model_id: str, 
        prompt_text: str, 
        system_prompt_text: Optional[str],
        request_identifier: str = "request" # For more specific logging
    ) -> str:
        """
        Makes a request to the specified LLM.

        If the model_id matches known local server types (Ollama, Llama.cpp)
        and the SERIALIZE_LOCAL_LLMS_ENV_VAR is set to "true",
        requests will be serialized using an asyncio.Lock.

        Args:
            model_id: The ID of the LLM to use (e.g., "ollama/llama3", "gpt-4o").
            prompt_text: The main prompt text for the LLM.
            system_prompt_text: Optional system prompt text.
            request_identifier: An identifier for logging purposes (e.g., power name + request type).

        Returns:
            The text response from the LLM.

        Raises:
            Exception: Propagates exceptions from the llm.get_async_model or model.prompt calls.
        """
        
        model_id_lower = model_id.lower()
        requires_serial_access = any(model_id_lower.startswith(prefix) for prefix in SERIAL_ACCESS_PREFIXES)
        
        serialization_enabled = os.environ.get(SERIALIZE_LOCAL_LLMS_ENV_VAR, "false").lower() == "true"
        
        should_use_lock = requires_serial_access and serialization_enabled
        lock_acquired_here = False
        
        # Prepare model instance (can raise llm.UnknownModelError)
        try:
            model_obj = llm.get_async_model(model_id)
        except llm.UnknownModelError as e:
            logger.error(f"[{request_identifier}] Unknown model_id '{model_id}': {e}")
            raise # Re-raise to be handled by the caller
        except Exception as e:
            logger.error(f"[{request_identifier}] Unexpected error getting model '{model_id}': {e}")
            raise # Re-raise to be handled by the caller

        try:
            if should_use_lock:
                logger.debug(f"[{request_identifier}] LLM call to '{model_id}' waiting for serial access lock (SERIALIZE_LOCAL_LLMS enabled)...")
                await _local_llm_lock.acquire()
                lock_acquired_here = True
                logger.debug(f"[{request_identifier}] LLM call to '{model_id}' acquired serial access lock.")
            else:
                if requires_serial_access: # Log if it's a local model but serialization is off
                    logger.debug(f"[{request_identifier}] LLM call to '{model_id}' proceeding concurrently (SERIALIZE_LOCAL_LLMS not enabled or not 'true').")
                # For non-local models, no special logging here, just proceed.

            logger.debug(f"[{request_identifier}] Sending prompt to '{model_id}'. System prompt length: {len(system_prompt_text) if system_prompt_text else 0}. Prompt length: {len(prompt_text)}")
            
            response_obj = await model_obj.prompt(prompt_text, system=system_prompt_text)
            llm_response_text = await response_obj.text()
            
            logger.debug(f"[{request_identifier}] Received response from '{model_id}'. Response length: {len(llm_response_text)}")
            return llm_response_text
            
        except Exception as e:
            # Log the error with context
            logger.error(f"[{request_identifier}] Error during LLM request to '{model_id}': {type(e).__name__}: {e}", exc_info=True)
            # Propagate the error to the caller to handle (e.g., log with log_llm_response, return fallback)
            raise
        finally:
            if lock_acquired_here and _local_llm_lock.locked():
                _local_llm_lock.release()
                logger.debug(f"[{request_identifier}] LLM call to '{model_id}' released serial access lock.")

if __name__ == '__main__':
    # Example Usage (requires 'llm' library and potentially an LLM server like Ollama)
    
    # Configure basic logging for the example
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    async def run_example():
        coordinator = LocalLLMCoordinator()

        # --- Test Case 1: Ollama model with serialization (set env var manually if needed) ---
        # Ensure Ollama is running and has 'llama3' model: `ollama pull llama3`
        # For this test to show locking, you might need to run multiple tasks concurrently.
        # Environment variable for serialization:
        # In your terminal: export SERIALIZE_LOCAL_LLMS="true"
        # Or, for testing within Python:
        os.environ[SERIALIZE_LOCAL_LLMS_ENV_VAR] = "true" 
        logger.info(f"'{SERIALIZE_LOCAL_LLMS_ENV_VAR}' is set to: {os.environ.get(SERIALIZE_LOCAL_LLMS_ENV_VAR)}")

        ollama_model_id = "ollama/llama3" 
        # A very short system prompt just for testing
        # Using a more complex system prompt might be useful for real tests
        # but this one is just for the coordinator.
        test_system_prompt = "You are a helpful assistant." 
        test_prompt_1 = "What is the capital of France?"
        test_prompt_2 = "Briefly explain asynchronous programming."

        try:
            logger.info(f"--- Test Case 1: Ollama with Serialization ({ollama_model_id}) ---")
            
            # Create tasks to run concurrently
            task1 = coordinator.request(ollama_model_id, test_prompt_1, test_system_prompt, "OllamaTest-1")
            task2 = coordinator.request(ollama_model_id, test_prompt_2, test_system_prompt, "OllamaTest-2")
            
            response1, response2 = await asyncio.gather(task1, task2, return_exceptions=True)

            if isinstance(response1, Exception):
                logger.error(f"OllamaTest-1 failed: {response1}")
            else:
                logger.info(f"OllamaTest-1 Response: {response1[:100]}...")

            if isinstance(response2, Exception):
                logger.error(f"OllamaTest-2 failed: {response2}")
            else:
                logger.info(f"OllamaTest-2 Response: {response2[:100]}...")

        except llm.UnknownModelError:
            logger.warning(f"Skipping Ollama test: Model '{ollama_model_id}' not found or Ollama not running.")
        except Exception as e:
            logger.error(f"An error occurred during Ollama test: {e}")
        
        # --- Test Case 2: Non-serialized model (e.g., a dummy or a fast API if available) ---
        # This test uses a non-existent model prefix to ensure it bypasses the lock.
        # If you have 'llm install llm-gpt4all', you could use 'gpt4all/dummy'
        # but that requires another setup. For simplicity, using a fake one.
        # Note: This will likely fail the llm.get_async_model call, which is expected for this test.
        # The goal is to see the coordinator's logic, not necessarily a successful LLM call.
        
        # Reset env var to test non-serialized path for local models if SERIALIZE_LOCAL_LLMS was true
        os.environ[SERIALIZE_LOCAL_LLMS_ENV_VAR] = "false"
        logger.info(f"'{SERIALIZE_LOCAL_LLMS_ENV_VAR}' is reset to: {os.environ.get(SERIALIZE_LOCAL_LLMS_ENV_VAR)}")

        try:
            logger.info(f"--- Test Case 2: Ollama model with Serialization Disabled ({ollama_model_id}) ---")
            # This should run concurrently (though Ollama might still process them one-by-one internally)
            task3 = coordinator.request(ollama_model_id, "Short story about a cat.", test_system_prompt, "OllamaTest-3-NoSerialize")
            task4 = coordinator.request(ollama_model_id, "Short story about a dog.", test_system_prompt, "OllamaTest-4-NoSerialize")
            
            response3, response4 = await asyncio.gather(task3, task4, return_exceptions=True)

            if isinstance(response3, Exception):
                logger.error(f"OllamaTest-3-NoSerialize failed: {response3}")
            else:
                logger.info(f"OllamaTest-3-NoSerialize Response: {response3[:100]}...")
            if isinstance(response4, Exception):
                logger.error(f"OllamaTest-4-NoSerialize failed: {response4}")
            else:
                logger.info(f"OllamaTest-4-NoSerialize Response: {response4[:100]}...")
        
        except llm.UnknownModelError:
             logger.warning(f"Skipping Test Case 2 (Ollama non-serialized): Model '{ollama_model_id}' not found or Ollama not running.")
        except Exception as e:
            logger.error(f"An error occurred during Test Case 2: {e}")


        # --- Test Case 3: Non-local model (should bypass lock regardless of env var) ---
        # Using a dummy model ID that won't match SERIAL_ACCESS_PREFIXES
        # This will likely cause llm.UnknownModelError, which is fine for testing coordinator logic.
        # Set SERIALIZE_LOCAL_LLMS to true to ensure it's ignored for non-local models
        os.environ[SERIALIZE_LOCAL_LLMS_ENV_VAR] = "true"
        logger.info(f"'{SERIALIZE_LOCAL_LLMS_ENV_VAR}' is set to true for Test Case 3.")
        
        non_local_model_id = "gpt-dummy/test-model" 
        try:
            logger.info(f"--- Test Case 3: Non-Local Model ({non_local_model_id}) ---")
            response = await coordinator.request(non_local_model_id, "Test prompt", None, "NonLocalTest")
            logger.info(f"NonLocalTest Response: {response[:100]}...")
        except llm.UnknownModelError:
            logger.warning(f"NonLocalTest: Model '{non_local_model_id}' is unknown (expected for this test).")
        except Exception as e:
            logger.error(f"An error occurred during NonLocalTest: {e}")
        
        # Clean up env var if set for test
        if SERIALIZE_LOCAL_LLMS_ENV_VAR in os.environ:
            del os.environ[SERIALIZE_LOCAL_LLMS_ENV_VAR]

    asyncio.run(run_example())
    logger.info("llm_coordinator.py example usage complete.")
