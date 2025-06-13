import pytest

@pytest.mark.unit
def test_rule_based_hold_agent(rule_agent, mini_board):
    """
    Test the simple rule-based hold agent.
    """
    orders = rule_agent(mini_board)
    assert "orders" in orders
    assert "FRANCE" in orders["orders"]
    assert len(orders["orders"]["FRANCE"]) == 3
    assert "A PAR H" in orders["orders"]["FRANCE"] 