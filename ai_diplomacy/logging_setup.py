"""
Configures logging for the AI Diplomacy application.

This module provides functionalities to:
- Set up root logger behavior, including log levels, formatting, console, and file handlers.
- Offer a custom filter (`LLMVerboseFilter`) to manage verbosity of LLM-related logs.
- Provide a helper function (`get_log_paths`) to construct standardized log paths.
- Support JSON-formatted logs via the `JsonFormatter` class, configurable through
  the `LOG_FORMAT=JSON` environment variable.
"""

import logging
import os
import sys  # To get stdout for console handler
import json  # Added for JsonFormatter
from datetime import datetime  # Added for JsonFormatter timestamp
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from .game_config import GameConfig

__all__ = ["LLMVerboseFilter", "JsonFormatter", "setup_logging", "get_log_paths"]


def get_log_paths(game_id: str, base_log_dir: str) -> Dict[str, str]:
    """
    Constructs standardized log and result paths for a given game.

    Args:
        game_id: The unique identifier for the game.
        base_log_dir: The base directory where game-specific logs should be stored.

    Returns:
        A dictionary containing the paths for game-specific logs, LLM interactions,
        general logs, results, and manifestos.
    """
    game_id_specific_log_dir = os.path.join(base_log_dir, game_id)
    llm_log_path = os.path.join(
        game_id_specific_log_dir, f"{game_id}_llm_interactions.csv"
    )
    general_log_path = os.path.join(game_id_specific_log_dir, f"{game_id}_general.log")
    results_dir = os.path.join(game_id_specific_log_dir, "results")
    manifestos_dir = os.path.join(results_dir, "manifestos")

    return {
        "game_id_specific_log_dir": game_id_specific_log_dir,
        "llm_log_path": llm_log_path,
        "general_log_path": general_log_path,
        "results_dir": results_dir,
        "manifestos_dir": manifestos_dir,
    }


class LLMVerboseFilter(logging.Filter):  # Removed comment: # Define the custom filter
    def __init__(self, name="", verbose_llm_debug=False):
        super().__init__(name)
        self.verbose_llm_debug = verbose_llm_debug

    def filter(self, record: logging.LogRecord) -> bool:  # Added type hints
        if not self.verbose_llm_debug and record.levelno == logging.INFO:
            # Check logger name or message content for typical LLM verbose logs
            msg_lower = (
                record.getMessage().lower()
            )  # getMessage ensures msg % args is done
            is_llm_log = (
                "llm_coordinator" in record.name
                or "prompt:" in msg_lower
                or "response:" in msg_lower
                or "raw_response" in msg_lower
                or "full_prompt" in msg_lower
            )

            if is_llm_log:
                # Truncate the message
                original_msg = record.getMessage()  # Get the fully formatted message
                record.msg = (
                    original_msg[:150]
                    + "... (set verbose_llm_debug=True for full details)"
                )
                record.args = ()  # Clear args as msg is now pre-formatted
        return True


