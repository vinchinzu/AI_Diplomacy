"""
Defines the Order class for representing a single diplomatic order.
"""

__all__ = ["Order"]


class Order:
    """Represents a single diplomatic order."""

    def __init__(self, order_text: str):
        self.order_text = order_text.strip()

    def __str__(self) -> str:
        return self.order_text

    def __repr__(self) -> str:
        return f"Order('{self.order_text}')"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Order):
            return self.order_text == other.order_text
        if isinstance(other, str):
            return self.order_text == other
        return False

    def __hash__(self) -> int:
        return hash(self.order_text)
