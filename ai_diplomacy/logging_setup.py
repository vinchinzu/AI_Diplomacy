import logging
import os
import sys # To get stdout for console handler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .game_config import GameConfig

class LLMVerboseFilter(logging.Filter): # Removed comment: # Define the custom filter
    def __init__(self, name="", verbose_llm_debug=False):
        super().__init__(name)
        self.verbose_llm_debug = verbose_llm_debug

    def filter(self, record):
        if not self.verbose_llm_debug and record.levelno == logging.INFO:
            # Check logger name or message content for typical LLM verbose logs
            msg_lower = record.getMessage().lower()
            is_llm_log = "llm_coordinator" in record.name or \
                         "prompt:" in msg_lower or \
                         "response:" in msg_lower or \
                         "raw_response" in msg_lower or \
                         "full_prompt" in msg_lower
            
            if is_llm_log:
                # Truncate the message
                original_msg = record.getMessage() # Get the fully formatted message
                record.msg = original_msg[:150] + "... (set verbose_llm_debug=True for full details)"
                record.args = () # Clear args as msg is now pre-formatted
        return True

def setup_logging(config: 'GameConfig') -> None: # verbose_llm_debug is part of config
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
        
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s') # Removed comment: # Basic formatter

    root_logger = logging.getLogger() # Removed comment: # Get the root logger
    root_logger.setLevel(numeric_log_level)
    
    # Remove any existing handlers to avoid duplicate logs if this is called multiple times
    # (though ideally it's called once)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()

    console_handler = logging.StreamHandler(sys.stdout) # Removed comment: # Console Handler
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    logging.info(f"Console logging configured at level {config.log_level}.")

    if config.log_to_file: # Removed comment: # File Handler (if enabled)
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

    # Apply the LLMVerboseFilter if verbose_llm_debug is False
    if not config.verbose_llm_debug:
        llm_filter = LLMVerboseFilter(verbose_llm_debug=False)
        
        # Apply to specific loggers known for verbosity or to root logger's handlers
        # Applying to handlers of the root logger ensures it affects all logs passing through them.
        # Alternatively, apply to specific loggers:
        # logging.getLogger("ai_diplomacy.llm_coordinator").addFilter(llm_filter)
        # logging.getLogger("ai_diplomacy.agent").addFilter(llm_filter) # If agent logs full prompts/responses at INFO
        
        # Add filter to console handler to affect what's printed on screen at INFO level
        # This is often the primary concern for reducing verbosity.
        # File logs might still retain full detail if desired, or filter can be added there too.
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout: # Target console handler
                logging.info(f"Applying LLMVerboseFilter to console handler as verbose_llm_debug is False.")
                handler.addFilter(llm_filter)

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
    
    # Simplified import for direct script execution, assuming GameConfig is in the same directory
    # or PYTHONPATH is set up. For actual use, the relative import `.game_config` is correct.
    # We need a definition of GameConfig that includes verbose_llm_debug for the test.
    # from .game_config import GameConfig # This is for package use

    # Minimal mock for GameConfig to test logging_setup.py directly
    class MinimalGameConfig:
        def __init__(self, log_level="DEBUG", game_id="test_log_game", log_to_file=True, log_dir=None, verbose_llm_debug=False):
            self.log_level = log_level
            self.game_id = game_id
            self.log_to_file = log_to_file
            self.general_log_path = os.path.join(log_dir if log_dir else ".", f"{game_id}_general.log")
            self.verbose_llm_debug = verbose_llm_debug # Add the new attribute

    print("--- Testing logging_setup.py ---")

    # Test 1: Logging to file and console, verbose_llm_debug = False
    print("\n--- Test 1: Logging (DEBUG level), verbose_llm_debug = False ---")
    config1 = MinimalGameConfig(log_level="DEBUG", game_id="log_test_verbose_false", verbose_llm_debug=False)
    setup_logging(config1)
    logging.getLogger("ai_diplomacy.llm_coordinator").info("LLM Coordinator Prompt: This is a very long prompt...")
    logging.getLogger("ai_diplomacy.other_module").info("Other Info: Regular message.")
    logging.getLogger("ai_diplomacy.llm_coordinator").debug("LLM Coordinator DEBUG: Full details here.")


    # Test 2: Logging to file and console, verbose_llm_debug = True
    print("\n--- Test 2: Logging (DEBUG level), verbose_llm_debug = True ---")
    config2 = MinimalGameConfig(log_level="DEBUG", game_id="log_test_verbose_true", verbose_llm_debug=True)
    setup_logging(config2)
    logging.getLogger("ai_diplomacy.llm_coordinator").info("LLM Coordinator Prompt: This is a very long prompt...")
    logging.getLogger("ai_diplomacy.other_module").info("Other Info: Regular message.")
    logging.getLogger("ai_diplomacy.llm_coordinator").debug("LLM Coordinator DEBUG: Full details here.")

    # Test 3: Logging at INFO level, verbose_llm_debug = False
    print("\n--- Test 3: Logging (INFO level), verbose_llm_debug = False ---")
    config3 = MinimalGameConfig(log_level="INFO", game_id="log_test_info_verbose_false", verbose_llm_debug=False)
    setup_logging(config3)
    logging.getLogger("ai_diplomacy.llm_coordinator").info("LLM Coordinator Prompt: This is a very long prompt...")
    logging.getLogger("ai_diplomacy.llm_coordinator").debug("LLM Coordinator DEBUG: This should not appear.")


    print("\n--- logging_setup.py test complete ---")
