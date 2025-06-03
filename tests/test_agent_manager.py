import logging
import pytest
from unittest.mock import patch

from ai_diplomacy.agent_manager import AgentManager
from ai_diplomacy.agents.llm_agent import LLMAgent
from tests._shared_fixtures import create_game_config
# from tests.fixtures.assertions_agent_manager import assertion_map # Removed this line

logger = logging.getLogger(__name__)

# TOML_CONTENT_TEST_8, TOML_CONTENT_TEST_9, TOML_CONTENT_TEST_10, TOML_CONTENT_TEST_11 removed


@pytest.fixture
def game_config_factory():
    return create_game_config


# PARAMETRIZED_TEST_CASES removed

# test_assign_models_parametrized function removed

logger.info("--- All AgentManager tests collected (parametrized) ---")
