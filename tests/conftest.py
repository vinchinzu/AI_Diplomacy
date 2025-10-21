import random
from typing import Generator

import pytest


@pytest.fixture(scope="function")
def fake_llm():
    """Implements LLM.complete() by returning deterministic JSON snippets; counts tokens."""

    class FakeLLM:
        def complete(self, prompt: str, **kwargs) -> str:
            # Simple deterministic output based on prompt content
            if "orders" in prompt.lower():
                return '{"orders": ["FRA A PAR H"]}'
            if "message" in prompt.lower():
                return '{"message": "Hello from fake_llm"}'
            return "{}"

        def __call__(self, *args, **kwargs):
            return self

    return FakeLLM()


@pytest.fixture(scope="module")
def mini_board() -> dict:
    """A 2-power 1901-spring board (json) loaded into domain.adapter_diplomacy."""
    # A simplified representation of a game state
    return {
        "name": "S1901M",
        "season": "spring",
        "year": 1901,
        "phase_type": "M",
        "units": {
            "ENGLAND": ["A LVP", "F LON", "F EDI"],
            "FRANCE": ["A PAR", "A MAR", "F BRE"],
        },
        "centers": {"ENGLAND": ["LON", "LVP", "EDI"], "FRANCE": ["PAR", "MAR", "BRE"]},
    }


@pytest.fixture(scope="function")
def rule_agent():
    """The tiny rule-based hold-in-place agent."""

    def agent_function(game_state: dict) -> dict:
        """Generates hold orders for all units of a power."""
        orders = {}
        power = "FRANCE"  # Example power
        if power in game_state["units"]:
            orders[power] = [f"{unit} H" for unit in game_state["units"][power]]
        return {"orders": orders}

    return agent_function


@pytest.fixture(scope="function")
def seed_random() -> Generator[None, None, None]:
    """random.seed(123) guards flakiness."""
    random.seed(123)
    yield
    # No cleanup needed after


def pytest_addoption(parser):
    """Add custom command-line options to pytest."""
    parser.addoption(
        "--llm-endpoint",
        action="store",
        default=None,
        help="Endpoint for a real LLM service (e.g., http://localhost:11434/api)",
    )
