import unittest
import os
import argparse
from unittest import mock

from ai_diplomacy.game_config import GameConfig

class TestGameConfigLogToFile(unittest.TestCase):

    def create_args_namespace(self, dev_mode=False, log_to_file_arg=None):
        """Helper to create an argparse.Namespace with common defaults."""
        args = {
            "power_name": None, "model_id": None, "num_players": 7,
            "game_id_prefix": "diplomacy_game", "log_level": "INFO",
            "perform_planning_phase": False, "num_negotiation_rounds": 3,
            "negotiation_style": "simultaneous", "fixed_models": None,
            "randomize_fixed_models": False, "exclude_powers": None,
            "max_years": None, "models_config_file": "models.toml",
            "game_id": "test_game_config_log", "log_dir": None, # Important for path derivation
            "verbose_llm_debug": False, "max_diary_tokens": 6500,
            # Test-specific values:
            "dev_mode": dev_mode,
            # log_to_file_arg will be used to set 'log_to_file' only if not None
        }
        if log_to_file_arg is not None:
            args["log_to_file"] = log_to_file_arg
        
        return argparse.Namespace(**args)

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_log_to_file_dev_mode_true_no_env_no_arg(self):
        """Scenario 1: dev_mode=True, no env var, no arg -> log_to_file should be False"""
        args = self.create_args_namespace(dev_mode=True, log_to_file_arg=None)
        # Ensure LOG_TO_FILE is not set
        if "LOG_TO_FILE" in os.environ: del os.environ["LOG_TO_FILE"]
        
        config = GameConfig(args)
        self.assertFalse(config.log_to_file, "Should be False in dev_mode by default")

    @mock.patch.dict(os.environ, {"LOG_TO_FILE": "1"}, clear=True)
    def test_log_to_file_dev_mode_true_env_true_no_arg(self):
        """Scenario 2: dev_mode=True, LOG_TO_FILE="1", no arg -> log_to_file should be True"""
        args = self.create_args_namespace(dev_mode=True, log_to_file_arg=None)
        config = GameConfig(args)
        self.assertTrue(config.log_to_file, "Should be True due to LOG_TO_FILE=1 override")

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_log_to_file_dev_mode_false_no_env_no_arg(self):
        """Scenario 3: dev_mode=False, no env var, no arg -> log_to_file should be True"""
        args = self.create_args_namespace(dev_mode=False, log_to_file_arg=None)
        if "LOG_TO_FILE" in os.environ: del os.environ["LOG_TO_FILE"]
        
        config = GameConfig(args)
        self.assertTrue(config.log_to_file, "Should be True by default when not in dev_mode")

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_log_to_file_dev_mode_true_arg_true(self):
        """Scenario 4: dev_mode=True, no env var, args.log_to_file=True -> log_to_file should be True"""
        args = self.create_args_namespace(dev_mode=True, log_to_file_arg=True)
        if "LOG_TO_FILE" in os.environ: del os.environ["LOG_TO_FILE"]

        config = GameConfig(args)
        self.assertTrue(config.log_to_file, "Should be True due to explicit arg --log_to_file True")

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_log_to_file_dev_mode_true_arg_false(self):
        """Scenario 5: dev_mode=True, no env var, args.log_to_file=False -> log_to_file should be False"""
        args = self.create_args_namespace(dev_mode=True, log_to_file_arg=False)
        if "LOG_TO_FILE" in os.environ: del os.environ["LOG_TO_FILE"]

        config = GameConfig(args)
        self.assertFalse(config.log_to_file, "Should be False due to explicit arg --log_to_file False")

    @mock.patch.dict(os.environ, {"LOG_TO_FILE": "0"}, clear=True) # Env var is not "1"
    def test_log_to_file_dev_mode_true_env_not_1_arg_true(self):
        """Test precedence: arg takes precedence over dev_mode if env var is not '1'"""
        args = self.create_args_namespace(dev_mode=True, log_to_file_arg=True)
        config = GameConfig(args)
        self.assertTrue(config.log_to_file, "Arg should override dev_mode default when LOG_TO_FILE is not '1'")

    @mock.patch.dict(os.environ, {"LOG_TO_FILE": "1"}, clear=True)
    def test_log_to_file_dev_mode_true_env_true_arg_false(self):
        """Test precedence: env var '1' takes precedence over arg and dev_mode"""
        args = self.create_args_namespace(dev_mode=True, log_to_file_arg=False)
        config = GameConfig(args)
        self.assertTrue(config.log_to_file, "LOG_TO_FILE=1 should override arg False")
        
    # Test that os.makedirs is called (or not called) based on log_to_file
    # This requires mocking os.makedirs
    @mock.patch('os.makedirs')
    @mock.patch.dict(os.environ, {}, clear=True)
    def test_makedirs_called_when_log_to_file_true(self, mock_makedirs):
        args = self.create_args_namespace(dev_mode=False, log_to_file_arg=True) # Ensures log_to_file is True
        config = GameConfig(args)
        self.assertTrue(config.log_to_file)
        # GameConfig calls makedirs for game_id_specific_log_dir, results_dir, manifestos_dir
        self.assertGreaterEqual(mock_makedirs.call_count, 3)
        mock_makedirs.assert_any_call(config.game_id_specific_log_dir, exist_ok=True)
        mock_makedirs.assert_any_call(config.results_dir, exist_ok=True)
        mock_makedirs.assert_any_call(config.manifestos_dir, exist_ok=True)

    @mock.patch('os.makedirs')
    @mock.patch.dict(os.environ, {}, clear=True)
    def test_makedirs_not_called_when_log_to_file_false(self, mock_makedirs):
        args = self.create_args_namespace(dev_mode=True, log_to_file_arg=None) # Ensures log_to_file is False
        config = GameConfig(args)
        self.assertFalse(config.log_to_file)
        mock_makedirs.assert_not_called()


if __name__ == '__main__':
    unittest.main()
