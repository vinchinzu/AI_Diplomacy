import unittest
import os
import json
import logging
from unittest import mock  # For mock.patch and mock.patch.dict

from ai_diplomacy.logging_setup import (
    get_log_paths,
    JsonFormatter,
    setup_logging,
)
from ai_diplomacy.game_config import (
    GameConfig,
)  # Needed for setup_logging and GameConfig tests


# Helper to create a dummy GameConfig for tests
def make_dummy_game_config(
    log_level="INFO", log_to_file=False, general_log_path=None, verbose_llm_debug=False
):
    # Mock argparse.Namespace
    args = mock.Mock()
    args.log_level = log_level
    args.log_to_file = log_to_file  # This will be used by GameConfig's logic
    args.general_log_path = (
        general_log_path if general_log_path else "dummy_general.log"
    )  # Path for GameConfig internal use
    args.game_id = "test_game_123"  # GameConfig needs a game_id
    args.log_dir = None  # Let GameConfig derive paths
    args.dev_mode = False  # Default, can be overridden in specific tests
    args.verbose_llm_debug = verbose_llm_debug

    # Ensure models_config_file is a string, as GameConfig will use it with os.path.exists
    # This path is used by GameConfig._load_models_config()
    args.models_config_file = (
        "dummy_test_models.toml"  # Explicitly set to a string path
    )

    # Add other attributes expected by GameConfig if not covered by getattr defaults
    # These are based on GameConfig structure.
    config_attrs = {
        "power_name": None,
        "model_id": None,
        "num_players": 7,
        "game_id_prefix": "diplomacy_game",
        "perform_planning_phase": False,
        "num_negotiation_rounds": 3,
        "negotiation_style": "simultaneous",
        "fixed_models": None,
        "randomize_fixed_models": False,
        "exclude_powers": None,
        "max_years": None,
        # "models_config_file": "models.toml", # Now explicitly set above to "dummy_test_models.toml"
        "max_diary_tokens": 6500,
    }
    for attr, val in config_attrs.items():
        if not hasattr(
            args, attr
        ):  # only set if not already set (e.g. by test-specific overrides)
            setattr(args, attr, val)

    return GameConfig(args)


class TestGetLogPaths(unittest.TestCase):
    def test_get_log_paths_structure_and_content(self):
        game_id = "test_game_alpha"
        base_log_dir = "/tmp/test_logs"

        expected_game_id_specific_log_dir = os.path.join(base_log_dir, game_id)
        expected_llm_log_path = os.path.join(
            expected_game_id_specific_log_dir, f"{game_id}_llm_interactions.csv"
        )
        expected_general_log_path = os.path.join(
            expected_game_id_specific_log_dir, f"{game_id}_general.log"
        )
        expected_results_dir = os.path.join(
            expected_game_id_specific_log_dir, "results"
        )
        expected_manifestos_dir = os.path.join(expected_results_dir, "manifestos")

        paths = get_log_paths(game_id, base_log_dir)

        self.assertIsInstance(paths, dict)
        self.assertIn("game_id_specific_log_dir", paths)
        self.assertIn("llm_log_path", paths)
        self.assertIn("general_log_path", paths)
        self.assertIn("results_dir", paths)
        self.assertIn("manifestos_dir", paths)

        self.assertEqual(
            paths["game_id_specific_log_dir"], expected_game_id_specific_log_dir
        )
        self.assertEqual(paths["llm_log_path"], expected_llm_log_path)
        self.assertEqual(paths["general_log_path"], expected_general_log_path)
        self.assertEqual(paths["results_dir"], expected_results_dir)
        self.assertEqual(paths["manifestos_dir"], expected_manifestos_dir)

    def test_get_log_paths_different_inputs(self):
        game_id = "another_game_456"
        base_log_dir = "test_data/game_logs"  # Relative path

        expected_game_id_specific_log_dir = os.path.join(base_log_dir, game_id)
        # Only check one path for brevity, assuming os.path.join works consistently
        expected_llm_log_path = os.path.join(
            expected_game_id_specific_log_dir, f"{game_id}_llm_interactions.csv"
        )

        paths = get_log_paths(game_id, base_log_dir)
        self.assertEqual(paths["llm_log_path"], expected_llm_log_path)


