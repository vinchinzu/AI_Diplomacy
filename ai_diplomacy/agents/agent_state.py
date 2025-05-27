from typing import List, Dict, Any, FrozenSet

class DiplomacyAgentState:
    """
    Manages the internal state of a Diplomacy agent, including relationships,
    goals, and private logs.
    """

    ALL_POWERS: FrozenSet[str] = frozenset({
        "AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"
    })
    ALLOWED_RELATIONSHIPS: List[str] = ["Enemy", "Unfriendly", "Neutral", "Friendly", "Ally"]

    def __init__(self, country: str):
        """
        Initializes the agent's state.

        Args:
            country (str): The country this state belongs to.
        """
        if country not in self.ALL_POWERS:
            raise ValueError(f"Invalid country '{country}'. Must be one of {self.ALL_POWERS}")

        self.country: str = country
        self.goals: List[str] = []
        self.relationships: Dict[str, str] = {
            power: "Neutral" for power in self.ALL_POWERS if power != self.country
        }
        self.private_journal: List[str] = []
        self.private_diary: List[str] = []

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

        relationship_levels = self.ALLOWED_RELATIONSHIPS
        
        for event in events:
            event_type = event.get("type")
            
            if event_type == "attack":
                attacker = event.get("attacker")
                target = event.get("target")
                if target == own_country and attacker in self.relationships:
                    current_relationship = self.relationships[attacker]
                    current_index = relationship_levels.index(current_relationship)
                    if current_index > 0: # Not "Enemy"
                        self.relationships[attacker] = relationship_levels[current_index - 1]
                        # Logging: logging.info(f"Relationship with {attacker} worsened to {self.relationships[attacker]} due to attack.")
                        
            elif event_type == "support":
                supporter = event.get("supporter")
                supported_player = event.get("supported") # Assuming 'supported' holds the country name
                if supported_player == own_country and supporter in self.relationships:
                    current_relationship = self.relationships[supporter]
                    current_index = relationship_levels.index(current_relationship)
                    if current_index < len(relationship_levels) - 1: # Not "Ally"
                        self.relationships[supporter] = relationship_levels[current_index + 1]
                        # Logging: logging.info(f"Relationship with {supporter} improved to {self.relationships[supporter]} due to support.")
            # Add handling for other event types like "betrayal" if they become relevant.

# Example Usage (can be removed or kept for testing)
if __name__ == "__main__":
    # Create a state for France
    french_state = DiplomacyAgentState("FRANCE")
    print(f"Initial state for {french_state.country}:")
    print(f"  Goals: {french_state.goals}")
    print(f"  Relationships: {french_state.relationships}")

    # Add some diary and journal entries
    french_state.add_diary_entry("Planning to move to Burgundy.", "Spring 1901 Movement")
    french_state.add_journal_entry("Germany seems suspicious. They moved an army to Ruhr.")
    french_state.add_diary_entry("Successfully moved to Burgundy.", "Spring 1901 Retreats") # Assuming phase name
    french_state.add_journal_entry("Italy proposed an alliance. Considering it.")

    print(f"\nPrivate Journal for {french_state.country}:")
    for entry in french_state.private_journal:
        print(f"- {entry}")

    print(f"\nPrivate Diary for {french_state.country} (formatted for prompt):")
    print(french_state.format_private_diary_for_prompt())

    # Simulate some game events
    print(f"\nSimulating game events for {french_state.country}...")
    events_affecting_france = [
        {"type": "attack", "attacker": "GERMANY", "target": "FRANCE", "details": "Munich attacks Burgundy"},
        {"type": "support", "supporter": "ITALY", "supported": "FRANCE", "details": "Rome supports Paris holds"},
        {"type": "attack", "attacker": "ENGLAND", "target": "FRANCE", "details": "London attacks Brest"},
        {"type": "attack", "attacker": "GERMANY", "target": "RUSSIA", "details": "Berlin attacks Warsaw"}, # Should not affect France's relationships
        {"type": "support", "supporter": "AUSTRIA", "supported": "ITALY", "details": "Vienna supports Rome"}, # Should not affect France's relationships
        {"type": "attack", "attacker": "TURKEY", "target": "FRANCE"} # Test repeated attack
    ]

    print(f"Relationships before events: {french_state.relationships}")
    french_state._update_relationships_from_events(own_country="FRANCE", events=events_affecting_france)
    print(f"Relationships after events: {french_state.relationships}")

    # Test edge cases for relationships
    print("\nTesting relationship boundaries...")
    french_state.relationships["ITALY"] = "Ally"
    french_state.relationships["GERMANY"] = "Enemy"
    print(f"Relationships set to extremes: {french_state.relationships}")
    
    boundary_test_events = [
        {"type": "attack", "attacker": "GERMANY", "target": "FRANCE"}, # Germany is already Enemy
        {"type": "support", "supporter": "ITALY", "supported": "FRANCE"}  # Italy is already Ally
    ]
    french_state._update_relationships_from_events(own_country="FRANCE", events=boundary_test_events)
    print(f"Relationships after boundary tests: {french_state.relationships}")

    # Test initialization with an invalid country
    try:
        invalid_state = DiplomacyAgentState("ATLANTIS")
    except ValueError as e:
        print(f"\nError creating state for invalid country: {e}")

    # Test formatting empty diary
    empty_diary_state = DiplomacyAgentState("AUSTRIA")
    print(f"\nFormatted empty diary: {empty_diary_state.format_private_diary_for_prompt()}")
