import pytest
import asyncio
import sqlite3
from unittest.mock import MagicMock, AsyncMock, patch, call
import logging

# Assuming llm_coordinator.py is in ai_diplomacy.services
from ai_diplomacy.services import llm_coordinator
from ai_diplomacy.services.llm_coordinator import LLMCallResult, LLMCoordinator, ModelPool

# Fixture to reset the database path for testing and ensure cleanup
@pytest.fixture(autouse=True)
def test_db_path(tmp_path, monkeypatch):
    db_file = tmp_path / "test_usage.db"
    monkeypatch.setattr(llm_coordinator, 'DATABASE_PATH', str(db_file))
    # Ensure a clean slate for each test that uses the DB
    if db_file.exists():
        db_file.unlink()
    llm_coordinator.initialize_database() # Initialize with the new path
    return str(db_file)

@pytest.fixture
def mock_llm_response():
    response = MagicMock(spec=llm_coordinator.LLMResponse) # Use the imported LLMResponse
    response.model = MagicMock()
    response.model.model_id = "test_model"
    
    # Mock the usage() method to be an async function returning a mock
    usage_mock = MagicMock()
    usage_mock.input = 100
    usage_mock.output = 50
    
    async def mock_usage():
        return usage_mock
        
    response.usage = AsyncMock(side_effect=mock_usage)
    return response

@pytest.mark.asyncio
async def test_record_usage_success(mock_llm_response, test_db_path):
    await llm_coordinator.record_usage("game1", "agent1", "phase1", mock_llm_response)
    
    # Verify data in DB
    with sqlite3.connect(test_db_path) as conn:
        cursor = conn.execute("SELECT game_id, agent, phase, model, input, output FROM usage")
        row = cursor.fetchone()
        assert row is not None
        assert row == ("game1", "agent1", "phase1", "test_model", 100, 50)

@pytest.mark.asyncio
async def test_record_usage_sqlite_error_on_insert(mock_llm_response, test_db_path, caplog):
    with patch("sqlite3.connect") as mock_connect:
        mock_conn_instance = MagicMock()
        mock_conn_instance.execute.side_effect = sqlite3.Error("Simulated DB insert error")
        mock_connect.return_value.__enter__.return_value = mock_conn_instance
        
        await llm_coordinator.record_usage("game1", "agent1", "phase1", mock_llm_response)
        
        assert "SQLite error in record_usage: Simulated DB insert error" in caplog.text

@pytest.mark.asyncio
async def test_record_usage_attribute_error_on_response(caplog):
    # Create a response object that will cause an AttributeError
    faulty_response = MagicMock()
    # Make .usage() an async function, but one that will lead to an attribute error later
    # e.g. if response.model is None or response.model.model_id is missing
    faulty_response.model = None 
    
    async def mock_faulty_usage():
        # This part might not even be reached if response.model.model_id fails first
        usage_mock = MagicMock()
        usage_mock.input = 10
        usage_mock.output = 5
        return usage_mock

    faulty_response.usage = AsyncMock(side_effect=mock_faulty_usage)

    # To trigger the attribute error on response.model.model_id
    # We need to ensure the code path reaches that point.
    # The specific error in the original code is:
    # response.model.model_id if hasattr(response, 'model') else 'N/A'
    # If model is None, it will try to access model.model_id, which will fail.

    await llm_coordinator.record_usage("game_attr_err", "agent_attr_err", "phase_attr_err", faulty_response)
    
    # Check if the logger caught an AttributeError
    # The exact message might depend on how the logger formats it.
    # We are interested in the fact that an AttributeError was logged.
    assert "Error accessing response attributes in record_usage" in caplog.text
    # A more specific check if possible:
    # assert "AttributeError: 'NoneType' object has no attribute 'model_id'" in caplog.text # This might be too specific

