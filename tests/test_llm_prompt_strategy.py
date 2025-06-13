"""
Tests for the prompt strategy.
"""
import pytest

from ai_diplomacy.agents.llm.prompt.strategy import JinjaPromptStrategy
from ai_diplomacy.domain.phase import PhaseKey, PhaseState


@pytest.fixture
def sample_phase_state() -> PhaseState:
    """Returns a sample PhaseState for testing."""
    return PhaseState(
        key=PhaseKey(
            state={},
            scs={},
            year=1901,
            season="SPRING",
            name="MOVEMENT",
        ),
        board={},  # type: ignore
        history=[],
    )


class TestJinjaPromptStrategy:
    """Tests for the JinjaPromptStrategy."""

    def test_for_orders_prompt_generation(self, sample_phase_state: PhaseState):
        """
        Verify that the for_orders method generates a valid prompt.
        """
        strategy = JinjaPromptStrategy()
        power = "FRANCE"
        goal_summary = "Take Belgium."

        prompt = strategy.for_orders(
            phase=sample_phase_state,
            power=power,
            goal_summary=goal_summary,
        )

        assert f"You are an AI agent playing as {power}" in prompt
        assert f"It is {sample_phase_state.key.season} {sample_phase_state.key.year}" in prompt
        assert goal_summary in prompt
        assert "Return your response as a JSON object" in prompt

    def test_for_orders_prompt_with_no_goals(self, sample_phase_state: PhaseState):
        """
        Verify that the prompt is generated correctly when no goals are provided.
        """
        strategy = JinjaPromptStrategy()
        power = "GERMANY"

        prompt = strategy.for_orders(phase=sample_phase_state, power=power)

        assert "No specific goals set." in prompt