class TestJsonFormatter(unittest.TestCase):
    def setUp(self):
        self.formatter = JsonFormatter()
        self.record_dict = {
            "name": "test.logger",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "pathname": "test_script.py",
            "filename": "test_script.py",
            "module": "test_script",
            "lineno": 123,
            "funcName": "test_function",
            "created": 1678886400.0,  # Example timestamp
            "asctime": "2023-03-15 12:00:00,000",  # Will be overridden by formatter
            "msecs": 0.0,
            "relativeCreated": 0.0,
            "thread": 12345,
            "threadName": "MainThread",
            "process": 6789,
            "message": "This is a test message with parameters: %s, %d",
            "args": ("hello", 42),
            "msg": "This is a test message with parameters: %s, %d",  # Raw message
        }
        self.record = logging.makeLogRecord(self.record_dict)
        # Re-assign asctime as makeLogRecord might not set it if formatter is not present on a handler
        # and JsonFormatter relies on super().format(record) which uses default_time_format
        # For consistent testing, we can also mock record.asctime if needed.
        # Or, we can let JsonFormatter's super().format() generate it.

    def test_basic_log_formatting(self):
        formatted_json_str = self.formatter.format(self.record)
        log_output = json.loads(formatted_json_str)

        self.assertEqual(log_output["name"], self.record.name)
        self.assertEqual(log_output["level"], self.record.levelname)
        # getMessage() resolves msg % args
        self.assertEqual(log_output["message"], self.record.getMessage())
        self.assertEqual(log_output["source"]["pathname"], self.record.pathname)
        self.assertEqual(log_output["source"]["lineno"], self.record.lineno)
        self.assertEqual(log_output["source"]["function"], self.record.funcName)
        self.assertIn(
            "timestamp", log_output
        )  # Check presence, exact value depends on Formatter's asctime

    def test_log_formatting_with_exception(self):
        try:
            raise ValueError("Test exception")
        except ValueError:
            # exc_info=True would capture it in a real logging call
            # Here we manually create it for the record
            import sys

            exc_info = sys.exc_info()
            self.record.exc_info = exc_info
            # The super().format(record) call in JsonFormatter will populate exc_text
            # self.record.exc_text = self.formatter.formatException(exc_info) # Not needed if super().format() is called

        formatted_json_str = self.formatter.format(self.record)
        log_output = json.loads(formatted_json_str)

        self.assertIn("exception", log_output)
        self.assertEqual(log_output["exception"]["type"], "ValueError")
        self.assertEqual(log_output["exception"]["message"], "Test exception")
        self.assertIn("stacktrace", log_output["exception"])
        self.assertTrue(len(log_output["exception"]["stacktrace"]) > 0)

    def test_log_formatting_with_extra_fields(self):
        self.record.extra_field_str = "extra_value"
        self.record.extra_field_int = 12345
        self.record.extra_field_dict = {"key": "val"}

        formatted_json_str = self.formatter.format(self.record)
        log_output = json.loads(formatted_json_str)

        self.assertIn("extra", log_output)
        self.assertEqual(log_output["extra"]["extra_field_str"], "extra_value")
        self.assertEqual(log_output["extra"]["extra_field_int"], 12345)
        self.assertEqual(log_output["extra"]["extra_field_dict"], {"key": "val"})

    def test_unserializable_extra_field_fallback(self):
        # This object won't be JSON serializable by default
        class Unserializable:
            pass

        self.record.unserializable = Unserializable()

        formatted_json_str = self.formatter.format(self.record)
        log_output = json.loads(formatted_json_str)

        # The formatter should now handle this by trying to convert to string or skipping
        # Based on the current JsonFormatter, it might skip or convert to str if that logic is added.
        # My current JsonFormatter in previous step only includes basic types for 'extra'.
        # So 'unserializable' should not be present in 'extra' if it's not a basic type.
        # If the formatter were to try str(value), it would be present.
        # Let's test based on the provided JsonFormatter which skips non-basic types for 'extra'.
        if "extra" in log_output and "unserializable" in log_output["extra"]:
            self.assertIsInstance(
                log_output["extra"]["unserializable"], str
            )  # if it converts to str
        # else:
        # If it strictly skips, 'unserializable' won't be in 'extra', or 'extra' might not be there if it's the only one.
        # self.assertNotIn('unserializable', log_output.get('extra', {}))
        # The current JsonFormatter I wrote for the previous step for 'extra' fields is:
        # if isinstance(value, (str, bool, int, float, list, dict, type(None))):
        # So, Unserializable() will be skipped.
        self.assertNotIn("unserializable", log_output.get("extra", {}))


