import pytest
import asyncio
# import sqlite3 # No longer needed here
from unittest.mock import MagicMock, AsyncMock, patch, call # call might not be needed
import logging

# Assuming llm_coordinator.py is in ai_diplomacy.services
from ai_diplomacy.services import llm_coordinator # llm_coordinator module itself for patching llm.get_async_model
from ai_diplomacy.services.llm_coordinator import LLMCallResult, LLMCoordinator, ModelPool

# DB-related fixtures and tests have been moved to tests/integration/services/test_llm_coordinator_db.py

# Tests for ModelPool
@pytest.mark.unit
@patch("llm.get_async_model") # Patch where llm is used in llm_coordinator (which is ai_diplomacy.services.llm_coordinator)
def test_model_pool_get_new_model(mock_get_async_model):
    mock_model_instance = MagicMock()
    mock_get_async_model.return_value = mock_model_instance
    
    ModelPool._cache = {} # Ensure clean cache
    model_id = "ollama/test_model"
    
    retrieved_model = ModelPool.get(model_id)
    
    mock_get_async_model.assert_called_once_with(model_id)
    assert retrieved_model == mock_model_instance
    assert model_id in ModelPool._cache
    assert ModelPool._cache[model_id] == mock_model_instance

@pytest.mark.unit
@patch("llm.get_async_model") # Patch where llm is used
def test_model_pool_get_cached_model(mock_get_async_model):
    mock_model_instance = MagicMock()
    model_id = "ollama/cached_model"
    
    ModelPool._cache = {model_id: mock_model_instance} # Pre-populate cache
    
    retrieved_model = ModelPool.get(model_id)
    
    mock_get_async_model.assert_not_called() # Should not be called if cached
    assert retrieved_model == mock_model_instance

# Tests for serial_if_local
@pytest.mark.unit
@pytest.mark.asyncio
async def test_serial_if_local_local_model():
    # Test with a model ID that should use the lock
    local_model_id = "ollama/llama3"
    llm_coordinator._local_lock = asyncio.Lock() # Ensure a fresh lock for the test
    
    async with llm_coordinator.serial_if_local(local_model_id):
        assert llm_coordinator._local_lock.locked()
    assert not llm_coordinator._local_lock.locked()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_serial_if_local_non_local_model():
    # Test with a model ID that should NOT use the lock
    non_local_model_id = "gpt-4o"
    llm_coordinator._local_lock = asyncio.Lock() # Ensure a fresh lock
    
    async with llm_coordinator.serial_if_local(non_local_model_id):
        assert not llm_coordinator._local_lock.locked() # Lock should not be acquired
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
        llm_caller_override=mock_custom_llm_caller
    )
    
    assert response == "Test response text"
    mock_custom_llm_caller.assert_called_once_with(
        game_id=game_id,
        agent_name=agent_id,
        phase_str=phase,
        model_id=model_id,
        prompt=prompt,
        system_prompt=system_prompt
    )

@pytest.mark.unit
@pytest.mark.asyncio
async def test_llmcoordinator_call_text_default_game_phase(coordinator):
    mock_custom_llm_caller = AsyncMock(return_value="Default response")
    
    prompt = "Another prompt"
    model_id = "another_model"
    agent_id = "another_agent"
    
    await coordinator.call_text(
        prompt=prompt,
        model_id=model_id,
        agent_id=agent_id,
        llm_caller_override=mock_custom_llm_caller
    )
    
    mock_custom_llm_caller.assert_called_once_with(
        game_id="default",
        agent_name=agent_id,
        phase_str="unknown",
        model_id=model_id,
        prompt=prompt,
        system_prompt=None
    )

