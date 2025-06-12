"""
Centralized LLM coordination service.
Single entry point for all LLM calls with model pooling, serial locking, usage tracking, and retry logic.
"""

import asyncio
import os
import logging
from typing import (
    Optional,
    Dict,
    Any,
    AsyncIterator,
    List,
    Callable,
    Awaitable,
)  # Removed Union, ContextManager
from contextlib import asynccontextmanager

# Removed: import json
import sqlite3  # Added import

# Removed: import functools

import llm  # Assuming this is the llm library by Simon Willison
from llm.models import (
    Model as LLMModel,
)  # Renamed to avoid conflict, used for type hinting
from llm import Response as LLMResponse  # For type hinting

from . import constants as generic_constants  # Import constants
from . import llm_utils  # Import llm_utils

logger = logging.getLogger(__name__)

__all__ = [
    "LLMCoordinator",
    "LLMCallResult",
    "ModelPool",
    "initialize_database",
    "record_usage",
    "get_usage_stats_by_country",
    "get_total_usage_stats",
    "get_global_coordinator",  # To access the singleton instance
]

# --- New Global Components based on the provided pattern ---

DATABASE_PATH = generic_constants.LLM_USAGE_DATABASE_PATH
_local_lock = asyncio.Lock()


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
    if any(
        model_id_lower.startswith(prefix) for prefix in generic_constants.LOCAL_LLM_SERIAL_ACCESS_PREFIXES
    ):
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
            conn.execute(
                """
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
            """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS usage_game_agent ON usage (game_id, agent);")
            conn.commit()
        logger.info(f"Database initialized successfully at {DATABASE_PATH}")
    except sqlite3.Error as e:
        logger.error(f"Error initializing database {DATABASE_PATH}: {e}", exc_info=True)
        raise


initialize_database()  # Removed comment: Initialize DB on module load


async def record_usage(game_id: str, agent: str, phase: str, response: LLMResponse):
    """Records LLM token usage in the database."""
    try:
        usage_stats = await response.usage()  # Usage(input=..., output=..., details=...)
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.execute(
                "INSERT INTO usage (game_id, agent, phase, model, input, output) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    game_id,
                    agent,
                    phase,
                    response.model.model_id,
                    usage_stats.input,
                    usage_stats.output,
                ),
            )
            conn.commit()
        logger.debug(
            f"Usage recorded for {agent} in game {game_id}, phase {phase}: {usage_stats.input} in, {usage_stats.output} out for model {response.model.model_id}"
        )
    except sqlite3.Error as e:
        logger.error(f"SQLite error in record_usage: {e}", exc_info=True)
    except AttributeError as e:
        model_id_for_log = "N/A"
        if hasattr(response, "model") and response.model is not None:
            if hasattr(response.model, "model_id"):
                model_id_for_log = response.model.model_id
            else:
                model_id_for_log = "Unknown (model_id attribute missing)"
        elif hasattr(response, "model") and response.model is None:
            model_id_for_log = "N/A (response.model is None)"

        logger.error(
            f"Error accessing response attributes in record_usage (model: {model_id_for_log}): {e}",
            exc_info=True,
        )
    except Exception as e:
        logger.error(f"Unexpected error in record_usage: {e}", exc_info=True)


def get_usage_stats_by_country(game_id: str) -> Dict[str, Dict[str, int]]:
    """Get API usage statistics by country for a specific game."""
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.execute(
                """
                SELECT agent, 
                       COUNT(*) as api_calls,
                       SUM(input) as total_input_tokens,
                       SUM(output) as total_output_tokens,
                       model
                FROM usage 
                WHERE game_id = ? 
                GROUP BY agent, model
                ORDER BY agent
            """,
                (game_id,),
            )

            results = {}
            for row in cursor.fetchall():
                agent, api_calls, input_tokens, output_tokens, model = row
                if agent not in results:
                    results[agent] = {
                        "api_calls": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "models": [],
                    }
                results[agent]["api_calls"] += api_calls
                results[agent]["input_tokens"] += input_tokens or 0
                results[agent]["output_tokens"] += output_tokens or 0
                if model not in results[agent]["models"]:
                    results[agent]["models"].append(model)

            return results
    except sqlite3.Error as e:
        logger.error(f"Error getting usage stats: {e}", exc_info=True)
        return {}


