import pytest
import asyncio
import os

# import sqlite3 # No longer needed here
from unittest.mock import MagicMock, AsyncMock, patch  # call might not be needed
import logging

# Assuming llm_coordinator.py is in ai_diplomacy.services
from generic_llm_framework import llm_coordinator
from generic_llm_framework.llm_coordinator import (
    LLMCallResult,
    LLMCoordinator,
    ModelPool,
)
from generic_llm_framework import constants as generic_constants


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
@patch("generic_llm_framework.llm_coordinator.llm_call_internal", new_callable=AsyncMock)
async def test_llmcoordinator_call_text_uses_internal_call(mock_llm_call_internal, coordinator):
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
        agent_name=agent_id,
        phase_str=phase,
        model_id=model_id,
        prompt=prompt,
        system_prompt=system_prompt,
        verbose_llm_debug=False,
    )


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.llm_call_internal", new_callable=AsyncMock)
async def test_llmcoordinator_call_text_internal_call_exception(mock_llm_call_internal, coordinator):
    mock_llm_call_internal.side_effect = ValueError("Internal LLM Error")

    with pytest.raises(ValueError, match="Internal LLM Error"):
        await coordinator.call_text(
            prompt="Error prompt internal",
            model_id="error_model_internal",
            agent_id="error_agent_internal",
            llm_caller_override=None,  # Explicitly None
        )

    mock_llm_call_internal.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
@patch.object(LLMCoordinator, "call_llm_with_json_parsing", new_callable=AsyncMock)
async def test_llmcoordinator_call_json_success(mock_call_llm_with_json_parsing, coordinator):
    expected_result = {"key": "value"}
    mock_call_llm_with_json_parsing.return_value = LLMCallResult(
        raw_response='{"key": "value"}', parsed_json=expected_result, success=True
    )

    response = await coordinator.call_json(prompt="Json prompt", model_id="json_model", agent_id="json_agent")

    assert response == expected_result
    mock_call_llm_with_json_parsing.assert_called_once_with(
        model_id="json_model",
        prompt="Json prompt",
        system_prompt=None,
        game_id=generic_constants.DEFAULT_GAME_ID,
        agent_name="json_agent",
        phase_str=generic_constants.DEFAULT_PHASE_NAME,
        expected_json_fields=None,
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
        raw_response="", parsed_json=None, success=False, error_message="LLM Error"
    )

    with pytest.raises(ValueError, match="LLM call failed: LLM Error"):
        await coordinator.call_json(prompt="fail prompt", model_id="fail_model", agent_id="fail_agent")


@pytest.mark.unit
@pytest.mark.asyncio
@patch.object(LLMCoordinator, "call_llm_with_json_parsing", new_callable=AsyncMock)
async def test_llmcoordinator_call_json_parsed_is_none(mock_call_llm_with_json_parsing, coordinator):
    mock_call_llm_with_json_parsing.return_value = LLMCallResult(
        raw_response="not json", parsed_json=None, success=True
    )

    response = await coordinator.call_json(
        prompt="parse fail prompt",
        model_id="parse_fail_model",
        agent_id="parse_fail_agent",
    )

    assert response == {}


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.xfail(reason="Caplog not capturing logger output correctly in this setup")
@patch.object(LLMCoordinator, "call_llm_with_json_parsing", new_callable=AsyncMock)
async def test_llmcoordinator_call_json_with_tools(mock_call_llm_with_json_parsing, coordinator, caplog):
    tools_def = [{"type": "function", "function": {"name": "get_weather"}}]

    with caplog.at_level(logging.DEBUG):
        await coordinator.call_json(
            prompt="Tool prompt",
            model_id="tool_model",
            agent_id="tool_agent",
            tools=tools_def,
        )

    assert "Tools provided but MCP not yet implemented" in caplog.text
    mock_call_llm_with_json_parsing.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.llm_utils.log_llm_response")
