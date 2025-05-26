import asyncio
import os
import logging
from typing import Optional, Dict, Any, Union, ContextManager, AsyncIterator
from contextlib import asynccontextmanager
import json
import sqlite3 # Added import
import functools # Added import

import llm # Assuming this is the llm library by Simon Willison
from llm.models import Model as LLMModel # Renamed to avoid conflict, used for type hinting
from llm import Response as LLMResponse # For type hinting

logger = logging.getLogger(__name__)

# --- New Global Components based on the provided pattern ---

DATABASE_PATH = "ai_diplomacy_usage.db"
_local_lock = asyncio.Lock() # Global lock for local LLM engines

class ModelPool:
    """Caches LLM model instances."""
    _cache: Dict[str, LLMModel] = {}

    @classmethod
    def get(cls, model_id: str) -> LLMModel:
        """Retrieves a model from the cache, loading if not present."""
        if model_id not in cls._cache:
            logger.debug(f"[ModelPool] Loading and caching model: {model_id}")
            cls._cache[model_id] = llm.get_async_model(model_id)
        else:
            logger.debug(f"[ModelPool] Retrieving model from cache: {model_id}")
        return cls._cache[model_id]

@asynccontextmanager
async def serial_if_local(model_id: str) -> AsyncIterator[None]:
    """
    Context manager to serialize access to local LLMs (ollama, llamacpp).
    """
    model_id_lower = model_id.lower()
    # Case-insensitive check will be applied to these prefixes
    # These prefixes are taken from the original SERIAL_ACCESS_PREFIXES
    if any(model_id_lower.startswith(prefix) for prefix in ["ollama/", "llamacpp/"]):
        logger.debug(f"Acquiring lock for local model: {model_id}")
        async with _local_lock:
            logger.debug(f"Lock acquired for local model: {model_id}")
            yield
            logger.debug(f"Lock released for local model: {model_id}")
    else:
        yield

