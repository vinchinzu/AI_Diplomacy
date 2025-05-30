import unittest
from ai_diplomacy.agents.agent_state import DiplomacyAgentState
from ai_diplomacy import constants # Import constants

class TestDiplomacyAgentState(unittest.TestCase):

    def setUp(self):
        """Setup for each test method."""
        self.test_country = "ENGLAND"
        self.state = DiplomacyAgentState(self.test_country)
        # Ensure ALL_POWERS for tests is consistent with the class
        self.all_powers_set = constants.ALL_POWERS # Use imported constant

    def test_initialization(self):
        self.assertEqual(self.state.country, self.test_country)
        self.assertEqual(self.state.goals, [])
        self.assertEqual(self.state.private_journal, [])
        self.assertEqual(self.state.private_diary, [])

        # Test relationships
        expected_relationships = {
            power: "Neutral" for power in self.all_powers_set if power != self.test_country
        }
        self.assertEqual(self.state.relationships, expected_relationships)
        self.assertNotIn(self.test_country, self.state.relationships)
        self.assertEqual(len(self.state.relationships), len(self.all_powers_set) - 1)

    def test_initialization_invalid_country(self):
        with self.assertRaises(ValueError):
            DiplomacyAgentState("WONDERLAND")

    def test_add_journal_entry(self):
        self.state.add_journal_entry("First entry.")
        self.assertEqual(self.state.private_journal, ["First entry."])
        
        self.state.add_journal_entry("Second entry.")
        self.assertEqual(self.state.private_journal, ["First entry.", "Second entry."])

        self.state.add_journal_entry(123) # Non-string entry
        self.assertEqual(self.state.private_journal, ["First entry.", "Second entry.", "123"])

    def test_add_diary_entry(self):
        phase1 = "Spring 1901 Movement"
        entry1 = "Moved to Paris."
        self.state.add_diary_entry(entry1, phase1)
        self.assertEqual(self.state.private_diary, [f"[{phase1}] {entry1}"])

        phase2 = "Fall 1901 Retreats"
        entry2 = 456 # Non-string entry
        self.state.add_diary_entry(entry2, phase2)
        self.assertEqual(self.state.private_diary, [f"[{phase1}] {entry1}", f"[{phase2}] {str(entry2)}"])

    def test_format_private_diary_for_prompt(self):
        # Test empty diary
        self.assertEqual(self.state.format_private_diary_for_prompt(), "(No diary entries yet)")

        # Test with fewer entries than max_entries
        self.state.add_diary_entry("Entry 1", "Phase 1")
        self.state.add_diary_entry("Entry 2", "Phase 2")
        expected_output_2_entries = "[Phase 1] Entry 1\n[Phase 2] Entry 2"
        self.assertEqual(self.state.format_private_diary_for_prompt(max_entries=5), expected_output_2_entries)

        # Test with more entries than max_entries
        self.state.add_diary_entry("Entry 3", "Phase 3")
        self.state.add_diary_entry("Entry 4", "Phase 4")
        self.state.add_diary_entry("Entry 5", "Phase 5")
        
        # max_entries = 3
        expected_output_3_entries = "[Phase 3] Entry 3\n[Phase 4] Entry 4\n[Phase 5] Entry 5"
        self.assertEqual(self.state.format_private_diary_for_prompt(max_entries=3), expected_output_3_entries)
        
        expected_output_2_entries_from_5 = "[Phase 4] Entry 4\n[Phase 5] Entry 5"
        self.assertEqual(self.state.format_private_diary_for_prompt(max_entries=2), expected_output_2_entries_from_5)

    def test_update_relationships_from_events_no_events(self):
        initial_relationships = self.state.relationships.copy()
        self.state._update_relationships_from_events(self.test_country, [])
        self.assertEqual(self.state.relationships, initial_relationships)

    def test_update_relationships_from_events_attack(self):
        # Attacker: FRANCE, Target: ENGLAND (own_country)
        events = [{"type": "attack", "attacker": "FRANCE", "target": self.test_country}]
        self.state._update_relationships_from_events(self.test_country, events)
        self.assertEqual(self.state.relationships["FRANCE"], "Unfriendly")

        # Attacker: GERMANY, Target: ENGLAND (own_country), already Unfriendly
        self.state.relationships["GERMANY"] = "Unfriendly"
        events = [{"type": "attack", "attacker": "GERMANY", "target": self.test_country}]
        self.state._update_relationships_from_events(self.test_country, events)
        self.assertEqual(self.state.relationships["GERMANY"], "Enemy")
        
        # Attacker: ITALY, Target: ENGLAND (own_country), ITALY is Enemy
        self.state.relationships["ITALY"] = "Enemy"
        events = [{"type": "attack", "attacker": "ITALY", "target": self.test_country}]
        self.state._update_relationships_from_events(self.test_country, events)
        self.assertEqual(self.state.relationships["ITALY"], "Enemy") # Stays Enemy

        # Attack on another country (FRANCE attacks GERMANY)
        initial_french_german_relationship_for_england = (
            self.state.relationships.get("FRANCE"), self.state.relationships.get("GERMANY")
        )
        events = [{"type": "attack", "attacker": "FRANCE", "target": "GERMANY"}]
        self.state._update_relationships_from_events(self.test_country, events)
        self.assertEqual(self.state.relationships.get("FRANCE"), initial_french_german_relationship_for_england[0])
        self.assertEqual(self.state.relationships.get("GERMANY"), initial_french_german_relationship_for_england[1])
        
        # Attack by own_country (ENGLAND attacks RUSSIA) - should not change relationship with RUSSIA via this method
        initial_russian_relationship = self.state.relationships["RUSSIA"]
        events = [{"type": "attack", "attacker": self.test_country, "target": "RUSSIA"}]
        self.state._update_relationships_from_events(self.test_country, events)
        self.assertEqual(self.state.relationships["RUSSIA"], initial_russian_relationship)
        
        # Attack by a country not in relationships (e.g. a new power "SPAIN")
        initial_relationships = self.state.relationships.copy()
        events = [{"type": "attack", "attacker": "SPAIN", "target": self.test_country}]
        self.state._update_relationships_from_events(self.test_country, events)
        self.assertEqual(self.state.relationships, initial_relationships) # No change, SPAIN not a known power

    def test_update_relationships_from_events_support(self):
        # Supporter: FRANCE, Supported: ENGLAND (own_country)
        events = [{"type": "support", "supporter": "FRANCE", "supported": self.test_country}]
        self.state._update_relationships_from_events(self.test_country, events)
        self.assertEqual(self.state.relationships["FRANCE"], "Friendly")

        # Supporter: GERMANY, Supported: ENGLAND (own_country), GERMANY is Friendly
        self.state.relationships["GERMANY"] = "Friendly"
        events = [{"type": "support", "supporter": "GERMANY", "supported": self.test_country}]
        self.state._update_relationships_from_events(self.test_country, events)
        self.assertEqual(self.state.relationships["GERMANY"], "Ally")

        # Supporter: ITALY, Supported: ENGLAND (own_country), ITALY is Ally
        self.state.relationships["ITALY"] = "Ally"
        events = [{"type": "support", "supporter": "ITALY", "supported": self.test_country}]
        self.state._update_relationships_from_events(self.test_country, events)
        self.assertEqual(self.state.relationships["ITALY"], "Ally") # Stays Ally
        
        # Supporter: RUSSIA, Supported: ENGLAND (own_country), RUSSIA is Enemy
        self.state.relationships["RUSSIA"] = "Enemy"
        events = [{"type": "support", "supporter": "RUSSIA", "supported": self.test_country}]
        self.state._update_relationships_from_events(self.test_country, events)
        self.assertEqual(self.state.relationships["RUSSIA"], "Unfriendly") # Enemy -> Unfriendly

        # Support for another country (FRANCE supports GERMANY)
        initial_french_german_relationship_for_england = (
            self.state.relationships.get("FRANCE"), self.state.relationships.get("GERMANY")
        )
        events = [{"type": "support", "supporter": "FRANCE", "supported": "GERMANY"}]
        self.state._update_relationships_from_events(self.test_country, events)
        self.assertEqual(self.state.relationships.get("FRANCE"), initial_french_german_relationship_for_england[0])
        self.assertEqual(self.state.relationships.get("GERMANY"), initial_french_german_relationship_for_england[1])

        # Support by own_country (ENGLAND supports RUSSIA) - should not change relationship with RUSSIA via this method
        initial_russian_relationship = self.state.relationships["RUSSIA"]
        events = [{"type": "support", "supporter": self.test_country, "supported": "RUSSIA"}]
        self.state._update_relationships_from_events(self.test_country, events)
        self.assertEqual(self.state.relationships["RUSSIA"], initial_russian_relationship)

        # Support by a country not in relationships (e.g. a new power "SPAIN")
        initial_relationships = self.state.relationships.copy()
        events = [{"type": "support", "supporter": "SPAIN", "supported": self.test_country}]
        self.state._update_relationships_from_events(self.test_country, events)
        self.assertEqual(self.state.relationships, initial_relationships) # No change, SPAIN not a known power

    def test_update_relationships_from_events_mixed(self):
        # Initial: FRANCE Neutral, GERMANY Neutral, ITALY Neutral
        events = [
            {"type": "attack", "attacker": "FRANCE", "target": self.test_country},    # FRANCE -> Unfriendly
            {"type": "support", "supporter": "GERMANY", "supported": self.test_country}, # GERMANY -> Friendly
            {"type": "attack", "attacker": "FRANCE", "target": self.test_country}     # FRANCE Unfriendly -> Enemy
        ]
        self.state._update_relationships_from_events(self.test_country, events)
        self.assertEqual(self.state.relationships["FRANCE"], "Enemy")
        self.assertEqual(self.state.relationships["GERMANY"], "Friendly")
        self.assertEqual(self.state.relationships["ITALY"], "Neutral") # Unchanged

    def test_update_relationships_from_events_boundaries(self):
        # Test Enemy attacking -> remains Enemy
        self.state.relationships["FRANCE"] = "Enemy"
        events_attack_enemy = [{"type": "attack", "attacker": "FRANCE", "target": self.test_country}]
        self.state._update_relationships_from_events(self.test_country, events_attack_enemy)
        self.assertEqual(self.state.relationships["FRANCE"], "Enemy")

        # Test Ally supporting -> remains Ally
        self.state.relationships["GERMANY"] = "Ally"
        events_support_ally = [{"type": "support", "supporter": "GERMANY", "supported": self.test_country}]
        self.state._update_relationships_from_events(self.test_country, events_support_ally)
        self.assertEqual(self.state.relationships["GERMANY"], "Ally")

        # Test multiple attacks to reach Enemy
        self.state.relationships["ITALY"] = "Friendly" # Friendly -> Neutral -> Unfriendly -> Enemy
        events = [
            {"type": "attack", "attacker": "ITALY", "target": self.test_country}, # Friendly -> Neutral
            {"type": "attack", "attacker": "ITALY", "target": self.test_country}, # Neutral -> Unfriendly
            {"type": "attack", "attacker": "ITALY", "target": self.test_country}  # Unfriendly -> Enemy
        ]
        self.state._update_relationships_from_events(self.test_country, events)
        self.assertEqual(self.state.relationships["ITALY"], "Enemy")
        
        # Test multiple supports to reach Ally
        self.state.relationships["RUSSIA"] = "Unfriendly" # Unfriendly -> Neutral -> Friendly -> Ally
        events = [
            {"type": "support", "supporter": "RUSSIA", "supported": self.test_country}, # Unfriendly -> Neutral
            {"type": "support", "supporter": "RUSSIA", "supported": self.test_country}, # Neutral -> Friendly
            {"type": "support", "supporter": "RUSSIA", "supported": self.test_country}  # Friendly -> Ally
        ]
        self.state._update_relationships_from_events(self.test_country, events)
        self.assertEqual(self.state.relationships["RUSSIA"], "Ally")

    def test_update_relationships_own_country_mismatch(self):
        # This tests that if own_country provided to the method differs from self.country,
        # the updates still happen based on the provided own_country.
        # The method's docstring notes this possibility.
        # Let's assume ENGLAND is self.country, but we pass "FRANCE" as own_country to the method.
        # We want to see if ENGLAND's relationships change based on events *targeting FRANCE*.

        # GERMANY attacks FRANCE. ENGLAND's relationship with GERMANY should worsen.
        self.state.relationships["GERMANY"] = "Neutral"
        events = [{"type": "attack", "attacker": "GERMANY", "target": "FRANCE"}]
        self.state._update_relationships_from_events(own_country="FRANCE", events=events)
        # Since the event is about FRANCE, and self.state is for ENGLAND,
        # ENGLAND's relationship with GERMANY should change if GERMANY attacks FRANCE.
        # This seems to be how the logic is written: if target == own_country (passed to method).
        # This might be an area for clarification in the original class if this behavior is not intended.
        # Based on current implementation:
        self.assertEqual(self.state.relationships["GERMANY"], "Unfriendly")


        # ITALY supports FRANCE. ENGLAND's relationship with ITALY should improve.
        self.state.relationships["ITALY"] = "Neutral"
        events = [{"type": "support", "supporter": "ITALY", "supported": "FRANCE"}]
        self.state._update_relationships_from_events(own_country="FRANCE", events=events)
        self.assertEqual(self.state.relationships["ITALY"], "Friendly")


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
