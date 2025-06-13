import pytest

@pytest.mark.unit
def test_fake_llm_call_for_orders(fake_llm):
    """
    Test that the fake_llm fixture can be used to simulate an LLM call for orders.
    """
    prompt = "Generate orders for FRANCE"
    response = fake_llm.complete(prompt)
    assert 'orders' in response 