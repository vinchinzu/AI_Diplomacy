import unittest
import os
import argparse
from unittest import mock

from ai_diplomacy.game_config import GameConfig
from diplomacy import Game  # To check type of game factory output
from scenarios import (
    SCENARIO_REGISTRY,
)  # For assertions

# Keep existing TestGameConfigLogToFile class and its methods


class TestGameConfigLogToFile(
    unittest.TestCase
):  # Original class, ensure it's preserved
    def create_args_namespace(
        self, dev_mode=False, log_to_file_arg=None, game_config_file="dummy_config.toml"
    ):
        """Helper to create an argparse.Namespace with common defaults."""
        args = {
            "game_config_file": game_config_file,  # Added game_config_file
            "power_name": None,  # Minimal set of args for GameConfig
            "model_id": None,
            # Keep other args minimal or as they were if GameConfig requires them
            # For scenario loading tests, many of these might not be strictly necessary
            # if the TOML mock provides all required fields.
            "log_level": "INFO",
            "game_id": "test_game_config_scenario",
            "log_dir": None,
            "dev_mode": dev_mode,
        }
        if log_to_file_arg is not None:  # From original helper
            args["log_to_file"] = log_to_file_arg

        # Add any other args that GameConfig constructor might expect even if not used by these tests
        # Based on GameConfig structure, it seems to mostly pull from TOML or args for overrides.
        # The critical one is game_config_file.
        # The following are defaults from the original helper that might be good to keep for general stability
        args.setdefault("num_players", 7)
        args.setdefault("game_id_prefix", "diplomacy_game")
        args.setdefault("perform_planning_phase", False)
        args.setdefault("num_negotiation_rounds", 3)
        args.setdefault("negotiation_style", "simultaneous")
        args.setdefault("fixed_models", None)
        args.setdefault("randomize_fixed_models", False)
        args.setdefault("exclude_powers", None)
        args.setdefault("max_years", None)
        args.setdefault("models_config_file", "models.toml")
        args.setdefault("verbose_llm_debug", False)
        args.setdefault("max_diary_tokens", 6500)

        return argparse.Namespace(**args)

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_log_to_file_dev_mode_true_no_env_no_arg(self):
        """Scenario 1: dev_mode=True, no env var, no arg -> log_to_file should be False"""
        args = self.create_args_namespace(dev_mode=True, log_to_file_arg=None)
        # Ensure LOG_TO_FILE is not set
        if "LOG_TO_FILE" in os.environ:
            del os.environ["LOG_TO_FILE"]

        config = GameConfig(args)
        self.assertFalse(config.log_to_file, "Should be False in dev_mode by default")

    @mock.patch.dict(os.environ, {"LOG_TO_FILE": "1"}, clear=True)
    def test_log_to_file_dev_mode_true_env_true_no_arg(self):
        """Scenario 2: dev_mode=True, LOG_TO_FILE="1", no arg -> log_to_file should be True"""
        args = self.create_args_namespace(dev_mode=True, log_to_file_arg=None)
        config = GameConfig(args)
        self.assertTrue(
            config.log_to_file, "Should be True due to LOG_TO_FILE=1 override"
        )

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_log_to_file_dev_mode_false_no_env_no_arg(self):
        """Scenario 3: dev_mode=False, no env var, no arg -> log_to_file should be True"""
        args = self.create_args_namespace(dev_mode=False, log_to_file_arg=None)
        if "LOG_TO_FILE" in os.environ:
            del os.environ["LOG_TO_FILE"]

        config = GameConfig(args)
        self.assertTrue(
            config.log_to_file, "Should be True by default when not in dev_mode"
        )

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_log_to_file_dev_mode_true_arg_true(self):
        """Scenario 4: dev_mode=True, no env var, args.log_to_file=True -> log_to_file should be True"""
        args = self.create_args_namespace(dev_mode=True, log_to_file_arg=True)
        if "LOG_TO_FILE" in os.environ:
            del os.environ["LOG_TO_FILE"]

        config = GameConfig(args)
        self.assertTrue(
            config.log_to_file, "Should be True due to explicit arg --log_to_file True"
        )

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_log_to_file_dev_mode_true_arg_false(self):
        """Scenario 5: dev_mode=True, no env var, args.log_to_file=False -> log_to_file should be False"""
        args = self.create_args_namespace(dev_mode=True, log_to_file_arg=False)
        if "LOG_TO_FILE" in os.environ:
            del os.environ["LOG_TO_FILE"]

        config = GameConfig(args)
        self.assertFalse(
            config.log_to_file,
            "Should be False due to explicit arg --log_to_file False",
        )

    @mock.patch.dict(os.environ, {"LOG_TO_FILE": "0"}, clear=True)  # Env var is not "1"
    def test_log_to_file_dev_mode_true_env_not_1_arg_true(self):
        """Test precedence: arg takes precedence over dev_mode if env var is not '1'"""
        args = self.create_args_namespace(dev_mode=True, log_to_file_arg=True)
        config = GameConfig(args)
        self.assertTrue(
            config.log_to_file,
            "Arg should override dev_mode default when LOG_TO_FILE is not '1'",
        )

    @mock.patch.dict(os.environ, {"LOG_TO_FILE": "1"}, clear=True)
    def test_log_to_file_dev_mode_true_env_true_arg_false(self):
        """Test precedence: env var '1' takes precedence over arg and dev_mode"""
        args = self.create_args_namespace(dev_mode=True, log_to_file_arg=False)
        config = GameConfig(args)
        self.assertTrue(config.log_to_file, "LOG_TO_FILE=1 should override arg False")

    # Test that os.makedirs is called (or not called) based on log_to_file
    # This requires mocking os.makedirs
    @mock.patch("os.makedirs")
    @mock.patch.dict(os.environ, {}, clear=True)
    def test_makedirs_called_when_log_to_file_true(self, mock_makedirs):
        args = self.create_args_namespace(
            dev_mode=False, log_to_file_arg=True
        )  # Ensures log_to_file is True
        config = GameConfig(args)
        self.assertTrue(config.log_to_file)
        # GameConfig calls makedirs for game_id_specific_log_dir, results_dir, manifestos_dir
        self.assertGreaterEqual(mock_makedirs.call_count, 3)
        mock_makedirs.assert_any_call(config.game_id_specific_log_dir, exist_ok=True)
        mock_makedirs.assert_any_call(config.results_dir, exist_ok=True)
        mock_makedirs.assert_any_call(config.manifestos_dir, exist_ok=True)

    @mock.patch("os.makedirs")
    @mock.patch.dict(os.environ, {}, clear=True)
    def test_makedirs_not_called_when_log_to_file_false(self, mock_makedirs):
        args = self.create_args_namespace(
            dev_mode=True, log_to_file_arg=None
        )  # Ensures log_to_file is False
        config = GameConfig(args)
        self.assertFalse(config.log_to_file)
        mock_makedirs.assert_not_called()