@pytest.mark.asyncio
async def test_record_usage_generic_exception(mock_llm_response, test_db_path, caplog):
    # Make response.usage() raise a generic exception
    async def mock_usage_exception():
        raise Exception("Simulated generic error in usage")
    mock_llm_response.usage = AsyncMock(side_effect=mock_usage_exception)
        
    await llm_coordinator.record_usage("game_generic_err", "agent_generic_err", "phase_generic_err", mock_llm_response)
    
    assert "Unexpected error in record_usage: Simulated generic error in usage" in caplog.text

# Tests for get_usage_stats_by_country
def setup_basic_usage_data(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO usage (game_id, agent, phase, model, input, output) VALUES (?, ?, ?, ?, ?, ?)",
                     ("game1", "agentA", "S1901M", "modelX", 10, 20))
        conn.execute("INSERT INTO usage (game_id, agent, phase, model, input, output) VALUES (?, ?, ?, ?, ?, ?)",
                     ("game1", "agentA", "F1901M", "modelX", 15, 25))
        conn.execute("INSERT INTO usage (game_id, agent, phase, model, input, output) VALUES (?, ?, ?, ?, ?, ?)",
                     ("game1", "agentB", "S1901M", "modelY", 30, 40))
        conn.execute("INSERT INTO usage (game_id, agent, phase, model, input, output) VALUES (?, ?, ?, ?, ?, ?)",
                     ("game2", "agentA", "S1901M", "modelX", 5, 5))
        conn.commit()

def test_get_usage_stats_by_country_success(test_db_path):
    setup_basic_usage_data(test_db_path)
    stats = llm_coordinator.get_usage_stats_by_country("game1")
    
    assert "agentA" in stats
    assert stats["agentA"]["api_calls"] == 2
    assert stats["agentA"]["input_tokens"] == 25 # 10 + 15
    assert stats["agentA"]["output_tokens"] == 45 # 20 + 25
    assert "modelX" in stats["agentA"]["models"]
    
    assert "agentB" in stats
    assert stats["agentB"]["api_calls"] == 1
    assert stats["agentB"]["input_tokens"] == 30
    assert stats["agentB"]["output_tokens"] == 40
    assert "modelY" in stats["agentB"]["models"]

def test_get_usage_stats_by_country_no_data_for_game(test_db_path):
    setup_basic_usage_data(test_db_path) # sets up for game1 and game2
    stats = llm_coordinator.get_usage_stats_by_country("game_nonexistent")
    assert stats == {}

def test_get_usage_stats_by_country_sqlite_error(test_db_path, caplog):
    with patch("sqlite3.connect") as mock_connect:
        mock_conn_instance = MagicMock()
        mock_conn_instance.execute.side_effect = sqlite3.Error("Simulated DB query error")
        mock_connect.return_value.__enter__.return_value = mock_conn_instance
        
        stats = llm_coordinator.get_usage_stats_by_country("game1")
        assert stats == {}
        assert "Error getting usage stats: Simulated DB query error" in caplog.text

# Tests for get_total_usage_stats
def test_get_total_usage_stats_success(test_db_path):
    setup_basic_usage_data(test_db_path) # agentA: 25in/45out, agentB: 30in/40out for game1
    stats = llm_coordinator.get_total_usage_stats("game1")
    
    assert stats["total_api_calls"] == 3
    assert stats["total_input_tokens"] == 55 # 25 + 30
    assert stats["total_output_tokens"] == 85 # 45 + 40

def test_get_total_usage_stats_no_data_for_game(test_db_path):
    setup_basic_usage_data(test_db_path)
    stats = llm_coordinator.get_total_usage_stats("game_nonexistent")
    assert stats == {"total_api_calls": 0, "total_input_tokens": 0, "total_output_tokens": 0}

def test_get_total_usage_stats_sqlite_error(test_db_path, caplog):
    with patch("sqlite3.connect") as mock_connect:
        mock_conn_instance = MagicMock()
        mock_conn_instance.execute.side_effect = sqlite3.Error("Simulated DB total query error")
        mock_connect.return_value.__enter__.return_value = mock_conn_instance
        
        stats = llm_coordinator.get_total_usage_stats("game1")
        assert stats == {"total_api_calls": 0, "total_input_tokens": 0, "total_output_tokens": 0}
        assert "Error getting total usage stats: Simulated DB total query error" in caplog.text