def get_total_usage_stats(game_id: str) -> Dict[str, int]:
    """Get total API usage statistics for a specific game."""
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.execute(
                """
                SELECT COUNT(*) as total_api_calls,
                       SUM(input) as total_input_tokens,
                       SUM(output) as total_output_tokens
                FROM usage 
                WHERE game_id = ?
            """,
                (game_id,),
            )

            row = cursor.fetchone()
            if row:
                return {
                    "total_api_calls": row[0],
                    "total_input_tokens": row[1] or 0,
                    "total_output_tokens": row[2] or 0,
                }
            return {
                "total_api_calls": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
            }
    except sqlite3.Error as e:
        logger.error(f"Error getting total usage stats: {e}", exc_info=True)
        return {"total_api_calls": 0, "total_input_tokens": 0, "total_output_tokens": 0}


async def llm_call_internal(
    game_id: str,
    agent_name: str,
    phase_str: str,
    model_id: str,
    prompt: str,
    system_prompt: Optional[str] = None,
    verbose_llm_debug: bool = False,
    **kwargs: Any,
) -> str:
    """
    Internal wrapper for LLM calls incorporating model pooling, serial locking, and usage recording.
    """
    # If running under pytest, return a mock response to avoid actual LLM calls,
    # unless a specific environment variable is set to allow it for certain tests.
    if "PYTEST_CURRENT_TEST" in os.environ and not os.environ.get("ALLOW_LLM_CALLS_IN_TEST"):
        logger.warning(
            f"PYTEST_CURRENT_TEST detected. Skipping actual LLM call for {model_id} and returning a mock response."
        )
        # This is a simplified mock response.
        # In a real scenario, you might want more control over this mock from the test itself.
        return '{"analysis": "mock analysis", "orders": []}'

    try:
        model_obj = ModelPool.get(model_id)

        prompt_options: Dict[str, Any] = {}
        if system_prompt:
            prompt_options["system"] = system_prompt
        prompt_options.update(kwargs)  # Ensure kwargs are included

        # Added verbose logging for prompt
        if verbose_llm_debug:
            logger.info(f"[LLM Call - {agent_name} @ {phase_str}] System Prompt: {system_prompt!r}")
            logger.info(f"[LLM Call - {agent_name} @ {phase_str}] User Prompt: {prompt!r}")

        async with serial_if_local(model_id):  # Use the new async context manager
            response_obj: LLMResponse = await model_obj.prompt(
                prompt,
                **prompt_options,  # kwargs are now in prompt_options
            )
            response_text = await response_obj.text()
            # Added verbose logging for raw response
            if verbose_llm_debug:
                logger.info(f"[LLM Resp - {agent_name} @ {phase_str}] Raw Response: {response_text!r}")
            asyncio.create_task(
                record_usage(game_id, agent_name, phase_str, response_obj)
            )  # Record usage as a background task
        return response_text
    except Exception as e:
        logger.error(
            f"Error in llm_call_internal for model {model_id} ({agent_name}, {phase_str}): {e}",
            exc_info=True,
        )
        raise


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
        error_message: str = generic_constants.LLM_CALL_RESULT_ERROR_NOT_INITIALIZED,
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


