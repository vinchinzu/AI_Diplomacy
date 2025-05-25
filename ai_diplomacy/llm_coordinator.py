import asyncio
import os
import logging
from typing import Optional, Dict, Any, Union, ContextManager
from contextlib import asynccontextmanager
import json

import llm # Assuming this is the llm library by Simon Willison
from llm.models import Model # Import Model for type hinting

logger = logging.getLogger(__name__)
_local_llm_lock = asyncio.Lock()

# Case-insensitive check will be applied to these prefixes
SERIAL_ACCESS_PREFIXES = ["ollama/", "llamacpp/"] # llama.cpp server can also be hit hard
SERIALIZE_LOCAL_LLMS_ENV_VAR = "SERIALIZE_LOCAL_LLMS" # Users can set this to "true"


class LLMCallResult:
    """Structured result from an LLM call with parsing."""
    def __init__(
        self, 
        raw_response: str, 
        parsed_json: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: str = ""
    ):
        self.raw_response = raw_response
        self.parsed_json = parsed_json
        self.success = success
        self.error_message = error_message

    def get_field(self, *field_names: str) -> Optional[Any]:
        """Get the first available field from the parsed JSON."""
        if not self.parsed_json:
            return None
        
        for field_name in field_names:
            if field_name in self.parsed_json:
                return self.parsed_json[field_name]
        return None


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

    @asynccontextmanager
    async def serial_access(self, model_id: str, request_identifier: str = "request"):
        """
        Context manager for handling serial access to local LLMs.
        
        Local LLMs (ollama/, llamacpp/) are ALWAYS locked to prevent concurrent
        streaming requests that can cause EOF errors.
        
        Args:
            model_id: The ID of the LLM model
            request_identifier: Identifier for logging
            
        Usage:
            async with coordinator.serial_access(model_id, "MyAgent-Planning"):
                # Your LLM call here - lock automatically handled for local LLMs
        """
        model_id_lower = model_id.lower()
        requires_serial_access = any(model_id_lower.startswith(prefix) for prefix in SERIAL_ACCESS_PREFIXES)
        
        if requires_serial_access:
            logger.debug(f"[{request_identifier}] LLM call to '{model_id}' waiting for serial access lock (local LLM)...")
            async with _local_llm_lock:
                logger.debug(f"[{request_identifier}] LLM call to '{model_id}' acquired serial access lock.")
                yield
                logger.debug(f"[{request_identifier}] LLM call to '{model_id}' released serial access lock.")
        else:
            # Non-local models don't need the lock
            yield

    async def _single_llm_call(self, model_id: str, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Makes a single LLM call without retry logic.
        
        Args:
            model_id: The LLM model identifier
            prompt: The prompt text
            system_prompt: Optional system prompt
            
        Returns:
            The raw response text
            
        Raises:
            Exception: Any error from the LLM call
        """
        model = llm.get_async_model(model_id)
        response_obj = model.prompt(prompt, system=system_prompt)
        return await response_obj.text()

    async def call_llm_with_retry(
        self,
        model_id: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        request_identifier: str = "request",
        max_retries: int = 3
    ) -> str:
        """
        Makes an LLM call with retry logic for EOF and other transient errors.
        
        Args:
            model_id: The LLM model identifier
            prompt: The prompt text
            system_prompt: Optional system prompt
            request_identifier: Identifier for logging
            max_retries: Maximum number of retry attempts
            
        Returns:
            The raw response text
            
        Raises:
            Exception: If all retries fail
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                async with self.serial_access(model_id, request_identifier):
                    return await self._single_llm_call(model_id, prompt, system_prompt)
                    
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                # Check for recoverable errors (EOF, connection issues, etc.)
                is_recoverable = any(keyword in error_str for keyword in [
                    "unexpected eof", "eof", "connection", "timeout", "stream"
                ])
                
                if not is_recoverable or attempt == max_retries - 1:
                    # Don't retry for non-recoverable errors or on final attempt
                    logger.error(f"[{request_identifier}] LLM call failed on attempt {attempt + 1}/{max_retries}: {e}")
                    raise
                
                # Exponential backoff: 1.5s, 3s, 4.5s, etc.
                sleep_time = 1.5 * (attempt + 1)
                logger.warning(f"[{request_identifier}] LLM call failed on attempt {attempt + 1}/{max_retries} with recoverable error: {e}. Retrying in {sleep_time}s...")
                await asyncio.sleep(sleep_time)
        
        # This should never be reached due to the raise in the loop, but just in case
        raise last_error or Exception("All retries failed")

    async def call_llm_with_json_parsing(
        self,
        model_id: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        request_identifier: str = "request",
        expected_json_fields: Optional[list] = None,
        log_file_path: Optional[str] = None,
        power_name: Optional[str] = None,
        phase: Optional[str] = None,
        response_type: str = "llm_call"
    ) -> LLMCallResult:
        """
        Centralized LLM call with automatic JSON parsing and error handling.
        
        Args:
            model_id: LLM model identifier
            prompt: The main prompt text
            system_prompt: Optional system prompt
            request_identifier: Identifier for logging
            expected_json_fields: List of expected JSON field names for validation
            log_file_path: Path for logging the response
            power_name: Power name for logging
            phase: Game phase for logging
            response_type: Type of response for logging
            
        Returns:
            LLMCallResult with parsed data or error information
        """
        from . import llm_utils  # Import here to avoid circular imports
        from .utils import log_llm_response
        
        result = LLMCallResult("", None, False, "Not initialized")
        
        try:
            # Use the new retry logic instead of manual lock handling
            raw_response = await self.call_llm_with_retry(
                model_id=model_id,
                prompt=prompt,
                system_prompt=system_prompt,
                request_identifier=request_identifier
            )
            
            result.raw_response = raw_response
            
            if raw_response and raw_response.strip():
                try:
                    # Parse JSON using the existing utility
                    parsed_data = llm_utils.extract_json_from_text(
                        raw_response, logger, f"[{request_identifier}]"
                    )
                    result.parsed_json = parsed_data
                    result.success = True
                    result.error_message = ""
                    
                    # Validate expected fields if provided
                    if expected_json_fields and isinstance(parsed_data, dict):
                        missing_fields = [field for field in expected_json_fields 
                                        if field not in parsed_data]
                        if missing_fields:
                            result.success = False
                            result.error_message = f"Missing expected fields: {missing_fields}"
                    
                except Exception as e:
                    logger.error(f"[{request_identifier}] JSON parsing failed: {e}")
                    result.success = False
                    result.error_message = f"JSON parsing error: {e}"
            else:
                result.success = False
                result.error_message = "Empty or no response from LLM"
                
        except Exception as e:
            logger.error(f"[{request_identifier}] LLM call failed: {e}", exc_info=True)
            result.success = False
            result.error_message = f"LLM call error: {e}"
            if not result.raw_response:
                result.raw_response = f"Error: {e}"
        
        # Log the response if logging parameters are provided
        if log_file_path and power_name and phase:
            success_status = "TRUE" if result.success else f"FALSE: {result.error_message}"
            log_llm_response(
                log_file_path=log_file_path,
                model_name=model_id,
                power_name=power_name,
                phase=phase,
                response_type=response_type,
                raw_input_prompt=prompt,
                raw_response=result.raw_response,
                success=success_status
            )
        
        return result

    async def request(
        self, 
        model_id: str, 
        prompt_text: str, 
        system_prompt_text: Optional[str],
        request_identifier: str = "request" # For more specific logging
    ) -> str:
        """
        Makes a request to the specified LLM with automatic retry for transient errors.

        Local LLMs (ollama/, llamacpp/) are automatically serialized to prevent
        concurrent streaming requests that can cause EOF errors.

        Args:
            model_id: The ID of the LLM to use (e.g., "ollama/llama3", "gpt-4o").
            prompt_text: The main prompt text for the LLM.
            system_prompt_text: Optional system prompt text.
            request_identifier: An identifier for logging purposes (e.g., power name + request type).

        Returns:
            The text response from the LLM.

        Raises:
            Exception: Propagates exceptions from the llm.get_async_model or model.prompt calls after retries.
        """
        # Only log ENV/connection info at DEBUG level
        logger.debug(f"[LLMCoordinator] Using model_id: {model_id}, system_prompt: {system_prompt_text}")
        logger.debug(f"[LLMCoordinator] Prompt: {prompt_text[:200]}...")
        logger.debug(f"[{request_identifier}] Sending prompt to '{model_id}'. System prompt length: {len(system_prompt_text) if system_prompt_text else 0}. Prompt length: {len(prompt_text)}")
        
        try:
            # Use the new retry logic which handles lock management automatically
            response_text = await self.call_llm_with_retry(
                model_id=model_id,
                prompt=prompt_text,
                system_prompt=system_prompt_text,
                request_identifier=request_identifier
            )
            
            # Only log LLM call result at INFO level
            logger.info(f"[LLMCoordinator] LLM call for {model_id} ({request_identifier}) succeeded.")
            logger.debug(f"[{request_identifier}] Received response from '{model_id}'. Response length: {len(response_text)}")
            return response_text
            
        except Exception as e:
            # Log the error with context and re-raise
            logger.error(f"[{request_identifier}] Error during LLM request to '{model_id}': {type(e).__name__}: {e}", exc_info=True)
            raise

    async def get_model_for_power(self, power_name: str, model_id: str) -> Model:
        """Retrieves an LLM model instance."""
        logger.debug(f"[{power_name}] Requesting model: {model_id}")
        try:
            # Get model instance - let any exceptions propagate up
            model_obj = llm.get_async_model(model_id)
            logger.debug(f"[{power_name}] Successfully retrieved model: {model_id}")
            return model_obj
        except Exception as e:
            logger.error(f"[{power_name}] Failed to get model {model_id}: {e}")
            raise

    async def execute_llm_call(
        self,
        model_id: str,
        prompt_text: str,
        system_prompt_text: Optional[str],
        request_identifier: str = "request"
    ) -> str:
        """
        Executes an LLM call with the specified parameters.

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
        return await self.request(model_id, prompt_text, system_prompt_text, request_identifier)

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
