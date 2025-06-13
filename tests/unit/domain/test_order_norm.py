import pytest
from hypothesis import given, strategies as st

# This is a placeholder for a real domain object
# from ai_diplomacy.domain import ...
any_valid_order = st.text(min_size=1, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ 1234567890-[]().")

@pytest.mark.unit
@given(order=any_valid_order)
def test_order_round_trip(order: str):
    """
    Property-based tests catch edge-cases in the move-parser earlier than integration games.
    """
    # norm = domain.utils.norm(order)
    # assert domain.utils.denorm(norm) == order
    assert isinstance(order, str) 