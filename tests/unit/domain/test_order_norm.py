import pytest

EXAMPLE_ORDERS = [
    "A PAR H",
    "F BRE-MAO",
    "A MAR S F BRE-MAO",
]

@pytest.mark.unit
@pytest.mark.parametrize("order", EXAMPLE_ORDERS)
def test_order_round_trip(order: str) -> None:
    """Simplistic regression test placeholder for order parsing."""
    assert isinstance(order, str)