@patch("generic_llm_framework.llm_coordinator.llm_utils.extract_json_from_text")
@patch("generic_llm_framework.llm_coordinator.llm_call_internal", new_callable=AsyncMock)
async def test_call_json_parsing_success_no_override(
    mock_llm_call_internal, mock_extract_json, mock_log_response, coordinator
):
    mock_llm_call_internal.return_value = '{"data": "value"}'
    mock_extract_json.return_value = {"data": "value"}

    result = await coordinator.call_llm_with_json_parsing(
        model_id="json_model_no_override",
        prompt="json prompt",
        agent_name="test_agent",
        game_id="test_game",
        phase_str="test_phase",
    )

    assert result.success is True
    assert result.parsed_json == {"data": "value"}
    mock_llm_call_internal.assert_called_once()
    mock_extract_json.assert_called_once_with(
        '{"data": "value"}',
        logging.getLogger("generic_llm_framework.llm_coordinator"),
        f"[{generic_constants.LLM_CALL_REQUEST_ID_DEFAULT}] JSON Parsing",
    )
    mock_log_response.assert_not_called()


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
    mock_custom_llm_caller = AsyncMock(return_value='{"data": "override"}')
    mock_extract_json.return_value = {"data": "override"}

    result = await coordinator.call_llm_with_json_parsing(
        model_id="json_model_override",
        prompt="json prompt override",
        agent_name="override_agent",
        game_id="override_game",
        phase_str="override_phase",
        llm_caller_override=mock_custom_llm_caller,
    )

    assert result.success is True
    assert result.parsed_json == {"data": "override"}
    mock_llm_call_internal.assert_not_called()
    mock_custom_llm_caller.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.llm_utils.log_llm_response")
@patch("generic_llm_framework.llm_coordinator.llm_utils.extract_json_from_text")
@patch("generic_llm_framework.llm_coordinator.llm_call_internal", new_callable=AsyncMock)
async def test_call_json_parsing_missing_expected_fields(
    mock_llm_call_internal, mock_extract_json, mock_log_response, coordinator
):
    mock_llm_call_internal.return_value = '{"field1": "value1"}'
    mock_extract_json.return_value = {"field1": "value1"}

    result = await coordinator.call_llm_with_json_parsing(
        model_id="missing_fields_model",
        prompt="missing fields prompt",
        agent_name="mf_agent",
        game_id="mf_game",
        phase_str="mf_phase",
        expected_json_fields=["field1", "field2"],
    )

    assert result.success is False
    assert "Missing expected fields: ['field2']" in result.error_message


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.llm_utils.log_llm_response")
@patch("generic_llm_framework.llm_coordinator.llm_utils.extract_json_from_text")
@patch("generic_llm_framework.llm_coordinator.llm_call_internal", new_callable=AsyncMock)
async def test_call_json_parsing_empty_response(
    mock_llm_call_internal, mock_extract_json, mock_log_response, coordinator
):
    mock_llm_call_internal.return_value = "  "

    result = await coordinator.call_llm_with_json_parsing(
        model_id="empty_model",
        prompt="empty prompt",
        agent_name="empty_agent",
        game_id="empty_game",
        phase_str="empty_phase",
    )

    assert result.success is False
    assert result.error_message == generic_constants.LLM_CALL_ERROR_EMPTY_RESPONSE
    mock_extract_json.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.llm_utils.log_llm_response")
