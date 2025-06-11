import pytest
import asyncio

# import sqlite3 # No longer needed here
from unittest.mock import MagicMock, AsyncMock, patch  # call might not be needed
import logging

# Assuming llm_coordinator.py is in ai_diplomacy.services
from generic_llm_framework import (  # UPDATED
    llm_coordinator,
)  # llm_coordinator module itself for patching llm.get_async_model
from generic_llm_framework.llm_coordinator import (  # UPDATED
    LLMCallResult,
    LLMCoordinator,
    ModelPool,
)
from generic_llm_framework import constants as generic_constants  # UPDATED with alias

# DB-related fixtures and tests have been moved to tests/integration/services/test_llm_coordinator_db.py


# Tests for ModelPool
@pytest.mark.unit
@patch(
    "llm.get_async_model"
)  # Patch where llm is used in llm_coordinator (now generic_llm_framework.llm_coordinator)
def test_model_pool_get_new_model(mock_get_async_model):
    mock_model_instance = MagicMock()
    mock_get_async_model.return_value = mock_model_instance

    ModelPool._cache = {}  # Ensure clean cache
    model_id = "ollama/test_model"

    retrieved_model = ModelPool.get(model_id)

    mock_get_async_model.assert_called_once_with(model_id)
    assert retrieved_model == mock_model_instance
    assert model_id in ModelPool._cache
    assert ModelPool._cache[model_id] == mock_model_instance


@pytest.mark.unit
@patch("llm.get_async_model")  # Patch where llm is used
def test_model_pool_get_cached_model(mock_get_async_model):
    mock_model_instance = MagicMock()
    model_id = "ollama/cached_model"

    ModelPool._cache = {model_id: mock_model_instance}  # Pre-populate cache

    retrieved_model = ModelPool.get(model_id)

    mock_get_async_model.assert_not_called()  # Should not be called if cached
    assert retrieved_model == mock_model_instance


# Tests for serial_if_local
@pytest.mark.unit
@pytest.mark.asyncio
async def test_serial_if_local_local_model():
    # Test with a model ID that should use the lock
    local_model_id = "ollama/llama3"
    llm_coordinator._local_lock = asyncio.Lock()  # Ensure a fresh lock for the test

    async with llm_coordinator.serial_if_local(local_model_id):
        assert llm_coordinator._local_lock.locked()
    assert not llm_coordinator._local_lock.locked()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_serial_if_local_non_local_model():
    # Test with a model ID that should NOT use the lock
    non_local_model_id = "gpt-4o"
    llm_coordinator._local_lock = asyncio.Lock()  # Ensure a fresh lock

    async with llm_coordinator.serial_if_local(non_local_model_id):
        assert not llm_coordinator._local_lock.locked()  # Lock should not be acquired
    assert not llm_coordinator._local_lock.locked()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_serial_if_local_llamacpp_model():
    local_model_id = "llamacpp/mistral"
    llm_coordinator._local_lock = asyncio.Lock()
    async with llm_coordinator.serial_if_local(local_model_id):
        assert llm_coordinator._local_lock.locked()
    assert not llm_coordinator._local_lock.locked()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_serial_if_local_case_insensitivity():
    local_model_id_upper = "OLLAMA/MIXTRAL"
    llm_coordinator._local_lock = asyncio.Lock()
    async with llm_coordinator.serial_if_local(local_model_id_upper):
        assert llm_coordinator._local_lock.locked()
    assert not llm_coordinator._local_lock.locked()


