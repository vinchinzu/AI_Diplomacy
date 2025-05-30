import unittest
import argparse # For mocking Namespace
from typing import Dict, List, Optional, Any

from ai_diplomacy.model_utils import assign_models_to_powers
from ai_diplomacy.game_config import GameConfig # Actual GameConfig
from ai_diplomacy.constants import DEFAULT_AGENT_MANAGER_FALLBACK_MODEL, ALL_POWERS

class TestAssignModelsToPowers(unittest.TestCase):

    def _create_mock_args(self, **kwargs) -> argparse.Namespace:
        """Creates a mock argparse.Namespace object with defaults."""
        args = argparse.Namespace()
        args.power_name = None
        args.model_id = None
        args.num_players = len(ALL_POWERS)
        args.game_id_prefix = "test_game"
        args.log_level = "INFO"
        args.perform_planning_phase = False
        args.num_negotiation_rounds = 1
        args.negotiation_style = "simultaneous"
        args.fixed_models = []
        args.randomize_fixed_models = False
        args.exclude_powers = []
        args.max_years = None
        args.log_to_file = False
        args.dev_mode = False
        args.verbose_llm_debug = False
        args.max_diary_tokens = 6500
        args.models_config_file = None # Important for _load_models_config
        args.game_id = None # To allow GameConfig to generate one

        # Apply overrides from kwargs
        for key, value in kwargs.items():
            setattr(args, key, value)
        return args

    def _create_game_config(
        self,
        power_model_assignments: Optional[Dict[str, str]] = None,
        default_model_from_config: Optional[str] = None,
        exclude_powers: Optional[List[str]] = None,
        power_name_cli: Optional[str] = None, # Renamed to avoid conflict with GameConfig attributes
        model_id_cli: Optional[str] = None,   # Renamed to avoid conflict
        num_players: int = len(ALL_POWERS),
        fixed_models_cli: Optional[List[str]] = None, # Renamed
        randomize_fixed_models_cli: bool = False # Renamed
    ) -> GameConfig:
        """
        Helper to create GameConfig for tests.
        This method now directly sets attributes on GameConfig instance
        after creating it with minimal args.
        """
        # Create minimal args needed for GameConfig constructor if it doesn't use them all
        mock_args = self._create_mock_args(
            exclude_powers=exclude_powers or [],
            power_name=power_name_cli,
            model_id=model_id_cli,
            num_players=num_players,
            fixed_models=fixed_models_cli or [],
            randomize_fixed_models=randomize_fixed_models_cli
        )
        
        config = GameConfig(args=mock_args)

        # Directly set these as they are loaded from TOML in real GameConfig init
        config.power_model_assignments = power_model_assignments or {}
        config.default_model_from_config = default_model_from_config
        
        # Ensure other relevant attributes are set if not covered by mock_args
        # (GameConfig's __init__ already handles most of these via getattr from args)
        config.exclude_powers = exclude_powers or []
        config.power_name = power_name_cli # This is the CLI override for primary agent
        config.model_id = model_id_cli     # Model for the CLI primary agent
        config.num_players = num_players
        config.fixed_models = fixed_models_cli or []
        config.randomize_fixed_models = randomize_fixed_models_cli
        
        return config

    def test_default_behavior_all_powers_llm(self):
        """All powers get fallback model if no other config and num_players = 7."""
        gc = self._create_game_config(num_players=7)
        assignments = assign_models_to_powers(game_config=gc, all_game_powers=list(ALL_POWERS))
        self.assertEqual(len(assignments), 7)
        for power in ALL_POWERS:
            self.assertEqual(assignments[power], DEFAULT_AGENT_MANAGER_FALLBACK_MODEL)

    def test_power_model_assignments_from_toml(self):
        """Powers specified in power_model_assignments (TOML) get their models."""
        toml_config = {"AUSTRIA": "model_austria", "FRANCE": "model_france"}
        gc = self._create_game_config(power_model_assignments=toml_config, num_players=7)
        assignments = assign_models_to_powers(game_config=gc, all_game_powers=list(ALL_POWERS))
        
        self.assertEqual(assignments["AUSTRIA"], "model_austria")
        self.assertEqual(assignments["FRANCE"], "model_france")
        # Others should get fallback
        for power in ALL_POWERS:
            if power not in toml_config:
                self.assertEqual(assignments[power], DEFAULT_AGENT_MANAGER_FALLBACK_MODEL)

    def test_default_model_from_config_used(self):
        """default_model_from_config is used as default if set."""
        custom_default = "custom_default_model"
        gc = self._create_game_config(default_model_from_config=custom_default, num_players=7)
        assignments = assign_models_to_powers(game_config=gc, all_game_powers=list(ALL_POWERS))
        
        self.assertEqual(len(assignments), 7)
        for power in ALL_POWERS:
            self.assertEqual(assignments[power], custom_default)

    def test_exclude_powers(self):
        """Excluded powers should not appear in the results."""
        excluded = ["ITALY", "GERMANY"]
        gc = self._create_game_config(exclude_powers=excluded, num_players=5) # 7 - 2 = 5
        assignments = assign_models_to_powers(game_config=gc, all_game_powers=list(ALL_POWERS))
        
        self.assertEqual(len(assignments), 5)
        for power in excluded:
            self.assertNotIn(power, assignments)
        for power in ALL_POWERS:
            if power not in excluded:
                self.assertIn(power, assignments)
                self.assertEqual(assignments[power], DEFAULT_AGENT_MANAGER_FALLBACK_MODEL)

    def test_primary_agent_cli_override(self):
        """Primary agent (CLI) settings override TOML and defaults."""
        toml_config = {"FRANCE": "toml_france_model"}
        gc = self._create_game_config(
            power_model_assignments=toml_config,
            power_name_cli="FRANCE", 
            model_id_cli="cli_france_model",
            num_players=7
        )
        assignments = assign_models_to_powers(game_config=gc, all_game_powers=list(ALL_POWERS))
        
        self.assertEqual(assignments["FRANCE"], "cli_france_model")
        # Ensure other TOML configs are respected if any
        # Ensure others get fallback

    def test_num_players_limit_less_than_available(self):
        """num_players limits assignments, prioritizing CLI primary, then TOML."""
        toml_config = {"AUSTRIA": "model_austria", "GERMANY": "model_germany"}
        # CLI primary: ENGLAND -> model_england
        # Order of application should be: ENGLAND (CLI), AUSTRIA (TOML), GERMANY (TOML)
        # If num_players = 1, only ENGLAND. If num_players = 2, ENGLAND, AUSTRIA.
        
        gc_np1 = self._create_game_config(
            power_model_assignments=toml_config,
            power_name_cli="ENGLAND", model_id_cli="model_england",
            num_players=1
        )
        assignments_np1 = assign_models_to_powers(game_config=gc_np1, all_game_powers=list(ALL_POWERS))
        self.assertEqual(len(assignments_np1), 1)
        self.assertEqual(assignments_np1["ENGLAND"], "model_england")

        gc_np2 = self._create_game_config(
            power_model_assignments=toml_config,
            power_name_cli="ENGLAND", model_id_cli="model_england",
            num_players=2
        )
        assignments_np2 = assign_models_to_powers(game_config=gc_np2, all_game_powers=list(ALL_POWERS))
        self.assertEqual(len(assignments_np2), 2)
        self.assertEqual(assignments_np2["ENGLAND"], "model_england")
        self.assertEqual(assignments_np2["AUSTRIA"], "model_austria") # Austria from TOML is next

        gc_np3 = self._create_game_config(
            power_model_assignments=toml_config,
            power_name_cli="ENGLAND", model_id_cli="model_england",
            num_players=3
        )
        assignments_np3 = assign_models_to_powers(game_config=gc_np3, all_game_powers=list(ALL_POWERS))
        self.assertEqual(len(assignments_np3), 3)
        self.assertIn("ENGLAND", assignments_np3)
        self.assertIn("AUSTRIA", assignments_np3)
        self.assertIn("GERMANY", assignments_np3)


    def test_num_players_limit_more_than_powers(self):
        """If num_players > available non-excluded, all non-excluded get models."""
        gc = self._create_game_config(exclude_powers=["ITALY"], num_players=7) # 6 non-excluded
        assignments = assign_models_to_powers(game_config=gc, all_game_powers=list(ALL_POWERS))
        self.assertEqual(len(assignments), 6) # Should be 6, not 7
        self.assertNotIn("ITALY", assignments)

    def test_fixed_models_cli_fill_slots(self):
        """fixed_models are used to fill remaining slots up to num_players."""
        # England (CLI primary), Austria (TOML) should be assigned first.
        # Then fixed_models should fill the rest.
        # num_players = 4. England, Austria, then 2 from fixed_models.
        gc = self._create_game_config(
            power_name_cli="ENGLAND", model_id_cli="model_england",
            power_model_assignments={"AUSTRIA": "model_austria"},
            fixed_models_cli=["fixed1", "fixed2", "fixed3"],
            num_players=4,
            randomize_fixed_models_cli=False # For predictable assignment
        )
        assignments = assign_models_to_powers(game_config=gc, all_game_powers=list(ALL_POWERS))
        
        self.assertEqual(len(assignments), 4)
        self.assertEqual(assignments["ENGLAND"], "model_england")
        self.assertEqual(assignments["AUSTRIA"], "model_austria")
        
        # The remaining 2 should be from fixed1, fixed2 for non-randomized
        # Need to know which powers are "remaining" after CLI and TOML.
        # Assuming standard ALL_POWERS order for this check after removing CLI/TOML ones.
        remaining_powers = [p for p in ALL_POWERS if p not in ["ENGLAND", "AUSTRIA"]]
        # France would be the first of remaining_powers in default sort order
        self.assertEqual(assignments[remaining_powers[0]], "fixed1") # e.g. FRANCE
        self.assertEqual(assignments[remaining_powers[1]], "fixed2") # e.g. GERMANY


    def test_fixed_models_cycling(self):
        """fixed_models cycle if num_players needs more models than available in fixed_models."""
        # num_players = 3. fixed_models = ["fx1"]. All 3 should get fx1.
        gc = self._create_game_config(
            fixed_models_cli=["fx1"],
            num_players=3,
            randomize_fixed_models_cli=False
        )
        assignments = assign_models_to_powers(game_config=gc, all_game_powers=list(ALL_POWERS))
        self.assertEqual(len(assignments), 3)
        assigned_models_list = list(assignments.values())
        # All 3 should be 'fx1'
        self.assertTrue(all(m == "fx1" for m in assigned_models_list))


    def test_complex_scenario(self):
        """Combine TOML, exclude, CLI primary, num_players limit, and fixed_models."""
        # TOML: Austria -> model_austria, Germany -> model_germany
        # Exclude: Italy
        # CLI Primary: England -> model_england
        # num_players = 4
        # fixed_models = ["fx1", "fx2"]
        # randomize = False
        # Expected assignment order:
        # 1. England (model_england) - CLI
        # 2. Austria (model_austria) - TOML
        # 3. Germany (model_germany) - TOML
        # 4. France (fx1) - fixed_models (France is the first non-excluded, non-CLI, non-TOML power)
        
        gc = self._create_game_config(
            power_model_assignments={"AUSTRIA": "model_austria", "GERMANY": "model_germany"},
            exclude_powers=["ITALY"],
            power_name_cli="ENGLAND", model_id_cli="model_england",
            num_players=4,
            fixed_models_cli=["fx1", "fx2"],
            randomize_fixed_models_cli=False
        )
        assignments = assign_models_to_powers(game_config=gc, all_game_powers=list(ALL_POWERS))

        self.assertEqual(len(assignments), 4)
        self.assertNotIn("ITALY", assignments)
        self.assertEqual(assignments["ENGLAND"], "model_england")
        self.assertEqual(assignments["AUSTRIA"], "model_austria")
        self.assertEqual(assignments["GERMANY"], "model_germany")
        
        # Determine the 4th power. It should be the first available non-excluded, non-CLI, non-TOML power.
        # ALL_POWERS = ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"] (typical order)
        # Excluded: ITALY
        # Assigned by CLI/TOML: ENGLAND, AUSTRIA, GERMANY
        # Remaining available for fixed_models, in order: FRANCE, RUSSIA, TURKEY
        self.assertEqual(assignments["FRANCE"], "fx1")


if __name__ == '__main__':
    unittest.main()