# New test class for scenario loading logic
class TestGameConfigScenarioLoading(unittest.TestCase):
    def create_gc_args(self, game_config_file="dummy_config.toml"):
        """Simplified arg creator for scenario tests."""
        return argparse.Namespace(
            game_config_file=game_config_file,
            # Add any other args that GameConfig's __init__ might access directly from 'args'
            # before TOML is even loaded, if any. Usually, it's just game_config_file.
            # For other args, GameConfig uses them as overrides *after* TOML.
            # So, for these tests, we can keep it minimal.
            log_level=None,  # Allow TOML to specify
            game_id=None,  # Allow TOML or auto-generation
            log_dir=None,  # Allow TOML or default
            dev_mode=False,  # Default for these tests
        )

    @mock.patch("ai_diplomacy.game_config.toml.load")
    def test_game_config_loads_scenario_from_registry(self, mock_toml_load):
        """GameConfig loads a scenario factory from SCENARIO_REGISTRY via 'scenario.game_factory'."""
        mock_toml_load.return_value = {
            "scenario": {"game_factory": "wwi_two_player"},
            "game_settings": {"num_players": 7},  # Minimal required by GameConfig
            "logging": {"log_level": "INFO"},  # Minimal required
            "agents": [{"id": "P1", "type": "human"}],  # Minimal agent config
        }
        args = self.create_gc_args()

        config = GameConfig(args)

        self.assertIsNotNone(config.game_factory)
        self.assertEqual(config.game_factory, SCENARIO_REGISTRY["wwi_two_player"])
        # Test the "Done when" condition: GameConfig(game_factory_path="wwi_two_player") can create a Game
        game = config.game_factory(entente_player="P1", central_player="P2")
        self.assertIsInstance(game, Game)

    @mock.patch("ai_diplomacy.game_config.toml.load")
    def test_game_config_loads_scenario_by_name_from_registry(self, mock_toml_load):
        """GameConfig loads a scenario factory using 'scenario.name' as key if 'game_factory' is absent."""
        mock_toml_load.return_value = {
            "scenario": {
                "name": "five_player_scenario"
            },  # No game_factory, should use name
            "game_settings": {"num_players": 5},
            "logging": {"log_level": "INFO"},
            "agents": [{"id": "P1", "type": "human"}],
        }
        args = self.create_gc_args()

        config = GameConfig(args)

        self.assertIsNotNone(config.game_factory)
        self.assertEqual(config.game_factory, SCENARIO_REGISTRY["five_player_scenario"])
        game = config.game_factory()
        self.assertIsInstance(game, Game)

    @mock.patch("ai_diplomacy.game_config.importlib.import_module")
    @mock.patch("ai_diplomacy.game_config.toml.load")
    def test_game_config_dynamic_import_fallback(
        self, mock_toml_load, mock_import_module
    ):
        """GameConfig falls back to dynamic import if factory path not in registry."""

        # 1. Define a dummy module and function for the mock to return
        mock_scenario_module = mock.MagicMock()

        def dummy_unregistered_scenario():
            return Game()

        mock_scenario_module.unregistered_scenario_test_func = (
            dummy_unregistered_scenario
        )

        # 2. Configure mock_import_module to return this dummy module
        # When import_module("some.external.module") is called, return our mock module
        mock_import_module.return_value = mock_scenario_module

        # 3. Setup TOML to point to this "external" module
        factory_path = "some.external.module.unregistered_scenario_test_func"
        mock_toml_load.return_value = {
            "scenario": {"game_factory": factory_path},
            "game_settings": {"num_players": 7},
            "logging": {"log_level": "INFO"},
            "agents": [{"id": "P1", "type": "human"}],
        }
        args = self.create_gc_args()

        config = GameConfig(args)

        self.assertIsNotNone(config.game_factory)
        self.assertEqual(config.game_factory, dummy_unregistered_scenario)
        # Check that import_module was called with the module part of the path
        mock_import_module.assert_called_once_with("some.external.module")
        game = config.game_factory()
        self.assertIsInstance(game, Game)

    @mock.patch("ai_diplomacy.game_config.toml.load")
    def test_game_config_invalid_factory_path(self, mock_toml_load):
        """GameConfig raises ValueError for an invalid factory path."""
        mock_toml_load.return_value = {
            "scenario": {"game_factory": "nonexistent.bogus_factory"},
            "game_settings": {"num_players": 7},
            "logging": {"log_level": "INFO"},
            "agents": [{"id": "P1", "type": "human"}],
        }
        args = self.create_gc_args()

        with self.assertRaises(ValueError) as context:
            GameConfig(args)

        self.assertIn("nonexistent.bogus_factory", str(context.exception))
        self.assertIn("not found in SCENARIO_REGISTRY", str(context.exception))
        self.assertIn("could not be dynamically imported", str(context.exception))

    @mock.patch("ai_diplomacy.game_config.toml.load")
    def test_game_config_no_factory_or_name_provided(self, mock_toml_load):
        """GameConfig raises ValueError if neither factory path nor scenario name is provided."""
        mock_toml_load.return_value = {
            "scenario": {},  # Empty scenario table
            "game_settings": {"num_players": 7},
            "logging": {"log_level": "INFO"},
            "agents": [{"id": "P1", "type": "human"}],
        }
        args = self.create_gc_args()

        with self.assertRaises(ValueError) as context:
            GameConfig(args)
        self.assertIn(
            "A game factory (via 'scenario.game_factory' or 'scenario.name' in TOML) is required",
            str(context.exception),
        )


if __name__ == "__main__":
    unittest.main()