class LLMCoordinator:
    """
    Coordinates requests to LLMs, incorporating model pooling, serial access for local models,
    and usage tracking. Single entry point for all LLM interactions.
    """

    def __init__(self):
        """Initialize the LLM coordinator."""
        logger.info("LLMCoordinator initialized.")

    async def call_text(
        self,
        prompt: str,
        *,
        model_id: str,
        agent_id: str,
        game_id: str = generic_constants.DEFAULT_GAME_ID,
        phase: str = generic_constants.DEFAULT_PHASE_NAME,
        system_prompt: Optional[str] = None,
        llm_caller_override: Optional[Callable[..., Awaitable[str]]] = None,
        verbose_llm_debug: bool = False,
    ) -> str:
        """
        Simple text completion call.

        Args:
            prompt: The prompt text
            model_id: LLM model identifier
            agent_id: Agent identifier for tracking
            game_id: Game identifier for tracking
            phase: Game phase for tracking
            system_prompt: Optional system prompt
            llm_caller_override: Optional override for the LLM call logic.
            verbose_llm_debug: Optional flag for verbose LLM call debugging.

        Returns:
            The raw text response
        """
        if llm_caller_override:
            return await llm_caller_override(
                game_id=game_id,
                agent_name=agent_id,
                phase_str=phase,
                model_id=model_id,
                prompt=prompt,
                system_prompt=system_prompt,
            )
        else:
            return await llm_call_internal(
                game_id=game_id,
                agent_name=agent_id,
                phase_str=phase,
                model_id=model_id,
                prompt=prompt,
                system_prompt=system_prompt,
                verbose_llm_debug=verbose_llm_debug,
            )

    async def call_json(
        self,
        prompt: str,
        *,
        model_id: str,
        agent_id: str,
        game_id: str = generic_constants.DEFAULT_GAME_ID,
        phase: str = generic_constants.DEFAULT_PHASE_NAME,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        expected_fields: Optional[List[str]] = None,
        llm_caller_override: Optional[Callable[..., Awaitable[str]]] = None,
        verbose_llm_debug: bool = False,  # Added verbose_llm_debug
    ) -> Dict[str, Any]:
        """
        JSON completion call with parsing and validation.

        Args:
            prompt: The prompt text
            model_id: LLM model identifier
            agent_id: Agent identifier for tracking
            game_id: Game identifier for tracking
            phase: Game phase for tracking
            system_prompt: Optional system prompt
            tools: Optional tool definitions for MCP-capable models
            expected_fields: Optional list of required JSON fields
            llm_caller_override: Optional override for the LLM call logic.
            verbose_llm_debug: Optional flag for verbose LLM call debugging

        Returns:
            Parsed JSON response

        Raises:
            ValueError: If JSON parsing fails or required fields are missing
        """
        # TODO: Implement tool calling logic for MCP in Stage 3
        if tools:
            logger.debug(f"Tools provided but MCP not yet implemented: {len(tools)} tools")

        result = await self.call_llm_with_json_parsing(
            model_id=model_id,
            prompt=prompt,
            system_prompt=system_prompt,
            game_id=game_id,
            agent_name=agent_id,
            phase_str=phase,
            expected_json_fields=expected_fields,
            llm_caller_override=llm_caller_override,
            verbose_llm_debug=verbose_llm_debug,  # Pass it down
        )

        if not result.success:
            raise ValueError(f"LLM call failed: {result.error_message}")

        return result.parsed_json or {}

    async def call_llm_with_json_parsing(
        self,
        model_id: str,
        prompt: str,
        game_id: str,
        agent_name: str,
        phase_str: str,
        system_prompt: Optional[str] = None,
        request_identifier: str = generic_constants.LLM_CALL_REQUEST_ID_DEFAULT,
        expected_json_fields: Optional[list] = None,
        response_type: str = generic_constants.LLM_CALL_LOG_RESPONSE_TYPE_DEFAULT,
        log_to_file_path: Optional[str] = None,
        llm_caller_override: Optional[Callable[..., Awaitable[str]]] = None,
        verbose_llm_debug: bool = False,
    ) -> LLMCallResult:
        """
        Internal method for LLM calls with JSON parsing.
        Used by call_json().
        """
        # llm_utils is already imported at the top of the file
        # from .llm_utils import log_llm_response # log_llm_response is part of llm_utils

        result = LLMCallResult("", None, False, generic_constants.LLM_CALL_RESULT_ERROR_NOT_INITIALIZED)

        try:
            logger.info(
                f"[{request_identifier}] Preparing LLM call. "
                f"Game: {game_id}, Agent: {agent_name}, Phase: {phase_str}, Model: {model_id}"
            )

            if llm_caller_override:
                raw_response = await llm_caller_override(
                    game_id=game_id,
                    agent_name=agent_name,
                    phase_str=phase_str,
                    model_id=model_id,
                    prompt=prompt,
                    system_prompt=system_prompt,
                )
            else:
                raw_response = await llm_call_internal(
                    game_id=game_id,
                    agent_name=agent_name,
                    phase_str=phase_str,
                    model_id=model_id,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    verbose_llm_debug=verbose_llm_debug,  # Pass verbose_llm_debug
                )

            result.raw_response = raw_response

            if raw_response and raw_response.strip():
                try:
                    parsed_data = llm_utils.extract_json_from_text(
                        raw_response, logger, f"[{request_identifier}] JSON Parsing"
                    )
                    result.parsed_json = parsed_data
                    result.success = True
                    result.error_message = ""

                    # Validate expected fields if provided
                    if expected_json_fields and isinstance(parsed_data, dict):
                        missing_fields = [field for field in expected_json_fields if field not in parsed_data]
                        if missing_fields:
                            result.success = False
                            result.error_message = f"Missing expected fields: {missing_fields}"

                except Exception as e:
                    logger.error(
                        f"[{request_identifier}] JSON parsing failed: {e}",
                        exc_info=True,
                    )
                    result.success = False
                    result.error_message = f"JSON parsing error: {e}"
            else:
                result.success = False
                result.error_message = generic_constants.LLM_CALL_ERROR_EMPTY_RESPONSE

        except Exception as e:
            logger.error(f"[{request_identifier}] LLM call failed: {e}", exc_info=True)
            result.success = False
            result.error_message = f"LLM call error: {e}"
            if not result.raw_response:
                result.raw_response = f"Error: {e}"

        # Log the full prompt/response to file if path provided
        if log_to_file_path and agent_name and phase_str:
            success_status = "TRUE" if result.success else f"FALSE: {result.error_message}"
            # Use the imported llm_utils.log_llm_response
            llm_utils.log_llm_response(
                log_file_path=log_to_file_path,
                model_name=model_id,
                agent_id=agent_name,  # Changed from power_name to agent_id
                phase=phase_str,
                response_type=response_type,
                # raw_input_prompt=prompt, # Not logged by the new function
                raw_response=result.raw_response,
                parsed_response=result.parsed_json,
                success=success_status,
                request_identifier=request_identifier,  # Pass request_identifier
                # turn_number can be added if available here, e.g. from game_id or phase_str parsing
            )

        return result

    async def request(
        self,
        model_id: str,
        prompt_text: str,
        system_prompt_text: Optional[str],
        # New parameters for llm_call_internal
        game_id: str,
        agent_name: str,  # Was implicitly part of request_identifier before, now explicit
        phase_str: str,  # New explicit parameter
        request_identifier: str = generic_constants.LLM_CALL_REQUEST_ID_DEFAULT,  # For coordinator's logging
        llm_caller_override: Optional[Callable[..., Awaitable[str]]] = None,
        verbose_llm_debug: bool = False,
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
            llm_caller_override: Optional override for the LLM call logic.
            verbose_llm_debug: Optional flag for verbose LLM call debugging.

        Returns:
            The text response from the LLM.

        Raises:
            Exception: Propagates exceptions from llm_call_internal.
        """
        logger.debug(
            f"[{request_identifier}] LLMCoordinator.request initiated. Model: {model_id}, Game: {game_id}, Agent: {agent_name}, Phase: {phase_str}"
        )
        logger.debug(
            f"[LLMCoordinator] Using model_id: {model_id}, system_prompt: {'Yes' if system_prompt_text else 'No'}"
        )
        logger.debug(f"[LLMCoordinator] Prompt (first 200 chars): {prompt_text[:200]}...")

        try:
            if llm_caller_override:
                response_text = await llm_caller_override(
                    game_id=game_id,
                    agent_name=agent_name,
                    phase_str=phase_str,
                    model_id=model_id,
                    prompt=prompt_text,
                    system_prompt=system_prompt_text,
                )
            else:
                response_text = await llm_call_internal(
                    game_id=game_id,
                    agent_name=agent_name,
                    phase_str=phase_str,
                    model_id=model_id,
                    prompt=prompt_text,
                    system_prompt=system_prompt_text,
                    verbose_llm_debug=verbose_llm_debug,
                )

            logger.info(
                f"[{request_identifier}] LLM call for {model_id} (Game: {game_id}, Agent: {agent_name}) succeeded via llm_call_internal."
            )
            logger.debug(
                f"[{request_identifier}] Received response from '{model_id}'. Response length: {len(response_text)}"
            )
            return response_text

        except Exception as e:
            logger.error(
                f"[{request_identifier}] LLM call for {model_id} failed: {e}",
                exc_info=True,
            )
            raise

    def get_model(self, model_id: str) -> LLMModel:  # Renamed from get_model_for_power
        """
        Retrieves a model instance from the pool.

        Args:
            model_id: The ID of the model to retrieve.

        Returns:
            An instance of the LLM model.
        """
        logger.debug(f"Getting model {model_id} via coordinator.")
        return ModelPool.get(model_id)

    # execute_llm_call method removed as it was a simple wrapper for request


# Initialize database on module load
initialize_database()

# Global coordinator instance
_global_coordinator = LLMCoordinator()


def get_global_coordinator() -> LLMCoordinator:
    """Returns the global singleton instance of LLMCoordinator."""
    return _global_coordinator
