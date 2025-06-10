# Constants for the generic LLM framework

# --- Constants previously in ai_diplomacy.constants and used by LLMCoordinator ---

# Path to the SQLite database for LLM usage tracking
LLM_USAGE_DATABASE_PATH = "llm_usage.db" # Default, can be overridden

# Default identifiers for LLM calls when specific ones are not provided
DEFAULT_GAME_ID = "default_game"
DEFAULT_PHASE_NAME = "default_phase"
LLM_CALL_REQUEST_ID_DEFAULT = "default_request_id"

# Prefixes for LLM serial access (if applicable, e.g. for local models)
LOCAL_LLM_SERIAL_ACCESS_PREFIXES = ("local/", "ollama/") # Example prefixes

# Error messages or codes for LLM call results
LLM_CALL_RESULT_ERROR_NOT_INITIALIZED = "LLM_NOT_INITIALIZED"
LLM_CALL_ERROR_EMPTY_RESPONSE = "EMPTY_LLM_RESPONSE"

# Default response type for LLM call logging
LLM_CALL_LOG_RESPONSE_TYPE_DEFAULT = "llm_response"

# Add any other constants that were used by the original LLMCoordinator
# and are generic enough for this framework.

# --- Constants for log_llm_response (if any are specific) ---
# (To be populated after inspecting log_llm_response)

# Maximum length of content to log to prevent overly verbose logs.
MAX_CONTENT_LOG_LENGTH = 500 # Example value, adjust as needed

# Default value for turn number when not available
DEFAULT_TURN_NUMBER = -1

# Default value for player name when not available
DEFAULT_PLAYER_NAME = "N/A"