# Tests for initialize_database
def test_initialize_database_success(tmp_path):
    db_file = tmp_path / "init_test.db"
    # Ensure it doesn't exist before test
    if db_file.exists():
        db_file.unlink()
    
    # Temporarily change DATABASE_PATH for this test
    original_db_path = llm_coordinator.DATABASE_PATH
    llm_coordinator.DATABASE_PATH = str(db_file)
    
    llm_coordinator.initialize_database()
    assert db_file.exists()
    
    # Check table and index creation
    with sqlite3.connect(db_file) as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='usage';")
        assert cursor.fetchone() is not None
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='usage_game_agent';")
        assert cursor.fetchone() is not None

    # Restore original path
    llm_coordinator.DATABASE_PATH = original_db_path


def test_initialize_database_failure(tmp_path, caplog, monkeypatch):
    # Simulate a non-writable path or other SQLite error condition
    # For simplicity, we can patch sqlite3.connect to raise an error
    
    # This test needs to be careful not to interfere with other tests using the DB
    # by using a unique path that won't be created.
    non_existent_path = tmp_path / "non_writeable_dir" / "fail.db"
    
    original_db_path = llm_coordinator.DATABASE_PATH
    monkeypatch.setattr(llm_coordinator, 'DATABASE_PATH', str(non_existent_path))

    with patch("sqlite3.connect", side_effect=sqlite3.OperationalError("cannot open database file")) as mock_connect:
        with pytest.raises(sqlite3.OperationalError): # Expect the error to be re-raised
             llm_coordinator.initialize_database()
        
        assert f"Error initializing database {str(non_existent_path)}: cannot open database file" in caplog.text
        mock_connect.assert_called_once_with(str(non_existent_path))

    # No need to restore DATABASE_PATH if using monkeypatch, it handles cleanup.
    # But if not using autouse fixture for test_db_path, ensure to restore if changing module global

# Tests for ModelPool
@patch("llm.get_async_model") # Patch where llm is used in llm_coordinator
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

@patch("llm.get_async_model")
def test_model_pool_get_cached_model(mock_get_async_model):
    mock_model_instance = MagicMock()
    model_id = "ollama/cached_model"
    
    ModelPool._cache = {model_id: mock_model_instance} # Pre-populate cache
    
    retrieved_model = ModelPool.get(model_id)
    
    mock_get_async_model.assert_not_called() # Should not be called if cached
    assert retrieved_model == mock_model_instance

# Tests for serial_if_local
@pytest.mark.asyncio
async def test_serial_if_local_local_model():
    # Test with a model ID that should use the lock
    local_model_id = "ollama/llama3"
    llm_coordinator._local_lock = asyncio.Lock() # Ensure a fresh lock for the test
    
    # Check if lock is acquired and released
    # This is a bit tricky to test directly without instrumenting the lock
    # We can check if it attempts to acquire the lock by seeing if it's locked inside the context
    async with llm_coordinator.serial_if_local(local_model_id):
        assert llm_coordinator._local_lock.locked()
    # After exiting context, lock should be released
    assert not llm_coordinator._local_lock.locked()

@pytest.mark.asyncio
async def test_serial_if_local_non_local_model():
    # Test with a model ID that should NOT use the lock
    non_local_model_id = "gpt-4o"
    llm_coordinator._local_lock = asyncio.Lock() # Ensure a fresh lock
    
    async with llm_coordinator.serial_if_local(non_local_model_id):
        assert not llm_coordinator._local_lock.locked() # Lock should not be acquired
    assert not llm_coordinator._local_lock.locked()

@pytest.mark.asyncio
async def test_serial_if_local_llamacpp_model():
    local_model_id = "llamacpp/mistral"
    llm_coordinator._local_lock = asyncio.Lock()
    async with llm_coordinator.serial_if_local(local_model_id):
        assert llm_coordinator._local_lock.locked()
    assert not llm_coordinator._local_lock.locked()

