from dataclasses import dataclass

@dataclass(frozen=True)
class Order:
    """Represents a single order."""
    # This will be filled out later
    value: str
