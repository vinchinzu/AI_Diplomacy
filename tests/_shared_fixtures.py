import argparse
from typing import Any
from datetime import datetime
import os
import pytest
from pathlib import Path

# Assuming GameConfig is imported from the correct path
# Adjust the import path if GameConfig is located elsewhere.
from ai_diplomacy.game_config import (
    GameConfig,
    DEFAULT_LOG_LEVEL,
    DEFAULT_GAME_ID_PREFIX,
    DEFAULT_NUM_PLAYERS,
    DEFAULT_NUM_NEGOTIATION_ROUNDS,
    DEFAULT_NEGOTIATION_STYLE,
)

# Default values for args that GameConfig expects
DEFAULT_ARGS_VALUES = {
    "game_config_file": None,
    "power_name": None,
    "model_id": None,
    "num_players": DEFAULT_NUM_PLAYERS,
    "game_id_prefix": DEFAULT_GAME_ID_PREFIX,
    "log_level": DEFAULT_LOG_LEVEL,
    "perform_planning_phase": False,
    "num_negotiation_rounds": DEFAULT_NUM_NEGOTIATION_ROUNDS,
    "negotiation_style": DEFAULT_NEGOTIATION_STYLE,
    "fixed_models": None,
    "randomize_fixed_models": False,
    "exclude_powers": None,
    "max_years": None,
    "log_to_file": False,  # Changed to False for tests to avoid creating log files by default
    "dev_mode": False,
    "verbose_llm_debug": False,
    "max_diary_tokens": 6500,
    "models_config_file": "models.toml",  # Default, can be overridden
    "game_id": None,  # Will be auto-generated if None
    "log_dir": None,  # GameConfig handles default log dir creation
    # The following are args used in some test setups, but not directly by GameConfig init
    # They are included here to allow tests to pass them through kwargs if needed elsewhere.
    "use_mocks": True,  # Common in tests
    "test_powers": "FRANCE",  # Example, specific tests might override
}


def create_game_config(**kwargs: Any) -> GameConfig:
    """
    Factory function to create a GameConfig instance with sensible defaults,
    allowing overrides via kwargs.
    """
    args_dict = DEFAULT_ARGS_VALUES.copy()
    args_dict.update(kwargs)

    # Ensure game_id is unique if not provided, to prevent clashes during parallel tests
    if args_dict.get("game_id") is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        prefix = args_dict.get("game_id_prefix", DEFAULT_GAME_ID_PREFIX)
        args_dict["game_id"] = f"{prefix}_test_{timestamp}"

    # For tests, if log_to_file is True but log_dir is not specified,
    # we should provide a default test log_dir to avoid cluttering the root directory.
    if args_dict.get("log_to_file") and args_dict.get("log_dir") is None:
        test_log_dir_base = os.path.join(os.getcwd(), "logs", "test_logs")
        # Further isolate by game_id to prevent concurrent write issues if tests run in parallel
        # GameConfig itself will append the game_id to base_log_dir, so we just provide the base.
        args_dict["log_dir"] = test_log_dir_base

    args = argparse.Namespace(**args_dict)

    # Before creating GameConfig, ensure the models.toml exists if GameConfig tries to load it,
    # or mock its loading path if it's not essential for the test.
    # For simplicity, we'll assume tests can manage this (e.g., by providing a dummy file or overriding models_config_path to None).
    # If models_config_file is None, GameConfig should handle it gracefully.
    if (
        "models_config_file" in args_dict
        and args_dict["models_config_file"] is not None
    ):
        if (
            not os.path.exists(args.models_config_file)
            and args.models_config_file == "models.toml"
        ):
            # If the default "models.toml" is specified and doesn't exist, skip the test.
            # Tests requiring it should create a dummy file or ensure it exists.
            pytest.skip(
                f"Default models_config_file '{args.models_config_file}' not found."
            )

    return GameConfig(args)


@pytest.fixture(name="game_config")
def game_config_fixture(cfg_file: Path, **kwargs: Any) -> GameConfig:
    """
    Pytest fixture that provides a GameConfig instance with sensible defaults.
    Allows overrides via kwargs passed during fixture parametrization or direct use.
    Example: @pytest.mark.parametrize("game_config", [{"num_players": 2}], indirect=True)
    """
    # This internal function call allows monkeypatching create_game_config in tests if needed,
    # though typically, overriding kwargs or monkeypatching the GameConfig object itself is preferred.
    if "game_config_file" not in kwargs:
        kwargs["game_config_file"] = str(cfg_file)
    return create_game_config(**kwargs)
