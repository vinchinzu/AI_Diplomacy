import logging
import os
import sys # To get stdout for console handler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .game_config import GameConfig

def setup_logging(config: 'GameConfig') -> None:
    """
    Sets up logging for the application.

    Configures a root logger with a console handler and optionally a file handler.
    Also sets the log level for noisy third-party libraries.

    Args:
        config: The GameConfig instance containing logging parameters like
                log_level, general_log_path, and log_to_file.
    """
    try:
        numeric_log_level = getattr(logging, config.log_level.upper(), None)
        if not isinstance(numeric_log_level, int):
            logging.warning(f"Invalid log level: {config.log_level}. Defaulting to INFO.")
            numeric_log_level = logging.INFO
    except AttributeError:
        logging.error(f"Log level {config.log_level} not found. Defaulting to INFO.")
        numeric_log_level = logging.INFO
        
    # Basic formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_log_level)
    
    # Remove any existing handlers to avoid duplicate logs if this is called multiple times
    # (though ideally it's called once)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    logging.info(f"Console logging configured at level {config.log_level}.")

    # File Handler (if enabled)
    if config.log_to_file:
        try:
            # Ensure the directory for the log file exists
            log_dir = os.path.dirname(config.general_log_path)
            if log_dir and not os.path.exists(log_dir): # Check if log_dir is not empty
                os.makedirs(log_dir, exist_ok=True)
            
            file_handler = logging.FileHandler(config.general_log_path, mode='a', encoding='utf-8')
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            logging.info(f"File logging configured at level {config.log_level}, path: {config.general_log_path}")
        except Exception as e:
            logging.error(f"Failed to configure file logging to {config.general_log_path}: {e}", exc_info=True)
            # Continue with console logging
    else:
        logging.info("File logging is disabled by configuration.")

    # Reduce verbosity of noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    # Add any other libraries that are too verbose
    # logging.getLogger("another_library").setLevel(logging.WARNING)

    logging.info(f"Root logger level set to {logging.getLevelName(root_logger.level)}")
    # Test message
    # logging.debug("Debug logging test - should only appear if level is DEBUG")
    # logging.info("Info logging test - should appear if level is INFO or DEBUG")

if __name__ == '__main__':
    # Example Usage for testing logging_setup.py directly
    
    # Mock GameConfig for testing
    class MockArgs:
        def __init__(self, log_level="DEBUG", game_id="test_log_game", log_to_file=True, log_dir=None):
            self.log_level = log_level
            self.game_id_prefix = "test_log"
            self.game_id = game_id # if None, GameConfig will generate one
            self.current_datetime_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_to_file = log_to_file
            # Allow log_dir to be None to test default path generation in GameConfig
            self.log_dir = log_dir
            # Add other attributes GameConfig expects from args, with defaults
            self.power_name = None
            self.model_id = None
            self.num_players = 7
            self.perform_planning_phase = False
            self.num_negotiation_rounds = 3
            self.negotiation_style = "simultaneous"
            self.fixed_models = None
            self.randomize_fixed_models = False
            self.exclude_powers = None
            self.max_years = None


    # Need to import GameConfig for the test, ensure path is correct for direct run
    # This might require adjusting PYTHONPATH if run directly from ai_diplomacy folder
    try:
        from game_config import GameConfig # If run from parent of ai_diplomacy
    except ImportError:
        from .game_config import GameConfig # If run as part of a package

    print("--- Testing logging_setup.py ---")

    # Test 1: Logging to file and console
    print("\n--- Test 1: Logging to file and console (DEBUG level) ---")
    mock_args_file = MockArgs(log_level="DEBUG", game_id="log_test_file_console")
    config_file = GameConfig(mock_args_file)
    setup_logging(config_file)
    logging.debug("This is a DEBUG message (Test 1).")
    logging.info("This is an INFO message (Test 1).")
    logging.warning("This is a WARNING message (Test 1).")
    print(f"General log for Test 1 should be at: {config_file.general_log_path}")

    # Test 2: Logging to console only
    print("\n--- Test 2: Logging to console only (INFO level) ---")
    mock_args_console = MockArgs(log_level="INFO", log_to_file=False, game_id="log_test_console_only")
    # To avoid GameConfig trying to create dirs for a file that won't be used:
    # We can either ensure GameConfig handles log_to_file=False correctly for path creation,
    # or pass a dummy log_dir that it won't use.
    # GameConfig's path creation is conditional on self.log_to_file, so it should be fine.
    config_console = GameConfig(mock_args_console)
    setup_logging(config_console)
    logging.debug("This is a DEBUG message (Test 2) - SHOULD NOT APPEAR.")
    logging.info("This is an INFO message (Test 2).")
    logging.warning("This is a WARNING message (Test 2).")

    # Test 3: Invalid log level
    print("\n--- Test 3: Invalid log level ---")
    mock_args_invalid = MockArgs(log_level="SUPERDEBUG", game_id="log_test_invalid_level")
    config_invalid = GameConfig(mock_args_invalid)
    setup_logging(config_invalid) # Should default to INFO and log a warning
    logging.debug("This is a DEBUG message (Test 3) - SHOULD NOT APPEAR.")
    logging.info("This is an INFO message (Test 3).")

    # Test 4: Specific log_dir provided
    print("\n--- Test 4: Specific log_dir provided ---")
    specific_log_directory = os.path.join(os.getcwd(), "temp_custom_logs", "game_XYZ")
    mock_args_custom_dir = MockArgs(log_level="DEBUG", game_id="game_XYZ", log_dir=specific_log_directory)
    config_custom_dir = GameConfig(mock_args_custom_dir)
    setup_logging(config_custom_dir)
    logging.debug(f"This is a DEBUG message (Test 4) in custom dir: {specific_log_directory}")
    logging.info(f"General log for Test 4 should be at: {config_custom_dir.general_log_path}")
    # Basic cleanup for test
    # if os.path.exists(specific_log_directory):
    #     import shutil
    #     shutil.rmtree(os.path.dirname(specific_log_directory)) # remove temp_custom_logs

    print("\n--- logging_setup.py test complete ---")
