import pytest

@pytest.mark.integration
def test_negotiation_rounds(fake_llm):
    """
    Test the negotiation logic between agents using the fake_llm.
    """
    # This test will require the negotiation part of the engine
    # 1. Setup two agents
    # 2. Run a few rounds of negotiation
    # 3. Assert that messages are exchanged and state is updated
    assert fake_llm is not None 