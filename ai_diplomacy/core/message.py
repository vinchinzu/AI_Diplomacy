"""
Defines the Message class for representing diplomatic messages.
"""
from typing import Dict

__all__ = ["Message"]

class Message:
    """Represents a diplomatic message between powers."""

    def __init__(self, recipient: str, content: str, message_type: str = "private"):
        self.recipient = recipient
        self.content = content
        self.message_type = message_type  # "private" or "global"

    def to_dict(self) -> Dict[str, str]:
        return {
            "recipient": self.recipient,
            "content": self.content,
            "message_type": self.message_type,
        }

    def __repr__(self) -> str:
        return f"Message(recipient='{self.recipient}', content='{self.content}', message_type='{self.message_type}')"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Message):
            return (
                self.recipient == other.recipient
                and self.content == other.content
                and self.message_type == other.message_type
            )
        return False

    def __hash__(self) -> int:
        return hash((self.recipient, self.content, self.message_type))
