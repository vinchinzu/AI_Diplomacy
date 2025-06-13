import pytest
import sqlite3
from unittest.mock import MagicMock, AsyncMock

# Assuming llm_coordinator.py is in ai_diplomacy.services
from generic_llm_framework import llm_coordinator  # Updated import
# LLMCoordinator, ModelPool, LLMCallResult are not directly used by these DB tests,
# but LLMResponse is used by mock_llm_response.
# from generic_llm_framework.llm_coordinator import LLMCoordinator, ModelPool, LLMCallResult # Updated commented import


# Fixture to reset the database path for testing and ensure cleanup
@pytest.fixture(autouse=True)
def test_db_path(tmp_path, monkeypatch):
    db_file = tmp_path / "test_usage.db"
    monkeypatch.setattr(llm_coordinator, "DATABASE_PATH", str(db_file))
    # Ensure a clean slate for each test that uses the DB
    if db_file.exists():
        db_file.unlink()
    llm_coordinator.initialize_database()  # Initialize with the new path
    return str(db_file)


@pytest.fixture
def mock_llm_response():
    response = MagicMock(
        spec=llm_coordinator.LLMResponse
    )  # Use the imported LLMResponse
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


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_record_usage_success(mock_llm_response, test_db_path):
    await llm_coordinator.record_usage("game1", "agent1", "phase1", mock_llm_response)

    # Verify data in DB
    with sqlite3.connect(test_db_path) as conn:
        cursor = conn.execute(
            "SELECT game_id, agent, phase, model, input, output FROM usage"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row == ("game1", "agent1", "phase1", "test_model", 100, 50)


def setup_basic_usage_data(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO usage (game_id, agent, phase, model, input, output) VALUES (?, ?, ?, ?, ?, ?)",
            ("game1", "agentA", "S1901M", "modelX", 10, 20),
        )
        conn.execute(
            "INSERT INTO usage (game_id, agent, phase, model, input, output) VALUES (?, ?, ?, ?, ?, ?)",
            ("game1", "agentA", "F1901M", "modelX", 15, 25),
        )
        conn.execute(
            "INSERT INTO usage (game_id, agent, phase, model, input, output) VALUES (?, ?, ?, ?, ?, ?)",
            ("game1", "agentB", "S1901M", "modelY", 30, 40),
        )
        conn.execute(
            "INSERT INTO usage (game_id, agent, phase, model, input, output) VALUES (?, ?, ?, ?, ?, ?)",
            ("game2", "agentA", "S1901M", "modelX", 5, 5),
        )
        conn.commit()


@pytest.mark.integration
@pytest.mark.slow
def test_get_usage_stats_by_country_success(test_db_path):
    setup_basic_usage_data(test_db_path)
    stats = llm_coordinator.get_usage_stats_by_country("game1")

    assert "agentA" in stats
    assert stats["agentA"]["api_calls"] == 2
    assert stats["agentA"]["input_tokens"] == 25
    assert stats["agentA"]["output_tokens"] == 45
    assert "modelX" in stats["agentA"]["models"]

    assert "agentB" in stats
    assert stats["agentB"]["api_calls"] == 1
    assert stats["agentB"]["input_tokens"] == 30
    assert stats["agentB"]["output_tokens"] == 40
    assert "modelY" in stats["agentB"]["models"]


@pytest.mark.integration
@pytest.mark.slow
def test_get_usage_stats_by_country_no_data_for_game(test_db_path):
    setup_basic_usage_data(test_db_path)
    stats = llm_coordinator.get_usage_stats_by_country("game_nonexistent")
    assert stats == {}



@pytest.mark.integration
@pytest.mark.slow
def test_get_total_usage_stats_success(test_db_path):
    setup_basic_usage_data(test_db_path)
    stats = llm_coordinator.get_total_usage_stats("game1")

    assert stats["total_api_calls"] == 3
    assert stats["total_input_tokens"] == 55
    assert stats["total_output_tokens"] == 85


@pytest.mark.integration
@pytest.mark.slow
def test_get_total_usage_stats_no_data_for_game(test_db_path):
    setup_basic_usage_data(test_db_path)
    stats = llm_coordinator.get_total_usage_stats("game_nonexistent")
    assert stats == {
        "total_api_calls": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
    }


@pytest.mark.integration
@pytest.mark.slow
def test_initialize_database_success(
    tmp_path,
):  # tmp_path here is fine, test_db_path fixture not strictly needed if we manage path locally
    db_file = tmp_path / "init_test.db"
    if db_file.exists():
        db_file.unlink()

    original_db_path = llm_coordinator.DATABASE_PATH
    llm_coordinator.DATABASE_PATH = str(db_file)  # Direct modification for this test

    try:
        llm_coordinator.initialize_database()
        assert db_file.exists()
        with sqlite3.connect(db_file) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='usage';"
            )
            assert cursor.fetchone() is not None
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='usage_game_agent';"
            )
            assert cursor.fetchone() is not None
    finally:
        llm_coordinator.DATABASE_PATH = original_db_path  # Restore