class TestSetupLoggingFormatSelection(unittest.TestCase):
    def setUp(self):
        # Ensure a clean state for root logger handlers
        self.root_logger = logging.getLogger()
        self.original_handlers = self.root_logger.handlers[:]
        for handler in self.original_handlers:
            self.root_logger.removeHandler(handler)
            handler.close()

        # Minimal GameConfig mock
        self.mock_game_config = make_dummy_game_config(
            log_to_file=False
        )  # Don't need file handler for this test

    def tearDown(self):
        # Restore original handlers
        current_handlers = self.root_logger.handlers[:]
        for handler in current_handlers:
            self.root_logger.removeHandler(handler)
            handler.close()
        for handler in self.original_handlers:
            self.root_logger.addHandler(handler)
        # Reset logging level if necessary, though setup_logging sets it
        # logging.getLogger().setLevel(logging.WARNING) # Or original level

    @mock.patch.dict(os.environ, {"LOG_FORMAT": "JSON"})
    def test_setup_logging_uses_json_formatter_when_env_set(self):
        setup_logging(self.mock_game_config)
        # Check console handler (assuming it's the first one or named specifically if possible)
        # For simplicity, checking all handlers on the root logger.
        # In a default setup, there's usually at least a console handler.
        found_json_formatter = False
        for handler in self.root_logger.handlers:
            if isinstance(handler.formatter, JsonFormatter):
                found_json_formatter = True
                break
        self.assertTrue(
            found_json_formatter, "JsonFormatter should be used when LOG_FORMAT=JSON"
        )

    @mock.patch.dict(os.environ, {}, clear=True)  # Clear LOG_FORMAT
    def test_setup_logging_uses_default_formatter_when_env_not_set(self):
        # Ensure LOG_FORMAT is not set, or set to something other than JSON
        if "LOG_FORMAT" in os.environ:  # Should be cleared by clear=True
            del os.environ["LOG_FORMAT"]

        setup_logging(self.mock_game_config)
        found_default_formatter = False
        for handler in self.root_logger.handlers:
            # Default formatter is logging.Formatter, not JsonFormatter
            if isinstance(handler.formatter, logging.Formatter) and not isinstance(
                handler.formatter, JsonFormatter
            ):
                found_default_formatter = True
                break
        self.assertTrue(
            found_default_formatter,
            "Default Formatter should be used when LOG_FORMAT is not JSON",
        )

    @mock.patch.dict(os.environ, {"LOG_FORMAT": "text"})  # Explicitly non-JSON
    def test_setup_logging_uses_default_formatter_when_env_is_not_json(self):
        setup_logging(self.mock_game_config)
        found_default_formatter = False
        for handler in self.root_logger.handlers:
            if isinstance(handler.formatter, logging.Formatter) and not isinstance(
                handler.formatter, JsonFormatter
            ):
                found_default_formatter = True
                break
        self.assertTrue(
            found_default_formatter,
            "Default Formatter should be used when LOG_FORMAT is not JSON",
        )


if __name__ == "__main__":
    unittest.main()
