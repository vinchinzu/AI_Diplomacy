"""
Manages the internal state of a Diplomacy agent.

This module defines the DiplomacyAgentState class, which encapsulates
an agent's goals, relationships with other powers, and private logs
(journal and diary). It provides methods for updating and formatting this state.
"""

from typing import List, Dict, Any

__all__ = ["DiplomacyAgentState"]

ALLOWED_RELATIONSHIPS = ["Enemy", "Unfriendly", "Neutral", "Friendly", "Ally"]


class DiplomacyAgentState:
    # Class docstring already exists and is good.

    def __init__(self, country: str, all_powers_in_game: List[str]):
        """
        Initializes the agent's state.

        Args:
            country (str): The country this state belongs to.
            all_powers_in_game (List[str]): A list of all powers in the game.
        """
        if country not in all_powers_in_game:
            raise ValueError(f"Invalid country '{country}'. Must be one of {all_powers_in_game}")

        self.country: str = country
        self.goals: List[str] = []
        self.relationships: Dict[str, str] = {
            power: "Neutral"
            for power in all_powers_in_game
            if power != self.country
        }
        self.private_journal: List[str] = []
        self.private_diary: List[str] = []

    def initialize_bloc_relationships(self, allied_powers: List[str], all_powers_in_game: List[str]) -> None:
        """
        Initializes relationships based on a bloc structure.
        Sets relationships to 'Ally' for bloc members and 'Enemy' for all others.

        Args:
            allied_powers (List[str]): A list of powers in the same bloc
                                       (including the agent's own country).
            all_powers_in_game (List[str]): A list of all powers in the game.
        """
        allied_powers_set = set(allied_powers)
        for power in all_powers_in_game:
            if power == self.country:
                continue

            if power in allied_powers_set:
                self.relationships[power] = "Ally"
            else:
                self.relationships[power] = "Enemy"

    def add_journal_entry(self, entry: str) -> None:
        """
        Adds an entry to the private journal.

        Args:
            entry (str): The journal entry.
        """
        if not isinstance(entry, str):
            # Or raise TypeError, depending on desired strictness
            entry = str(entry)
        self.private_journal.append(entry)
        # Logging could be added here: logging.debug(f"Journal entry added for {self.country}: {entry}")

    def add_diary_entry(self, entry: str, phase: str) -> None:
        """
        Adds a formatted entry to the private diary.

        Args:
            entry (str): The diary entry.
            phase (str): The game phase (e.g., "Spring 1901 Movement").
        """
        if not isinstance(entry, str):
            entry = str(entry)
        formatted_entry = f"[{phase}] {entry}"
        self.private_diary.append(formatted_entry)
        # Logging could be added here: logging.debug(f"Diary entry added for {self.country}: {formatted_entry}")

    def format_private_diary_for_prompt(self, max_entries: int = 40) -> str:
        """
        Formats the most recent diary entries into a single string for prompts.

        Args:
            max_entries (int): The maximum number of recent entries to include.

        Returns:
            str: A string containing the formatted diary entries, or a message
                 if the diary is empty.
        """
        if not self.private_diary:
            return "(No diary entries yet)"

        recent_entries = self.private_diary[-max_entries:]
        return "\n".join(recent_entries)

    def _update_relationships_from_events(self, own_country: str, events: List[Dict[str, Any]]) -> None:
        """
        Updates relationships based on game events.
        This is intended for internal use by the agent.

        Args:
            own_country (str): The country of the agent whose state this is.
                               (Should typically match self.country).
            events (List[Dict[str, Any]]): A list of game events.
                                           Expected event structure:
                                           {"type": "attack", "attacker": "FRANCE", "target": "GERMANY", ...}
                                           {"type": "support", "supporter": "ITALY", "supported": "AUSTRIA", ...}
        """
        if own_country != self.country:
            # Potentially log a warning if own_country doesn't match self.country
            # This might indicate a logic error elsewhere if they are expected to always match.
            pass

        relationship_levels = ALLOWED_RELATIONSHIPS

        for event in events:
            event_type = event.get("type")

            if event_type == "attack":
                attacker = event.get("attacker")
                target = event.get("target")
                if target == own_country and attacker in self.relationships:
                    current_relationship = self.relationships[attacker]
                    current_index = relationship_levels.index(current_relationship)
                    if current_index > 0:  # Not "Enemy"
                        self.relationships[attacker] = relationship_levels[current_index - 1]
                        # Logging: logging.info(f"Relationship with {attacker} worsened to {self.relationships[attacker]} due to attack.")

            elif event_type == "support":
                supporter = event.get("supporter")
                supported_player = event.get("supported")  # Assuming 'supported' holds the country name
                if supported_player == own_country and supporter in self.relationships:
                    current_relationship = self.relationships[supporter]
                    current_index = relationship_levels.index(current_relationship)
                    if current_index < len(relationship_levels) - 1:  # Not "Ally"
                        self.relationships[supporter] = relationship_levels[current_index + 1]
                        # Logging: logging.info(f"Relationship with {supporter} improved to {self.relationships[supporter]} due to support.")
            # Add handling for other event types like "betrayal" if they become relevant.