@patch("generic_llm_framework.llm_coordinator.llm_utils.extract_json_from_text")
@patch("generic_llm_framework.llm_coordinator.llm_call_internal", new_callable=AsyncMock)
async def test_call_json_parsing_json_error(
    mock_llm_call_internal, mock_extract_json, mock_log_response, coordinator
):
    mock_llm_call_internal.return_value = "not json"
    mock_extract_json.side_effect = Exception("JSON error")

    result = await coordinator.call_llm_with_json_parsing(
        model_id="json_err_model",
        prompt="json err prompt",
        agent_name="err_agent",
        game_id="err_game",
        phase_str="err_phase",
    )

    assert result.success is False
    assert "JSON parsing error" in result.error_message


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.llm_utils.log_llm_response")
@patch("generic_llm_framework.llm_coordinator.llm_utils.extract_json_from_text")
@patch("generic_llm_framework.llm_coordinator.llm_call_internal", new_callable=AsyncMock)
async def test_call_json_parsing_llm_call_exception_internal(
    mock_llm_call_internal, mock_extract_json, mock_log_response, coordinator
):
    mock_llm_call_internal.side_effect = ValueError("LLM blew up")

    result = await coordinator.call_llm_with_json_parsing(
        model_id="exc_model",
        prompt="exc prompt",
        agent_name="exc_agent",
        game_id="exc_game",
        phase_str="exc_phase",
    )

    assert result.success is False
    assert "LLM call error: LLM blew up" in result.error_message


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.llm_utils.log_llm_response")
@patch("generic_llm_framework.llm_coordinator.llm_utils.extract_json_from_text")
async def test_call_json_parsing_llm_call_exception_override(
    mock_extract_json, mock_log_response, coordinator
):
    mock_custom_llm_caller = AsyncMock(side_effect=ValueError("Override blew up"))

    result = await coordinator.call_llm_with_json_parsing(
        model_id="exc_override_model",
        prompt="exc override prompt",
        agent_name="exc_override_agent",
        game_id="exc_override_game",
        phase_str="exc_override_phase",
        llm_caller_override=mock_custom_llm_caller,
    )

    assert result.success is False
    assert "LLM call error: Override blew up" in result.error_message


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.llm_utils.log_llm_response")
@patch("generic_llm_framework.llm_coordinator.llm_utils.extract_json_from_text")
@patch("generic_llm_framework.llm_coordinator.llm_call_internal", new_callable=AsyncMock)
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
    log_kwargs = mock_log_response.call_args.kwargs

    assert log_kwargs["raw_response"] == '{"data": "logged"}'
    assert log_kwargs["parsed_response"] == {"data": "logged"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_llmcoordinator_request_with_override(coordinator):
    mock_custom_llm_caller = AsyncMock(return_value="Override response")

    response = await coordinator.request(
        game_id="req_game",
        agent_name="req_agent",
        phase_str="req_phase",
        model_id="req_model",
        prompt_text="Request prompt",
        system_prompt_text="Request system prompt",
        llm_caller_override=mock_custom_llm_caller,
    )

    assert response == "Override response"
    mock_custom_llm_caller.assert_called_once_with(
        game_id="req_game",
        agent_name="req_agent",
        phase_str="req_phase",
        model_id="req_model",
        prompt="Request prompt",
        system_prompt="Request system prompt",
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_llmcoordinator_request_with_override_exception(coordinator):
    mock_custom_llm_caller = AsyncMock(side_effect=ValueError("Override Error"))

    with pytest.raises(ValueError, match="Override Error"):
        await coordinator.request(
            game_id="req_err_game",
            agent_name="req_err_agent",
            phase_str="req_err_phase",
            model_id="req_err_model",
            prompt_text="Request error prompt",
            system_prompt_text="Request error system prompt",
            llm_caller_override=mock_custom_llm_caller,
        )


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.llm_call_internal", new_callable=AsyncMock)
async def test_llmcoordinator_request_uses_internal_call(mock_llm_call_internal, coordinator):
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
        verbose_llm_debug=False,
    )


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.llm_call_internal", new_callable=AsyncMock)
async def test_llmcoordinator_request_internal_call_exception(mock_llm_call_internal, coordinator):
    mock_llm_call_internal.side_effect = ValueError("Internal Request Error")

    with pytest.raises(ValueError, match="Internal Request Error"):
        await coordinator.request(
            game_id="req_err_game_internal",
            agent_name="req_err_agent_internal",
            phase_str="req_err_phase_internal",
            model_id="req_err_model_internal",
            prompt_text="Request error prompt internal",
            system_prompt_text="Request error system prompt internal",
        )


@pytest.mark.unit
@patch("generic_llm_framework.llm_coordinator.ModelPool.get")  # Patching ModelPool.get directly
def test_llmcoordinator_get_model(mock_model_pool_get, coordinator):
    mock_model_instance = MagicMock(name="MockModelInstance")
    mock_model_pool_get.return_value = mock_model_instance
    model_id_to_get = "test_model_for_get_model"

    retrieved_model = coordinator.get_model(model_id_to_get)

    mock_model_pool_get.assert_called_once_with(model_id_to_get)
    assert retrieved_model == mock_model_instance


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
    monkeypatch,
):
    monkeypatch.setenv("ALLOW_LLM_CALLS_IN_TEST", "1")
    mock_model_obj = MagicMock()
    mock_llm_response_obj = AsyncMock()
    # The .text() method of a response object is async
    type(mock_llm_response_obj).text = AsyncMock(return_value="Test LLM response")
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
    mock_model_obj.prompt.assert_called_once_with(prompt)


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
    monkeypatch,
):
    monkeypatch.setenv("ALLOW_LLM_CALLS_IN_TEST", "1")
    mock_model_obj = MagicMock()
    mock_llm_response_obj = AsyncMock()
    type(mock_llm_response_obj).text = AsyncMock(return_value="Response with tools")
    mock_model_obj.prompt = AsyncMock(return_value=mock_llm_response_obj)
    mock_model_pool_get.return_value = mock_model_obj

    mock_serial_cm = AsyncMock()
    mock_serial_cm.__aenter__.return_value = None
    mock_serial_if_local.return_value = mock_serial_cm

    model_id = "tool_model"
    prompt = "Tool prompt"
    system_prompt = "Use tools wisely"
    tools_def = [{"type": "function", "function": {"name": "get_weather"}}]

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
    mock_model_obj.prompt.assert_called_once_with(prompt, system=system_prompt, tools=tools_def)


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.logger")
@patch("generic_llm_framework.llm_coordinator.asyncio.create_task")  # Keep patching create_task
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
    monkeypatch,
):
    monkeypatch.setenv("ALLOW_LLM_CALLS_IN_TEST", "1")
    mock_model_obj = MagicMock()
    mock_llm_response_obj = AsyncMock()
    type(mock_llm_response_obj).text = AsyncMock(return_value="Verbose response")
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
    assert mock_logger.info.call_count >= 2


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.asyncio.create_task")  # Patch create_task
@patch("generic_llm_framework.llm_coordinator.record_usage", new_callable=AsyncMock)  # Patch record_usage
@patch("generic_llm_framework.llm_coordinator.serial_if_local")
@patch("generic_llm_framework.llm_coordinator.ModelPool.get")
async def test_llm_call_internal_exception_from_model_prompt(
    mock_model_pool_get,
    mock_serial_if_local,
    mock_record_usage,
    mock_create_task,  # Add mock_create_task
    monkeypatch,
):
    monkeypatch.setenv("ALLOW_LLM_CALLS_IN_TEST", "1")
    mock_model_obj = MagicMock()
    mock_model_obj.prompt.side_effect = ValueError("Model prompt error")
    mock_model_pool_get.return_value = mock_model_obj

    mock_serial_cm = AsyncMock()
    mock_serial_cm.__aenter__.return_value = None
    mock_serial_if_local.return_value = mock_serial_cm

    with pytest.raises(ValueError, match="Model prompt error"):
        await llm_coordinator.llm_call_internal(
            model_id="error_model",
            prompt="error prompt",
            agent_name="error_agent",
            game_id="error_game",
            phase_str="error_phase",
        )


@pytest.mark.unit
@pytest.mark.asyncio
@patch("generic_llm_framework.llm_coordinator.asyncio.create_task")  # Patch create_task
@patch("generic_llm_framework.llm_coordinator.record_usage", new_callable=AsyncMock)  # Patch record_usage
@patch("generic_llm_framework.llm_coordinator.serial_if_local")
@patch("generic_llm_framework.llm_coordinator.ModelPool.get")
async def test_llm_call_internal_exception_from_model_pool_get(
    mock_model_pool_get,
    mock_serial_if_local,
    mock_record_usage,
    mock_create_task,  # Add mock_create_task
    monkeypatch,
):
    monkeypatch.setenv("ALLOW_LLM_CALLS_IN_TEST", "1")
    mock_model_pool_get.side_effect = Exception("ModelPool.get failed")

    with pytest.raises(Exception, match="ModelPool.get failed"):
        await llm_coordinator.llm_call_internal(
            model_id="get_fail_model",
            prompt="get fail prompt",
            agent_name="get_fail_agent",
            game_id="get_fail_game",
            phase_str="get_fail_phase",
        )
