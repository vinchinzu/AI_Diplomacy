"""
Defines the Order class for representing a single diplomatic order.
"""

from dataclasses import dataclass

__all__ = ["Order"]


@dataclass(frozen=True)
class Order:
    """Represents a single diplomatic order."""

    value: str

    def __str__(self) -> str:
        """Returns the string representation of the order."""
        return self.value 