def initialize_database():
    """Initializes the SQLite database and creates the 'usage' table if it doesn't exist."""
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
            CREATE TABLE IF NOT EXISTS usage (
              id          INTEGER PRIMARY KEY,
              game_id     TEXT,
              agent       TEXT,
              phase       TEXT,
              model       TEXT,
              input       INTEGER,
              output      INTEGER,
              ts          DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS usage_game_agent ON usage (game_id, agent);")
            conn.commit()
        logger.info(f"Database initialized successfully at {DATABASE_PATH}")
    except sqlite3.Error as e:
        logger.error(f"Error initializing database {DATABASE_PATH}: {e}", exc_info=True)
        raise

initialize_database() # Initialize DB on module load

async def record_usage(game_id: str, agent: str, phase: str, response: LLMResponse):
    """Records LLM token usage in the database."""
    try:
        usage_stats = await response.usage() # Usage(input=..., output=..., details=...)
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.execute(
                "INSERT INTO usage (game_id, agent, phase, model, input, output) VALUES (?, ?, ?, ?, ?, ?)",
                (game_id, agent, phase, response.model.model_id, usage_stats.input, usage_stats.output)
            )
            conn.commit()
        logger.debug(f"Usage recorded for {agent} in game {game_id}, phase {phase}: {usage_stats.input} in, {usage_stats.output} out for model {response.model.model_id}")
    except sqlite3.Error as e:
        logger.error(f"SQLite error in record_usage: {e}", exc_info=True)
    except AttributeError as e:
        logger.error(f"Error accessing response attributes in record_usage (model: {response.model.model_id if hasattr(response, 'model') else 'N/A'}): {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error in record_usage: {e}", exc_info=True)

def get_usage_stats_by_country(game_id: str) -> Dict[str, Dict[str, int]]:
    """Get API usage statistics by country for a specific game."""
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.execute("""
                SELECT agent, 
                       COUNT(*) as api_calls,
                       SUM(input) as total_input_tokens,
                       SUM(output) as total_output_tokens,
                       model
                FROM usage 
                WHERE game_id = ? 
                GROUP BY agent, model
                ORDER BY agent
            """, (game_id,))
            
            results = {}
            for row in cursor.fetchall():
                agent, api_calls, input_tokens, output_tokens, model = row
                if agent not in results:
                    results[agent] = {
                        'api_calls': 0,
                        'input_tokens': 0,
                        'output_tokens': 0,
                        'models': []
                    }
                results[agent]['api_calls'] += api_calls
                results[agent]['input_tokens'] += input_tokens or 0
                results[agent]['output_tokens'] += output_tokens or 0
                if model not in results[agent]['models']:
                    results[agent]['models'].append(model)
            
            return results
    except sqlite3.Error as e:
        logger.error(f"Error getting usage stats: {e}", exc_info=True)
        return {}

def get_total_usage_stats(game_id: str) -> Dict[str, int]:
    """Get total API usage statistics for a specific game."""
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) as total_api_calls,
                       SUM(input) as total_input_tokens,
                       SUM(output) as total_output_tokens
                FROM usage 
                WHERE game_id = ?
            """, (game_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'total_api_calls': row[0],
                    'total_input_tokens': row[1] or 0,
                    'total_output_tokens': row[2] or 0
                }
            return {'total_api_calls': 0, 'total_input_tokens': 0, 'total_output_tokens': 0}
    except sqlite3.Error as e:
        logger.error(f"Error getting total usage stats: {e}", exc_info=True)
        return {'total_api_calls': 0, 'total_input_tokens': 0, 'total_output_tokens': 0}

async def llm_call_internal(
    game_id: str,
    agent_name: str,
    phase_str: str,
    model_id: str,
    prompt: str,
    system_prompt: Optional[str] = None,
    **kwargs: Any
) -> str:
    """
    Internal wrapper for LLM calls incorporating model pooling, serial locking, and usage recording.
    """
    model_obj = ModelPool.get(model_id)
    
    prompt_options: Dict[str, Any] = {}
    if system_prompt:
        prompt_options['system'] = system_prompt
    prompt_options.update(kwargs)

    async with serial_if_local(model_id):
        response_obj = model_obj.prompt(prompt, **prompt_options)
        
        # Ensure we wait for the text to be fully generated.
        response_text = await response_obj.text()
        
        # Record usage after getting the response (fire-and-forget)
        asyncio.create_task(record_usage(game_id, agent_name, phase_str, response_obj))
        
        return response_text

# --- End of New Global Components ---

# _local_llm_lock = asyncio.Lock() # Removed, use _local_lock

# Case-insensitive check will be applied to these prefixes
# SERIAL_ACCESS_PREFIXES = ["ollama/", "llamacpp/"] # Removed
# SERIALIZE_LOCAL_LLMS_ENV_VAR = "SERIALIZE_LOCAL_LLMS" # Removed


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
    Coordinates requests to LLMs, incorporating model pooling, serial access for local models,
    and usage tracking.
    """

    def __init__(self):
        """
        Initializes the LocalLLMCoordinator.
        Database initialization is handled at the module level.
        """
        logger.info("LocalLLMCoordinator initialized.")
        # Initialization of DB is now at module level.
        pass

    # serial_access context manager removed, replaced by global serial_if_local

    # _single_llm_call method removed

    # call_llm_with_retry method removed

    async def call_llm_with_json_parsing(
        self,
        model_id: str,
        prompt: str,
        # Parameters for new llm_call_internal (non-default)
        game_id: str,
        agent_name: str, # Was power_name
        phase_str: str,    # Was phase
        # Optional parameters (with defaults)
        system_prompt: Optional[str] = None,
        request_identifier: str = "request", # Primarily for coordinator's own logging
        expected_json_fields: Optional[list] = None,
        response_type: str = "llm_call", # For file logging
        log_to_file_path: Optional[str] = None # Path for logging full prompt/response to file
    ) -> LLMCallResult:
        """
        Makes an LLM call using the new internal wrapper, then parses for JSON.
        Logs full prompt/response to a file if path provided, token usage logged to DB.
        
        Args:
            model_id: LLM model identifier
            prompt: The main prompt text
            system_prompt: Optional system prompt
            request_identifier: Identifier for coordinator's internal logging
            expected_json_fields: List of expected JSON field names for validation
            game_id: Game identifier for DB logging
            agent_name: Agent/Power name for DB logging
            phase_str: Game phase for DB logging
            response_type: Type of response for file logging
            log_to_file_path: Optional path for file logging the full transaction
            
        Returns:
            LLMCallResult with parsed data or error information
        """
        from . import llm_utils  # Import here to avoid circular imports
        from .utils import log_llm_response # Assuming this is still used for file logging
        
        result = LLMCallResult("", None, False, "Not initialized")
        
        try:
            logger.info(f"[{request_identifier}] Preparing LLM call. Game: {game_id}, Agent: {agent_name}, Phase: {phase_str}, Model: {model_id}")
            raw_response = await llm_call_internal(
                game_id=game_id,
                agent_name=agent_name,
                phase_str=phase_str,
                model_id=model_id,
                prompt=prompt,
                system_prompt=system_prompt
                # Any additional **kwargs for model.prompt() could be passed here if needed
            )
            
            result.raw_response = raw_response
            
            if raw_response and raw_response.strip():
                try:
                    # Parse JSON using the existing utility
                    parsed_data = llm_utils.extract_json_from_text(
                        raw_response, logger, f"[{request_identifier}] JSON Parsing"
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
                    logger.error(f"[{request_identifier}] JSON parsing failed: {e}", exc_info=True)
                    result.success = False
                    result.error_message = f"JSON parsing error: {e}"
            else:
                result.success = False
                result.error_message = "Empty or no response from LLM"
                
        except Exception as e:
            logger.error(f"[{request_identifier}] LLM call via llm_call_internal failed: {e}", exc_info=True)
            result.success = False
            result.error_message = f"LLM call error: {e}"
            if not result.raw_response: # Ensure raw_response has error if call failed early
                result.raw_response = f"Error: {e}"
        
        # Log the full prompt/response to file if path provided
        if log_to_file_path and agent_name and phase_str: # Changed power_name to agent_name
            success_status = "TRUE" if result.success else f"FALSE: {result.error_message}"
            # Assuming log_llm_response is compatible with these params
            log_llm_response(
                log_file_path=log_to_file_path,
                model_name=model_id,
                power_name=agent_name, # Pass agent_name as power_name
                phase=phase_str,       # Pass phase_str as phase
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
        # New parameters for llm_call_internal
        game_id: str,
        agent_name: str, # Was implicitly part of request_identifier before, now explicit
        phase_str: str,    # New explicit parameter
        request_identifier: str = "request" # For coordinator's logging
    ) -> str:
        """
        Makes a request to the specified LLM using the new internal wrapper.
        Handles model pooling, serial locking for local models, and DB-based usage logging.

        Args:
            model_id: The ID of the LLM to use (e.g., "ollama/llama3", "gpt-4o").
            prompt_text: The main prompt text for the LLM.
            system_prompt_text: Optional system prompt text.
            game_id: Game identifier for DB logging and context.
            agent_name: Agent/Power name for DB logging and context.
            phase_str: Game phase for DB logging and context.
            request_identifier: An identifier for the coordinator's logging purposes.

        Returns:
            The text response from the LLM.

        Raises:
            Exception: Propagates exceptions from llm_call_internal.
        """
        logger.debug(f"[{request_identifier}] LLMCoordinator.request initiated. Model: {model_id}, Game: {game_id}, Agent: {agent_name}, Phase: {phase_str}")
        logger.debug(f"[LLMCoordinator] Using model_id: {model_id}, system_prompt: {'Yes' if system_prompt_text else 'No'}")
        logger.debug(f"[LLMCoordinator] Prompt (first 200 chars): {prompt_text[:200]}...")
        
        try:
            response_text = await llm_call_internal(
                game_id=game_id,
                agent_name=agent_name,
                phase_str=phase_str,
                model_id=model_id,
                prompt=prompt_text,
                system_prompt=system_prompt_text
            )
            
            logger.info(f"[{request_identifier}] LLM call for {model_id} (Game: {game_id}, Agent: {agent_name}) succeeded via llm_call_internal.")
            logger.debug(f"[{request_identifier}] Received response from '{model_id}'. Response length: {len(response_text)}")
            return response_text
            
        except Exception as e:
            logger.error(f"[{request_identifier}] Error during LLM request via llm_call_internal to '{model_id}' (Game: {game_id}, Agent: {agent_name}): {type(e).__name__}: {e}", exc_info=True)
            raise

    async def get_model(self, model_id: str) -> LLMModel: # Renamed from get_model_for_power
        """Retrieves an LLM model instance using the ModelPool."""
        # power_name argument removed as ModelPool is global
        logger.debug(f"Requesting model: {model_id} via ModelPool")
        try:
            model_obj = ModelPool.get(model_id)
            logger.debug(f"Successfully retrieved model: {model_id} from ModelPool")
            return model_obj
        except Exception as e:
            logger.error(f"Failed to get model {model_id} via ModelPool: {e}", exc_info=True)
            raise

    # execute_llm_call method removed as it was a simple wrapper for request

if __name__ == '__main__':
    # Example Usage (requires 'llm' library and potentially an LLM server like Ollama)
    
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    async def run_example():
        coordinator = LocalLLMCoordinator()

        # Define common parameters for example calls
        example_game_id = "test_game_001"
        example_phase_str = "S1901M"
        
        ollama_model_id = "ollama/llama3" 
        # If 'ollama/llama3' is not available, ollama tests will show UnknownModelError from ModelPool
        
        test_system_prompt = "You are a concise and helpful assistant."
        test_prompt_1 = "What is the capital of France? Respond in one word."
        test_prompt_2 = "Briefly explain asynchronous programming in Python."

        # --- Test Case 1: Ollama model calls (will be serialized by serial_if_local) ---
        try:
            logger.info(f"--- Test Case 1: Concurrent Ollama calls ({ollama_model_id}) ---")
            
            task1 = coordinator.request(
                model_id=ollama_model_id, 
                prompt_text=test_prompt_1, 
                system_prompt_text=test_system_prompt, 
                game_id=example_game_id, 
                agent_name="AgentFrance", 
                phase_str=example_phase_str,
                request_identifier="OllamaTest-1"
            )
            task2 = coordinator.request(
                model_id=ollama_model_id, 
                prompt_text=test_prompt_2, 
                system_prompt_text=test_system_prompt, 
                game_id=example_game_id, 
                agent_name="AgentGermany", 
                phase_str=example_phase_str,
                request_identifier="OllamaTest-2"
            )
            
            # Results will be exceptions if llm.get_async_model fails (e.g. model not found)
            response1, response2 = await asyncio.gather(task1, task2, return_exceptions=True)

            if isinstance(response1, Exception):
                logger.error(f"OllamaTest-1 failed: {response1}")
            else:
                logger.info(f"OllamaTest-1 Response: {response1[:150]}...")

            if isinstance(response2, Exception):
                logger.error(f"OllamaTest-2 failed: {response2}")
            else:
                logger.info(f"OllamaTest-2 Response: {response2[:150]}...")

        except Exception as e: # Catching broad exceptions for llm setup issues
            logger.error(f"An error occurred during Ollama Test Case 1 (likely model not found or Ollama server issue): {e}", exc_info=True)
        
        # --- Test Case 2: Non-local model (e.g., gpt-4o-mini if configured in llm) ---
        # This will bypass the serial_if_local lock.
        # Replace with a model you have configured for 'llm' that is not ollama/llamacpp
        # For this example, we'll use a placeholder that will likely cause UnknownModelError
        # if not actually configured, demonstrating the flow.
        non_local_model_id = "gpt-4o-mini" # or "gpt-3.5-turbo" or any other non-ollama/llamacpp model
        
        try:
            logger.info(f"--- Test Case 2: Non-Local Model call ({non_local_model_id}) ---")
            # This call should not wait for the _local_lock
            response3 = await coordinator.request(
                model_id=non_local_model_id, 
                prompt_text="What is a large language model?", 
                system_prompt_text=test_system_prompt,
                game_id=example_game_id,
                agent_name="Researcher",
                phase_str="F1902M",
                request_identifier="NonLocalTest-1"
            )
            logger.info(f"NonLocalTest-1 Response: {response3[:150]}...")
        except llm.UnknownModelError:
            logger.warning(f"Test Case 2: Model '{non_local_model_id}' is unknown. This is expected if not configured with 'llm'.")
        except Exception as e:
            logger.error(f"An error occurred during Non-Local Model Test Case 2: {e}", exc_info=True)

        # --- Test Case 3: JSON Parsing Call ---
        json_prompt = "Provide a JSON object with two keys: 'city' and 'country'. For Paris and France."
        try:
            logger.info(f"--- Test Case 3: JSON Parsing with Ollama model ({ollama_model_id}) ---")
            json_result = await coordinator.call_llm_with_json_parsing(
                model_id=ollama_model_id,
                prompt=json_prompt,
                system_prompt="Respond strictly in JSON format.",
                request_identifier="JsonTest-Ollama",
                expected_json_fields=["city", "country"],
                game_id=example_game_id,
                agent_name="JsonAgent",
                phase_str="W1901A",
                response_type="json_query",
                log_to_file_path=f"{example_game_id}_json_log.txt" # Example file logging
            )
            if json_result.success:
                logger.info(f"JsonTest-Ollama Parsed JSON: {json_result.parsed_json}")
            else:
                logger.error(f"JsonTest-Ollama Failed: {json_result.error_message}. Raw: {json_result.raw_response[:150]}...")
        except Exception as e:
             logger.error(f"An error occurred during JSON Parsing Test Case 3: {e}", exc_info=True)
        
        logger.info("--- Example run finished. Check 'ai_diplomacy_usage.db' for usage logs. ---")
        logger.info("If Ollama or other models were not available, errors would be logged for those specific calls.")

    asyncio.run(run_example())
    logger.info("llm_coordinator.py example usage complete.")