class JsonFormatter(logging.Formatter):
    """
    Formats log records as JSON strings.

    This formatter converts a LogRecord into a JSON string, including standard
    logging fields like timestamp, level, logger name, and message, as well
    as file/line information. It also includes exception information if present.
    Extra fields passed to the logger can also be included if they are JSON serializable.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Can set default_time_format and default_msec_format here if desired
        # For example, to always use ISO format with UTC:
        # self.default_time_format = '%Y-%m-%dT%H:%M:%S'
        # self.default_msec_format = '%s.%03dZ' # Note: %s is for seconds, not milliseconds from record.created
        # To use datetime.fromtimestamp(record.created).isoformat() for timestamp:
        # You would need to handle it directly in the format method instead of relying on record.asctime

    def format(self, record: logging.LogRecord) -> str:
        # Ensure standard Formatter attributes are available, especially record.message and record.asctime
        # record.message is created from record.msg % record.args
        # record.asctime is created based on default_time_format
        super().format(record)  # This populates record.asctime and record.message

        log_entry = {
            "timestamp": getattr(
                record, "asctime", datetime.fromtimestamp(record.created).isoformat()
            ),
            "level": record.levelname,
            "name": record.name,
            "message": record.message,  # Contains the fully formatted message string
            "source": {  # Grouping source information
                "pathname": record.pathname,
                "lineno": record.lineno,
                "function": record.funcName,
            },
            # "module": record.module, # Often redundant with pathname
            # "process_id": record.process, # Optional: process ID
            # "thread_name": record.threadName, # Optional: thread name
        }

        # Add exception info if present and formatted
        if record.exc_info and record.exc_text:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__
                if record.exc_info[0]
                else "Exception",
                "message": str(record.exc_info[1]) if record.exc_info[1] else "",
                "stacktrace": record.exc_text,
            }
        elif (
            record.exc_info
        ):  # Fallback if exc_text is not pre-formatted (should be by super().format)
            log_entry["exception_info"] = self.formatException(record.exc_info)

        # Add any extra fields passed to the logger via logging.Logger.debug("...", extra=dict(...))
        # Standard LogRecord attributes that might be of interest are already handled or commented out.
        # User-defined extra fields:
        standard_record_keys = {
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "message",
            "module",
            "msecs",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
            "_log",
            "_name",
            "_exc_info_hidden",  # Internal/already processed
        }
        extra_fields = {}
        for key, value in record.__dict__.items():
            if (
                key not in standard_record_keys and key not in log_entry
            ):  # Avoid overwriting already set fields
                if isinstance(value, (str, bool, int, float, list, dict, type(None))):
                    extra_fields[key] = value
                # else: # Potentially skip or convert non-basic types to string
                #     extra_fields[key] = str(value)
        if extra_fields:
            log_entry["extra"] = extra_fields

        try:
            return json.dumps(log_entry, ensure_ascii=False)
        except TypeError as e:
            # Fallback for unserializable fields
            fallback_timestamp = (
                datetime.fromtimestamp(record.created).isoformat()
                if hasattr(record, "created")
                else datetime.utcnow().isoformat()
            )
            error_log_entry = {
                "timestamp": fallback_timestamp,
                "level": "ERROR",
                "name": "JsonFormatter.SerializationError",
                "message": f"Error serializing log record: {e}. See original_record field.",
                "original_record_name": getattr(record, "name", "Unknown"),
                "original_record_msg_preview": getattr(record, "msg", "N/A")[:100],
            }
            return json.dumps(error_log_entry, ensure_ascii=False)


def setup_logging(config: "GameConfig") -> None:  # verbose_llm_debug is part of config
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
            logging.warning(
                f"Invalid log level: {config.log_level}. Defaulting to INFO."
            )
            numeric_log_level = logging.INFO
    except AttributeError:
        logging.error(f"Log level {config.log_level} not found. Defaulting to INFO.")
        numeric_log_level = logging.INFO

    # Determine which formatter to use
    log_format_env = os.getenv("LOG_FORMAT", "").upper()
    if log_format_env == "JSON":
        formatter = JsonFormatter()
        # Standard date format for JsonFormatter's asctime (if not overridden in JsonFormatter itself)
        # formatter.default_time_format = '%Y-%m-%dT%H:%M:%S'
        # formatter.default_msec_format = '%s.%03dZ' # Example for UTC
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    root_logger = logging.getLogger()  # Removed comment: # Get the root logger
    root_logger.setLevel(numeric_log_level)

    # Remove any existing handlers to avoid duplicate logs if this is called multiple times
    # (though ideally it's called once)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()

    console_handler = logging.StreamHandler(
        sys.stdout
    )  # Removed comment: # Console Handler
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    logging.info(f"Console logging configured at level {config.log_level}.")

    if config.log_to_file:  # Removed comment: # File Handler (if enabled)
        try:
            # Ensure the directory for the log file exists
            log_dir = os.path.dirname(config.general_log_path)
            if log_dir and not os.path.exists(log_dir):  # Check if log_dir is not empty
                os.makedirs(log_dir, exist_ok=True)

            file_handler = logging.FileHandler(
                config.general_log_path, mode="a", encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            logging.info(
                f"File logging configured at level {config.log_level}, path: {config.general_log_path}"
            )
        except Exception as e:
            logging.error(
                f"Failed to configure file logging to {config.general_log_path}: {e}",
                exc_info=True,
            )
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
            if (
                isinstance(handler, logging.StreamHandler)
                and handler.stream == sys.stdout
            ):  # Target console handler
                logging.info(
                    "Applying LLMVerboseFilter to console handler as verbose_llm_debug is False."
                )
                handler.addFilter(llm_filter)