# Fixture for coordinator used by unit tests
@pytest.fixture
@pytest.mark.unit
def coordinator():
    return LLMCoordinator()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_llmcoordinator_call_text_success(coordinator):
    mock_custom_llm_caller = AsyncMock(return_value="Test response text")

    prompt = "Hello world"
    model_id = "test_model_id"
    agent_id = "test_agent"
    game_id = "test_game"
    phase = "test_phase"
    system_prompt = "System instructions"

    response = await coordinator.call_text(
        prompt=prompt,
        model_id=model_id,
        agent_id=agent_id,
        game_id=game_id,
        phase=phase,
        system_prompt=system_prompt,
        llm_caller_override=mock_custom_llm_caller,
    )

    assert response == "Test response text"
    mock_custom_llm_caller.assert_called_once_with(
        game_id=game_id,
        agent_name=agent_id,
        phase_str=phase,
        model_id=model_id,
        prompt=prompt,
        system_prompt=system_prompt,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_llmcoordinator_call_text_default_game_phase(coordinator):
    mock_custom_llm_caller = AsyncMock(return_value="Default response")

    prompt = "Another prompt"
    model_id = "another_model"
    agent_id = "another_agent"

    # generic_constants is now imported at the top of the file

    await coordinator.call_text(
        prompt=prompt,
        model_id=model_id,
        agent_id=agent_id,
        llm_caller_override=mock_custom_llm_caller,
    )

    mock_custom_llm_caller.assert_called_once_with(
        game_id=generic_constants.DEFAULT_GAME_ID,
        agent_name=agent_id,
        phase_str=generic_constants.DEFAULT_PHASE_NAME,
        model_id=model_id,
        prompt=prompt,
        system_prompt=None,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_llmcoordinator_call_text_propagates_exception(coordinator):
    mock_custom_llm_caller = AsyncMock(side_effect=ValueError("LLM Internal Error"))

    # generic_constants is now imported at the top of the file

    with pytest.raises(ValueError, match="LLM Internal Error"):
        await coordinator.call_text(
            prompt="Error prompt",
            model_id="error_model",
            agent_id="error_agent",
            llm_caller_override=mock_custom_llm_caller,
        )

    mock_custom_llm_caller.assert_called_once_with(
        game_id=generic_constants.DEFAULT_GAME_ID,
        agent_name="error_agent",
        phase_str=generic_constants.DEFAULT_PHASE_NAME,
        model_id="error_model",
        prompt="Error prompt",
        system_prompt=None,
    )


@pytest.mark.unit
@pytest.mark.asyncio
@patch(
    "generic_llm_framework.llm_coordinator.llm_call_internal", new_callable=AsyncMock
)
async def test_llmcoordinator_call_text_uses_internal_call(
    mock_llm_call_internal, coordinator
):
    mock_llm_call_internal.return_value = "Internal response text"

    prompt = "Hello internal"
    model_id = "internal_model"
    agent_id = "internal_agent"
    game_id = "internal_game"
    phase = "internal_phase"
    system_prompt = "Internal system instructions"

    response = await coordinator.call_text(
        prompt=prompt,
        model_id=model_id,
        agent_id=agent_id,
        game_id=game_id,
        phase=phase,
        system_prompt=system_prompt,
        llm_caller_override=None,  # Explicitly None
    )

    assert response == "Internal response text"
    mock_llm_call_internal.assert_called_once_with(
        game_id=game_id,
        agent_name=agent_id,  # Note: llm_call_internal takes agent_name
        phase_str=phase,
        model_id=model_id,
        prompt=prompt,
        system_prompt=system_prompt,
    )


@pytest.mark.unit
@pytest.mark.asyncio
@patch(
    "generic_llm_framework.llm_coordinator.llm_call_internal", new_callable=AsyncMock
)
async def test_llmcoordinator_call_text_internal_call_exception(
    mock_llm_call_internal, coordinator
):
    mock_llm_call_internal.side_effect = ValueError("Internal LLM Error")

    with pytest.raises(ValueError, match="Internal LLM Error"):
        await coordinator.call_text(
            prompt="Error prompt internal",
            model_id="error_model_internal",
            agent_id="error_agent_internal",
            llm_caller_override=None,  # Explicitly None
        )

    mock_llm_call_internal.assert_called_once()
    # We can also check specific args if needed, similar to the success case
    call_args = mock_llm_call_internal.call_args[1]
    assert call_args["prompt"] == "Error prompt internal"
    assert call_args["model_id"] == "error_model_internal"
    assert call_args["agent_name"] == "error_agent_internal"
    assert call_args["game_id"] == generic_constants.DEFAULT_GAME_ID  # Check defaults
    assert (
        call_args["phase_str"] == generic_constants.DEFAULT_PHASE_NAME
    )  # Check defaults
    assert call_args["system_prompt"] is None  # Check defaults
    assert call_args["verbose_llm_debug"] is False  # Check defaults


# Tests for LLMCoordinator.call_json
@pytest.mark.unit
@pytest.mark.asyncio
@patch.object(LLMCoordinator, "call_llm_with_json_parsing", new_callable=AsyncMock)
async def test_llmcoordinator_call_json_success(
    mock_call_llm_with_json_parsing, coordinator
):
    expected_dict = {"key": "value", "orders": ["A PAR H"]}
    mock_call_llm_with_json_parsing.return_value = LLMCallResult(
        raw_response="""{"key": "value", "orders": ["A PAR H"]}""",
        parsed_json=expected_dict,
        success=True,
    )

    result = await coordinator.call_json(
        prompt="json prompt",
        model_id="json_model",
        agent_id="json_agent",
        expected_fields=["key", "orders"],
        # llm_caller_override will default to None and be passed to call_llm_with_json_parsing
    )

    assert result == expected_dict
    # generic_constants is now imported at the top of the file
    mock_call_llm_with_json_parsing.assert_called_once_with(
        model_id="json_model",
        prompt="json prompt",
        system_prompt="json system",
        game_id="json_game",
        agent_name="json_agent",
        phase_str="json_phase",
        expected_json_fields=["key"],
        llm_caller_override=None,
        verbose_llm_debug=False,
    )


@pytest.mark.unit
@pytest.mark.asyncio
@patch.object(LLMCoordinator, "call_llm_with_json_parsing", new_callable=AsyncMock)
async def test_llmcoordinator_call_json_failure_from_internal_call(
    mock_call_llm_with_json_parsing, coordinator
):
    mock_call_llm_with_json_parsing.return_value = LLMCallResult(
        raw_response="", parsed_json=None, success=False, error_message="Internal fail"
    )

    with pytest.raises(ValueError, match="LLM call failed: Internal fail"):
        await coordinator.call_json(
            prompt="json prompt_fail",
            model_id="json_model_fail",
            agent_id="json_agent_fail",
            game_id="json_game_fail",
            phase="json_phase_fail",
        )
    mock_call_llm_with_json_parsing.assert_called_once_with(
        model_id="json_model_fail",
        prompt="json prompt_fail",
        system_prompt=None,
        game_id="json_game_fail",
        agent_name="json_agent_fail",
        phase_str="json_phase_fail",
        expected_json_fields=None,
        llm_caller_override=None,
        verbose_llm_debug=False,
    )


@pytest.mark.unit
@pytest.mark.asyncio
@patch.object(LLMCoordinator, "call_llm_with_json_parsing", new_callable=AsyncMock)
async def test_llmcoordinator_call_json_parsed_is_none(
    mock_call_llm_with_json_parsing, coordinator
):
    mock_call_llm_with_json_parsing.return_value = LLMCallResult(
        raw_response="{}", parsed_json=None, success=True
    )

    response = await coordinator.call_json(
        prompt="json prompt_none",
        model_id="json_model_none",
        agent_id="json_agent_none",
        game_id="json_game_none",
        phase="json_phase_none",
    )

    assert response == {}  # Should return empty dict if parsed_json is None
    mock_call_llm_with_json_parsing.assert_called_once_with(
        model_id="json_model_none",
        prompt="json prompt_none",
        system_prompt=None,
        game_id="json_game_none",
        agent_name="json_agent_none",
        phase_str="json_phase_none",
        expected_json_fields=None,
        llm_caller_override=None,
        verbose_llm_debug=False,
    )


@pytest.mark.unit
@pytest.mark.asyncio
@patch.object(LLMCoordinator, "call_llm_with_json_parsing", new_callable=AsyncMock)
async def test_llmcoordinator_call_json_with_tools(
    mock_call_llm_with_json_parsing, coordinator, caplog
):
    mock_call_llm_with_json_parsing.return_value = LLMCallResult(
        raw_response='{"key": "value"}', parsed_json={"key": "value"}, success=True
    )

    with caplog.at_level(logging.DEBUG):
        await coordinator.call_json(
            prompt="json prompt_tools",
            model_id="json_model_tools",
            agent_id="json_agent_tools",
            tools=[{"type": "function", "function": {}}],
            verbose_llm_debug=True,
        )
    assert "Tools provided but MCP not yet implemented" in caplog.text

    args, kwargs = mock_call_llm_with_json_parsing.call_args
    assert kwargs.get("model_id") == "json_model_tools"
    assert kwargs.get("verbose_llm_debug") is True


# Tests for LLMCoordinator.call_llm_with_json_parsing
@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.llm_utils.log_llm_response")
@patch("generic_llm_framework.llm_coordinator.llm_utils.extract_json_from_text")
@patch(
    "generic_llm_framework.llm_coordinator.llm_call_internal", new_callable=AsyncMock
)
async def test_call_json_parsing_success_no_override(
    mock_llm_call_internal, mock_extract_json, mock_log_response, coordinator
):
    mock_llm_call_internal.return_value = '{"key": "value", "num": 123}'
    mock_extract_json.return_value = {"key": "value", "num": 123}
    expected_fields = ["key", "num"]

    result = await coordinator.call_llm_with_json_parsing(
        model_id="json_model_1",
        prompt="json prompt",
        expected_json_fields=expected_fields,
        agent_name="test_agent_json",
        verbose_llm_debug=True,  # Test this flag
    )

    assert result.success is True
    assert result.raw_response == '{"key": "value", "num": 123}'
    assert result.parsed_json == {"key": "value", "num": 123}
    assert result.error_message is None
    mock_llm_call_internal.assert_called_once()
    args = mock_llm_call_internal.call_args[1]
    assert args["model_id"] == "json_model_1"
    assert args["prompt"] == "json prompt"
    assert args["agent_name"] == "test_agent_json"
    assert args["verbose_llm_debug"] is True
    mock_extract_json.assert_called_once_with(
        '{"key": "value", "num": 123}', expected_fields
    )
    mock_log_response.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.llm_utils.log_llm_response")
@patch("generic_llm_framework.llm_coordinator.llm_utils.extract_json_from_text")
@patch(
    "generic_llm_framework.llm_coordinator.llm_call_internal", new_callable=AsyncMock
)  # Still need to patch to ensure it's NOT called
async def test_call_json_parsing_success_with_override(
    mock_llm_call_internal, mock_extract_json, mock_log_response, coordinator
):
    mock_override_caller = AsyncMock(return_value='{"key_override": "value_override"}')
    mock_extract_json.return_value = {"key_override": "value_override"}

    result = await coordinator.call_llm_with_json_parsing(
        model_id="json_model_override",
        prompt="json prompt override",
        llm_caller_override=mock_override_caller,
        agent_name="override_agent",
        game_id="override_game",
        phase_str="override_phase",
    )

    assert result.success is True
    assert result.raw_response == '{"key_override": "value_override"}'
    assert result.parsed_json == {"key_override": "value_override"}
    mock_llm_call_internal.assert_not_called()
    mock_override_caller.assert_called_once_with(
        model_id="json_model_override",  # Override receives all params
        prompt="json prompt override",
        system_prompt=None,
        tools=None,
        agent_name="override_agent",
        game_id="override_game",
        phase_str="override_phase",
        log_to_file_path=None,
        verbose_llm_debug=False,  # Default for this param
    )
    mock_extract_json.assert_called_once_with(
        '{"key_override": "value_override"}', None
    )  # No expected_fields
    mock_log_response.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.llm_utils.log_llm_response")
@patch("generic_llm_framework.llm_coordinator.llm_utils.extract_json_from_text")
@patch(
    "generic_llm_framework.llm_coordinator.llm_call_internal", new_callable=AsyncMock
)
async def test_call_json_parsing_missing_expected_fields(
    mock_llm_call_internal, mock_extract_json, mock_log_response, coordinator
):
    mock_llm_call_internal.return_value = '{"key": "value"}'  # "num" is missing
    mock_extract_json.return_value = {"key": "value"}
    expected_fields = ["key", "num"]

    result = await coordinator.call_llm_with_json_parsing(
        model_id="json_model_missing",
        prompt="json prompt missing",
        expected_json_fields=expected_fields,
    )

    assert result.success is False
    assert result.raw_response == '{"key": "value"}'
    assert result.parsed_json == {"key": "value"}
    assert "Missing expected JSON fields: {'num'}" in result.error_message
    mock_extract_json.assert_called_once_with('{"key": "value"}', expected_fields)
    mock_log_response.assert_called_once()  # Logged even on failure


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.llm_utils.log_llm_response")
@patch("generic_llm_framework.llm_coordinator.llm_utils.extract_json_from_text")
@patch(
    "generic_llm_framework.llm_coordinator.llm_call_internal", new_callable=AsyncMock
)
async def test_call_json_parsing_empty_response(
    mock_llm_call_internal, mock_extract_json, mock_log_response, coordinator
):
    mock_llm_call_internal.return_value = "   "  # Empty/whitespace response

    result = await coordinator.call_llm_with_json_parsing(
        model_id="json_model_empty", prompt="json prompt empty"
    )

    assert result.success is False
    assert result.raw_response == "   "
    assert result.parsed_json is None
    assert result.error_message == generic_constants.LLM_CALL_ERROR_EMPTY_RESPONSE
    mock_extract_json.assert_not_called()
    mock_log_response.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.llm_utils.log_llm_response")
@patch("generic_llm_framework.llm_coordinator.llm_utils.extract_json_from_text")
@patch(
    "generic_llm_framework.llm_coordinator.llm_call_internal", new_callable=AsyncMock
)
async def test_call_json_parsing_json_error(
    mock_llm_call_internal, mock_extract_json, mock_log_response, coordinator
):
    mock_llm_call_internal.return_value = "{not_json}"
    mock_extract_json.side_effect = ValueError("Bad JSON")

    result = await coordinator.call_llm_with_json_parsing(
        model_id="json_model_bad", prompt="json prompt bad"
    )

    assert result.success is False
    assert result.raw_response == "{not_json}"
    assert result.parsed_json is None
    assert (
        "JSON parsing failed: Bad JSON. Raw response: {not_json}"
        in result.error_message
    )
    mock_extract_json.assert_called_once_with("{not_json}", None)
    mock_log_response.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.llm_utils.log_llm_response")
@patch("generic_llm_framework.llm_coordinator.llm_utils.extract_json_from_text")
@patch(
    "generic_llm_framework.llm_coordinator.llm_call_internal", new_callable=AsyncMock
)
async def test_call_json_parsing_llm_call_exception_internal(
    mock_llm_call_internal, mock_extract_json, mock_log_response, coordinator
):
    mock_llm_call_internal.side_effect = Exception("LLM exploded")

    result = await coordinator.call_llm_with_json_parsing(
        model_id="json_model_explode", prompt="json prompt explode"
    )

    assert result.success is False
    assert result.raw_response is None
    assert result.parsed_json is None
    assert "LLM call failed: LLM exploded" in result.error_message
    mock_extract_json.assert_not_called()
    mock_log_response.assert_not_called()  # Not called if llm_call_internal fails before response


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.llm_utils.log_llm_response")
@patch("generic_llm_framework.llm_coordinator.llm_utils.extract_json_from_text")
async def test_call_json_parsing_llm_call_exception_override(
    mock_extract_json, mock_log_response, coordinator
):
    mock_override_caller = AsyncMock(side_effect=Exception("Override exploded"))

    result = await coordinator.call_llm_with_json_parsing(
        model_id="json_model_explode_override",
        prompt="json prompt explode override",
        llm_caller_override=mock_override_caller,
    )

    assert result.success is False
    assert result.raw_response is None
    assert result.parsed_json is None
    assert "LLM call failed: Override exploded" in result.error_message
    mock_extract_json.assert_not_called()
    mock_log_response.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.llm_utils.log_llm_response")
@patch("generic_llm_framework.llm_coordinator.llm_utils.extract_json_from_text")
@patch(
    "generic_llm_framework.llm_coordinator.llm_call_internal", new_callable=AsyncMock
)
async def test_call_json_parsing_log_to_file_path(
    mock_llm_call_internal, mock_extract_json, mock_log_response, coordinator
):
    mock_llm_call_internal.return_value = '{"data": "logged"}'
    mock_extract_json.return_value = {"data": "logged"}
    log_path = "/test/debug/llm_calls.log"

    await coordinator.call_llm_with_json_parsing(
        model_id="json_model_log",
        prompt="json prompt log",
        log_to_file_path=log_path,
        agent_name="log_agent",
        game_id="log_game",
        phase_str="log_phase",
        system_prompt="log_system",
    )

    mock_log_response.assert_called_once()
    log_args = mock_log_response.call_args[0]  # Positional arguments
    log_kwargs = mock_log_response.call_args[1]  # Keyword arguments

    assert log_kwargs["raw_response"] == '{"data": "logged"}'
    assert log_kwargs["parsed_response"] == {"data": "logged"}
    assert log_kwargs["model_id"] == "json_model_log"
    assert log_kwargs["prompt"] == "json prompt log"
    assert log_kwargs["system_prompt"] == "log_system"
    assert log_kwargs["agent_name"] == "log_agent"
    assert log_kwargs["game_id"] == "log_game"
    assert log_kwargs["phase"] == "log_phase"
    assert log_kwargs["log_file_path"] == log_path
    assert log_kwargs["error_message"] is None
    assert log_kwargs["expected_json_fields"] is None
    assert log_kwargs["tools"] is None


# Tests for LLMCoordinator.request
@pytest.mark.unit
@pytest.mark.asyncio
async def test_llmcoordinator_request_with_override(coordinator):
    mock_custom_llm_caller = AsyncMock(return_value="Override response for request")

    game_id = "req_game_override"
    agent_name = "req_agent_override"
    phase_str = "req_phase_override"
    model_id = "req_model_override"
    prompt_text = "Request prompt override"
    system_prompt_text = "Request system prompt override"

    response = await coordinator.request(
        game_id=game_id,
        agent_name=agent_name,
        phase_str=phase_str,
        model_id=model_id,
        prompt_text=prompt_text,
        system_prompt_text=system_prompt_text,
        llm_caller_override=mock_custom_llm_caller,
    )

    assert response == "Override response for request"
    mock_custom_llm_caller.assert_called_once_with(
        game_id=game_id,
        agent_name=agent_name,
        phase_str=phase_str,
        model_id=model_id,
        prompt=prompt_text,  # 'prompt' in the override call
        system_prompt=system_prompt_text,  # 'system_prompt' in the override call
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_llmcoordinator_request_with_override_exception(coordinator):
    mock_custom_llm_caller = AsyncMock(side_effect=ValueError("Request Override Error"))

    with pytest.raises(ValueError, match="Request Override Error"):
        await coordinator.request(
            game_id="req_game_exc",
            agent_name="req_agent_exc",
            phase_str="req_phase_exc",
            model_id="req_model_exc",
            prompt_text="Request prompt exc",
            system_prompt_text="Request system prompt exc",
            llm_caller_override=mock_custom_llm_caller,
        )
    mock_custom_llm_caller.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
@patch(
    "generic_llm_framework.llm_coordinator.llm_call_internal", new_callable=AsyncMock
)
async def test_llmcoordinator_request_uses_internal_call(
    mock_llm_call_internal, coordinator
):
    mock_llm_call_internal.return_value = "Internal response for request"

    game_id = "req_game_internal"
    agent_name = "req_agent_internal"
    phase_str = "req_phase_internal"
    model_id = "req_model_internal"
    prompt_text = "Request prompt internal"
    system_prompt_text = "Request system prompt internal"

    response = await coordinator.request(
        game_id=game_id,
        agent_name=agent_name,
        phase_str=phase_str,
        model_id=model_id,
        prompt_text=prompt_text,
        system_prompt_text=system_prompt_text,
        llm_caller_override=None,  # Explicitly None
    )

    assert response == "Internal response for request"
    mock_llm_call_internal.assert_called_once_with(
        game_id=game_id,
        agent_name=agent_name,
        phase_str=phase_str,
        model_id=model_id,
        prompt=prompt_text,
        system_prompt=system_prompt_text,
        tools=None,
        verbose_llm_debug=False,  # Default from call_text
        log_to_file_path=None,  # Default from call_text
    )


@pytest.mark.unit
@pytest.mark.asyncio
@patch(
    "generic_llm_framework.llm_coordinator.llm_call_internal", new_callable=AsyncMock
)
async def test_llmcoordinator_request_internal_call_exception(
    mock_llm_call_internal, coordinator
):
    mock_llm_call_internal.side_effect = ValueError("Request Internal LLM Error")

    with pytest.raises(ValueError, match="Request Internal LLM Error"):
        await coordinator.request(
            game_id="req_game_internal_exc",
            agent_name="req_agent_internal_exc",
            phase_str="req_phase_internal_exc",
            model_id="req_model_internal_exc",
            prompt_text="Request prompt internal exc",
            system_prompt_text="Request system prompt internal exc",
            llm_caller_override=None,
        )
    mock_llm_call_internal.assert_called_once()


# Test for LLMCoordinator.get_model
@pytest.mark.unit
@pytest.mark.asyncio
@patch(
    "generic_llm_framework.llm_coordinator.ModelPool.get"
)  # Patching ModelPool.get directly
async def test_llmcoordinator_get_model(mock_model_pool_get, coordinator):
    mock_model_instance = MagicMock(name="MockModelInstance")
    mock_model_pool_get.return_value = mock_model_instance
    model_id_to_get = "test_model_for_get_model"

    # The coordinator's get_model is synchronous, but ModelPool.get might be underlyingly async if it calls llm.get_async_model
    # However, the LLMCoordinator.get_model itself is defined as `def get_model`, not `async def`.
    # And ModelPool.get is also synchronous.
    # The actual model fetching (`llm.get_async_model`) is async, but that's handled within ModelPool.
    # So, no `await` needed for coordinator.get_model.

    retrieved_model = coordinator.get_model(model_id_to_get)

    mock_model_pool_get.assert_called_once_with(model_id_to_get)
    assert retrieved_model == mock_model_instance


# Tests for llm_call_internal free function
@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.logger")
@patch("generic_llm_framework.llm_coordinator.asyncio.create_task")
@patch("generic_llm_framework.llm_coordinator.record_usage", new_callable=AsyncMock)
@patch("generic_llm_framework.llm_coordinator.serial_if_local")
@patch("generic_llm_framework.llm_coordinator.ModelPool.get")
async def test_llm_call_internal_success_no_system_prompt_no_tools(
    mock_model_pool_get,
    mock_serial_if_local,
    mock_record_usage,
    mock_create_task,
    mock_logger,
):
    mock_model_obj = MagicMock()
    # mock_model_obj.prompt = AsyncMock(return_value=MagicMock(text="Test LLM response")) # if .text is an attribute
    # If .text is an async method:
    mock_llm_response_obj = AsyncMock()
    mock_llm_response_obj.text = AsyncMock(return_value="Test LLM response")
    mock_model_obj.prompt = AsyncMock(return_value=mock_llm_response_obj)

    mock_model_pool_get.return_value = mock_model_obj

    # Mock for serial_if_local context manager
    mock_serial_cm = AsyncMock()
    mock_serial_cm.__aenter__.return_value = None
    mock_serial_if_local.return_value = mock_serial_cm

    model_id = "test_model"
    prompt = "Test prompt"

    response_text = await llm_coordinator.llm_call_internal(
        model_id=model_id,
        prompt=prompt,
        agent_name="test_agent",
        game_id="test_game",
        phase_str="test_phase",
    )

    assert response_text == "Test LLM response"
    mock_model_pool_get.assert_called_once_with(model_id)
    mock_serial_if_local.assert_called_once_with(model_id)
    mock_model_obj.prompt.assert_called_once_with(prompt, system=None, tools=None)
    # mock_llm_response_obj.text.assert_called_once() # If .text is an async method and you want to ensure it was awaited

    # Check that record_usage was scheduled with asyncio.create_task
    mock_create_task.assert_called_once()
    # Get the first argument of the first call to create_task, which should be the record_usage coroutine
    # This is a bit tricky as the coroutine object itself is passed. We check if the mock_record_usage was the one.
    # A more robust way might be to check that mock_record_usage itself was eventually called,
    # but that requires running the event loop or more complex async testing.
    # For now, checking it was passed to create_task is a good indicator.
    assert (
        mock_create_task.call_args[0][0].__qualname__ == mock_record_usage.__qualname__
    )
    # We can also check the arguments passed to record_usage if it were called directly,
    # but since it's create_task'd, we'd need to inspect the coroutine object more deeply or await it.
    # Let's assume for now that if create_task is called with it, it's correct.
    # To actually test record_usage args, we might need to patch asyncio.create_task to run the coro immediately.


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.logger")
@patch("generic_llm_framework.llm_coordinator.asyncio.create_task")
@patch("generic_llm_framework.llm_coordinator.record_usage", new_callable=AsyncMock)
@patch("generic_llm_framework.llm_coordinator.serial_if_local")
@patch("generic_llm_framework.llm_coordinator.ModelPool.get")
async def test_llm_call_internal_success_with_system_prompt_and_tools(
    mock_model_pool_get,
    mock_serial_if_local,
    mock_record_usage,
    mock_create_task,
    mock_logger,
):
    mock_model_obj = MagicMock()
    mock_llm_response_obj = AsyncMock()
    mock_llm_response_obj.text = AsyncMock(return_value="Response with tools")
    mock_model_obj.prompt = AsyncMock(return_value=mock_llm_response_obj)
    mock_model_pool_get.return_value = mock_model_obj

    mock_serial_cm = AsyncMock()
    mock_serial_cm.__aenter__.return_value = None
    mock_serial_if_local.return_value = mock_serial_cm

    model_id = "tool_model"
    prompt = "Tool prompt"
    system_prompt = "Use tools wisely"
    tools_def = [{"type": "function", "function": {"name": "get_weather"}}]
    # llm library expects tools in a specific format for some models, llm_call_internal handles this conversion if needed.
    # For this test, we assume the format passed to model.prompt is what the underlying llm library expects.

    response_text = await llm_coordinator.llm_call_internal(
        model_id=model_id,
        prompt=prompt,
        system_prompt=system_prompt,
        tools=tools_def,
        agent_name="tool_agent",
        game_id="tool_game",
        phase_str="tool_phase",
    )

    assert response_text == "Response with tools"
    mock_model_obj.prompt.assert_called_once_with(
        prompt, system=system_prompt, tools=tools_def
    )
    mock_create_task.assert_called_once()  # record_usage scheduled


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.logger")
@patch(
    "generic_llm_framework.llm_coordinator.asyncio.create_task"
)  # Keep patching create_task
@patch(
    "generic_llm_framework.llm_coordinator.record_usage", new_callable=AsyncMock
)  # Keep patching record_usage
@patch("generic_llm_framework.llm_coordinator.serial_if_local")
@patch("generic_llm_framework.llm_coordinator.ModelPool.get")
async def test_llm_call_internal_verbose_logging(
    mock_model_pool_get,
    mock_serial_if_local,
    mock_record_usage,
    mock_create_task,
    mock_logger,
):
    mock_model_obj = MagicMock()
    mock_llm_response_obj = AsyncMock()
    mock_llm_response_obj.text = AsyncMock(return_value="Verbose response")
    mock_model_obj.prompt = AsyncMock(return_value=mock_llm_response_obj)
    mock_model_pool_get.return_value = mock_model_obj

    mock_serial_cm = AsyncMock()
    mock_serial_cm.__aenter__.return_value = None
    mock_serial_if_local.return_value = mock_serial_cm

    await llm_coordinator.llm_call_internal(
        model_id="verbose_model",
        prompt="verbose_prompt",
        system_prompt="verbose_system",
        verbose_llm_debug=True,
        agent_name="v_agent",
        game_id="v_game",
        phase_str="v_phase",
    )

    # Check for logger.info calls
    # There should be one for the prompt and one for the response.
    assert mock_logger.info.call_count >= 2
    # Check that specific parts of the prompt and response were logged
    # This is a bit fragile as it depends on exact log formatting.
    # A more robust check might involve checking that certain keywords are present in log calls.
    # Example (adjust based on actual log messages):
    found_prompt_log = any(
        "LLM Call (verbose):" in call.args[0] and "verbose_prompt" in call.args[0]
        for call in mock_logger.info.call_args_list
    )
    found_response_log = any(
        "LLM Response (verbose):" in call.args[0] and "Verbose response" in call.args[0]
        for call in mock_logger.info.call_args_list
    )
    assert found_prompt_log
    assert found_response_log


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.asyncio.create_task")  # Patch create_task
@patch(
    "generic_llm_framework.llm_coordinator.record_usage", new_callable=AsyncMock
)  # Patch record_usage
@patch("generic_llm_framework.llm_coordinator.serial_if_local")
@patch("generic_llm_framework.llm_coordinator.ModelPool.get")
async def test_llm_call_internal_exception_from_model_prompt(
    mock_model_pool_get,
    mock_serial_if_local,
    mock_record_usage,
    mock_create_task,  # Add mock_create_task
):
    mock_model_obj = MagicMock()
    mock_model_obj.prompt = AsyncMock(side_effect=ValueError("Model prompt error"))
    mock_model_pool_get.return_value = mock_model_obj

    mock_serial_cm = AsyncMock()
    mock_serial_cm.__aenter__.return_value = None
    mock_serial_if_local.return_value = mock_serial_cm

    with pytest.raises(ValueError, match="Model prompt error"):
        await llm_coordinator.llm_call_internal(
            model_id="error_model",
            prompt="error_prompt",
            agent_name="e_agent",
            game_id="e_game",
            phase_str="e_phase",
        )

    mock_create_task.assert_not_called()  # record_usage should not be scheduled


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.asyncio.create_task")  # Patch create_task
@patch(
    "generic_llm_framework.llm_coordinator.record_usage", new_callable=AsyncMock
)  # Patch record_usage
@patch("generic_llm_framework.llm_coordinator.serial_if_local")
@patch("generic_llm_framework.llm_coordinator.ModelPool.get")
async def test_llm_call_internal_exception_from_model_pool_get(
    mock_model_pool_get,
    mock_serial_if_local,
    mock_record_usage,
    mock_create_task,  # Add mock_create_task
):
    mock_model_pool_get.side_effect = Exception("ModelPool.get failed")

    with pytest.raises(Exception, match="ModelPool.get failed"):
        await llm_coordinator.llm_call_internal(
            model_id="get_fail_model",
            prompt="get_fail_prompt",
            agent_name="gf_agent",
            game_id="gf_game",
            phase_str="gf_phase",
        )

    mock_serial_if_local.assert_not_called()
    mock_create_task.assert_not_called()  # record_usage should not be scheduled
