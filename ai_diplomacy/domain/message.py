"""
Defines the Message class for representing diplomatic messages.
"""

from dataclasses import dataclass, asdict
from typing import Dict

__all__ = ["Message"]


@dataclass(frozen=True)
class Message:
    """Represents a diplomatic message between powers."""

    recipient: str
    content: str
    message_type: str = "private"  # "private" or "global"

    def to_dict(self) -> Dict[str, str]:
        """Returns a dictionary representation of the message."""
        return asdict(self) 