@pytest.mark.unit
@pytest.mark.asyncio
async def test_llmcoordinator_call_text_propagates_exception(coordinator):
    mock_custom_llm_caller = AsyncMock(side_effect=ValueError("LLM Internal Error"))
    
    with pytest.raises(ValueError, match="LLM Internal Error"):
        await coordinator.call_text(
            prompt="Error prompt",
            model_id="error_model",
            agent_id="error_agent",
            llm_caller_override=mock_custom_llm_caller
        )
    
    mock_custom_llm_caller.assert_called_once_with(
        game_id="default",
        agent_name="error_agent",
        phase_str="unknown",
        model_id="error_model",
        prompt="Error prompt",
        system_prompt=None
    )

# Tests for LLMCoordinator.call_json
@pytest.mark.unit
@pytest.mark.asyncio
@patch.object(LLMCoordinator, "call_llm_with_json_parsing", new_callable=AsyncMock)
async def test_llmcoordinator_call_json_success(mock_call_llm_with_json_parsing, coordinator):
    expected_dict = {"key": "value", "orders": ["A PAR H"]}
    mock_call_llm_with_json_parsing.return_value = LLMCallResult(
        raw_response='''{"key": "value", "orders": ["A PAR H"]}''',
        parsed_json=expected_dict,
        success=True
    )
    
    result = await coordinator.call_json(
        prompt="json prompt",
        model_id="json_model",
        agent_id="json_agent",
        expected_fields=["key", "orders"]
        # llm_caller_override will default to None and be passed to call_llm_with_json_parsing
    )
    
    assert result == expected_dict
    mock_call_llm_with_json_parsing.assert_called_once_with(
        model_id="json_model",
        prompt="json prompt",
        system_prompt=None,
        game_id="default",
        agent_name="json_agent",
        phase_str="unknown",
        expected_json_fields=["key", "orders"],
        llm_caller_override=None # Explicitly check it's passed as None
    )

@pytest.mark.unit
@pytest.mark.asyncio
@patch.object(LLMCoordinator, "call_llm_with_json_parsing", new_callable=AsyncMock)
async def test_llmcoordinator_call_json_failure_from_internal_call(mock_call_llm_with_json_parsing, coordinator):
    mock_call_llm_with_json_parsing.return_value = LLMCallResult(
        raw_response="error from llm",
        success=False,
        error_message="Internal LLM error"
    )
    
    with pytest.raises(ValueError, match="LLM call failed: Internal LLM error"):
        await coordinator.call_json(
            prompt="json prompt",
            model_id="json_model",
            agent_id="json_agent"
        )

@pytest.mark.unit
@pytest.mark.asyncio
@patch.object(LLMCoordinator, "call_llm_with_json_parsing", new_callable=AsyncMock)
async def test_llmcoordinator_call_json_parsed_is_none(mock_call_llm_with_json_parsing, coordinator):
    mock_call_llm_with_json_parsing.return_value = LLMCallResult(
        raw_response="",
        parsed_json=None, 
        success=True 
    )
    
    result = await coordinator.call_json(
        prompt="json prompt",
        model_id="json_model",
        agent_id="json_agent"
    )
    assert result == {}

@pytest.mark.unit
@pytest.mark.asyncio
@patch.object(LLMCoordinator, "call_llm_with_json_parsing", new_callable=AsyncMock)
async def test_llmcoordinator_call_json_with_tools(mock_call_llm_with_json_parsing, coordinator, caplog):
    expected_dict = {"some_data": "data"}
    mock_call_llm_with_json_parsing.return_value = LLMCallResult(
        raw_response='''{"some_data": "data"}''',
        parsed_json=expected_dict,
        success=True
    )
    
    tools_def = [{"type": "function", "function": {"name": "get_weather"}}]
    
    with caplog.at_level(logging.DEBUG, logger="ai_diplomacy.services.llm_coordinator"):
        await coordinator.call_json(
            prompt="json prompt with tools",
            model_id="mcp_model",
            agent_id="mcp_agent",
            tools=tools_def
        )
    
    # Verify that llm_caller_override=None was passed to the internal call
    args, kwargs = mock_call_llm_with_json_parsing.call_args
    assert kwargs.get("llm_caller_override") is None
    assert "Tools provided but MCP not yet implemented: 1 tools" in caplog.text