@pytest.mark.asyncio
async def test_serial_if_local_case_insensitivity():
    local_model_id_upper = "OLLAMA/MIXTRAL"
    llm_coordinator._local_lock = asyncio.Lock()
    async with llm_coordinator.serial_if_local(local_model_id_upper):
        assert llm_coordinator._local_lock.locked()
    assert not llm_coordinator._local_lock.locked()

# More tests for LLMCoordinator methods to come...

@pytest.fixture
def coordinator():
    return LLMCoordinator()

@pytest.mark.asyncio
@patch("ai_diplomacy.services.llm_coordinator.llm_call_internal", new_callable=AsyncMock) # Patch within the module
async def test_llmcoordinator_call_text_success(mock_llm_call_internal, coordinator):
    mock_llm_call_internal.return_value = "Test response text"
    
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
        system_prompt=system_prompt
    )
    
    assert response == "Test response text"
    mock_llm_call_internal.assert_called_once_with(
        game_id=game_id,
        agent_name=agent_id,
        phase_str=phase,
        model_id=model_id,
        prompt=prompt,
        system_prompt=system_prompt
    )

@pytest.mark.asyncio
@patch("ai_diplomacy.services.llm_coordinator.llm_call_internal", new_callable=AsyncMock)
async def test_llmcoordinator_call_text_default_game_phase(mock_llm_call_internal, coordinator):
    mock_llm_call_internal.return_value = "Default response"
    
    prompt = "Another prompt"
    model_id = "another_model"
    agent_id = "another_agent"
    
    await coordinator.call_text(
        prompt=prompt,
        model_id=model_id,
        agent_id=agent_id
        # game_id and phase use defaults
    )
    
    mock_llm_call_internal.assert_called_once_with(
        game_id="default",
        agent_name=agent_id,
        phase_str="unknown",
        model_id=model_id,
        prompt=prompt,
        system_prompt=None # Default system_prompt
    )

@pytest.mark.asyncio
@patch("ai_diplomacy.services.llm_coordinator.llm_call_internal", new_callable=AsyncMock)
async def test_llmcoordinator_call_text_propagates_exception(mock_llm_call_internal, coordinator):
    mock_llm_call_internal.side_effect = ValueError("LLM Internal Error")
    
    with pytest.raises(ValueError, match="LLM Internal Error"):
        await coordinator.call_text(
            prompt="Error prompt",
            model_id="error_model",
            agent_id="error_agent"
        )

# Tests for LLMCoordinator.call_json
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
    )
    
    assert result == expected_dict
    mock_call_llm_with_json_parsing.assert_called_once_with(
        model_id="json_model",
        prompt="json prompt",
        system_prompt=None,
        game_id="default",
        agent_name="json_agent",
        phase_str="unknown",
        expected_json_fields=["key", "orders"]
    )

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

@pytest.mark.asyncio
@patch.object(LLMCoordinator, "call_llm_with_json_parsing", new_callable=AsyncMock)
async def test_llmcoordinator_call_json_parsed_is_none(mock_call_llm_with_json_parsing, coordinator):
    mock_call_llm_with_json_parsing.return_value = LLMCallResult(
        raw_response="",
        parsed_json=None, # Simulate case where parsing returns None but success is True (e.g. empty string parsed)
        success=True 
    )
    
    result = await coordinator.call_json(
        prompt="json prompt",
        model_id="json_model",
        agent_id="json_agent"
    )
    assert result == {} # Should return empty dict if parsed_json is None

@pytest.mark.asyncio
@patch.object(LLMCoordinator, "call_llm_with_json_parsing", new_callable=AsyncMock)
async def test_llmcoordinator_call_json_with_tools(mock_call_llm_with_json_parsing, coordinator, caplog):
    # This test mainly checks that the 'tools' argument is passed through
    # and logs the debug message, as full MCP tool use isn't implemented yet.
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
    
    mock_call_llm_with_json_parsing.assert_called_once() # args are checked in first test
    assert "Tools provided but MCP not yet implemented: 1 tools" in caplog.text

# More tests for LLMCoordinator methods to come... 