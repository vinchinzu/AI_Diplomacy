import pytest
from ai_diplomacy.agents.scripted_agent import ScriptedAgent
from ai_diplomacy.core.state import PhaseState

@pytest.mark.unit
@pytest.mark.asyncio
async def test_scripted_agent():
    """Test scripted agent functionality."""
    agent = ScriptedAgent("test-france", "FRANCE", "neutral")

    # Create test phase state
    phase = PhaseState(
        phase_name="S1901M",
        year=1901,
        season="SPRING",
        phase_type="MOVEMENT",
        powers=frozenset(["FRANCE", "GERMANY"]),
        units={"FRANCE": ["A PAR", "F BRE"], "GERMANY": ["A BER", "F KIE"]},
        supply_centers={
            "FRANCE": ["PAR", "BRE", "MAR"],
            "GERMANY": ["BER", "KIE", "MUN"],
        },
    )

    # Test order generation
    orders = await agent.decide_orders(phase)
    # Basic assertion: check if orders is a list (actual order content might vary)
    assert isinstance(orders, list)

    # Test message generation
    messages = await agent.negotiate(phase)
    # Basic assertion: check if messages is a list
    assert isinstance(messages, list)

    # Test state update
    await agent.update_state(phase, [])
    # No direct assertable output from update_state, but we check it runs without error
