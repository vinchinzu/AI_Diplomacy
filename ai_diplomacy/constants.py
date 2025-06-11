"""
Constants used throughout the AI Diplomacy system.
"""

__all__ = [
    # Game Structure & Diplomacy Specific
    "ALL_POWERS",
    "ALLOWED_RELATIONSHIPS",
    "STATUS_ELIMINATED_PLAYER",
    # Default Identifiers & Fallbacks
    "DEFAULT_GAME_ID",
    "DEFAULT_PHASE_NAME",
    "DEFAULT_AGENT_MANAGER_FALLBACK_MODEL",
    "DEFAULT_SYSTEM_PROMPT_FILENAME",
    # LLM Interaction Keys & Values
    "LLM_RESPONSE_KEY_ORDERS",
    "LLM_RESPONSE_KEY_MESSAGES",
    "LLM_RESPONSE_KEY_DIARY_ENTRY",
    "LLM_RESPONSE_KEY_UPDATED_GOALS",
    "LLM_RESPONSE_KEY_REASONING",
    "LLM_MESSAGE_KEY_RECIPIENT",
    "LLM_MESSAGE_KEY_CONTENT",
    "LLM_MESSAGE_KEY_TYPE",
    "MESSAGE_RECIPIENT_GLOBAL",
    "MESSAGE_TYPE_BROADCAST",
    "VALID_MESSAGE_TYPES",
    # Prompt Template Filenames
    "PROMPT_TEMPLATE_CONTEXT",
    "PROMPT_TEMPLATE_FEW_SHOT",
    "PROMPT_TEMPLATE_ORDER_INSTRUCTIONS",
    # Orchestrator Settings & Timeouts
    "NEGOTIATION_MESSAGE_TIMEOUT_SECONDS",
    "ORDER_DECISION_TIMEOUT_SECONDS",
    "GAME_STATUS_COMPLETED",
    "PHASE_TYPE_PROCESS_ONLY",
    "PHASE_STRING_WINTER",
    # Service Configurations & Defaults
    "DEFAULT_TOKEN_BUDGET",
    "DEFAULT_LOG_LEVEL",
    "CONTEXT_PROVIDER_AUTO",
    "CONTEXT_PROVIDER_MCP",
    "CONTEXT_PROVIDER_INLINE",
    "MODEL_CAPABILITIES_KEY_SUPPORTS_TOOLS",
    # Context Provider Specific
    "CONTEXT_SECTION_HEADER_GAME_STATE",
    "CONTEXT_SECTION_HEADER_POSSIBLE_ORDERS",
    "CONTEXT_SECTION_HEADER_STRATEGIC_ANALYSIS",
    "CONTEXT_SECTION_HEADER_RECENT_MESSAGES",
    "MCP_TOOL_BOARD_STATE",
    "MCP_TOOL_POSSIBLE_ORDERS",
    "MCP_TOOL_RECENT_MESSAGES",
    # LLM Coordinator & Usage Tracking
    "LLM_USAGE_DATABASE_PATH",
    "LOCAL_LLM_SERIAL_ACCESS_PREFIXES",
    "LLM_CALL_RESULT_ERROR_NOT_INITIALIZED",
    "LLM_CALL_REQUEST_ID_DEFAULT",
    "LLM_CALL_LOG_RESPONSE_TYPE_DEFAULT",
    "LLM_CALL_ERROR_EMPTY_RESPONSE",
    # Model pricing
    "MODEL_PRICING_ESTIMATES",
    "DEFAULT_MODEL_PRICE_ESTIMATE_PAIR",
]

# --- Game Structure & Diplomacy Specific ---
ALL_POWERS = frozenset(
    {"AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"}
)
ALLOWED_RELATIONSHIPS = [
    "Enemy",
    "Unfriendly",
    "Neutral",
    "Friendly",
    "Ally",
]  # Used by agent_state
STATUS_ELIMINATED_PLAYER = "[ELIMINATED]"  # Used in prompt_constructor

# --- Default Identifiers & Fallbacks ---
DEFAULT_GAME_ID = "unknown_game"  # Used in LLMAgent, LLMCoordinator uses "default"
DEFAULT_PHASE_NAME = "unknown_phase"  # LLMCoordinator uses "unknown"
DEFAULT_AGENT_MANAGER_FALLBACK_MODEL = (
    "gemma3:4b"  # Used in model_utils (moved from agent_manager)
)
DEFAULT_SYSTEM_PROMPT_FILENAME = "system_prompt.txt"  # Used in LLMAgent

# --- LLM Interaction Keys & Values ---
LLM_RESPONSE_KEY_ORDERS = "orders"  # Used in LLMAgent
LLM_RESPONSE_KEY_MESSAGES = "messages"  # Used in LLMAgent
LLM_RESPONSE_KEY_DIARY_ENTRY = "diary_entry"  # Used in LLMAgent
LLM_RESPONSE_KEY_UPDATED_GOALS = "updated_goals"  # Used in LLMAgent
LLM_RESPONSE_KEY_REASONING = "reasoning"  # Used in LLMAgent
LLM_MESSAGE_KEY_RECIPIENT = "recipient"  # Used in LLMAgent
LLM_MESSAGE_KEY_CONTENT = "content"  # Used in LLMAgent
LLM_MESSAGE_KEY_TYPE = "message_type"  # Used in LLMAgent
MESSAGE_RECIPIENT_GLOBAL = "GLOBAL"  # Used in LLMAgent, orchestrators.negotiation
MESSAGE_TYPE_BROADCAST = "BROADCAST"  # Added
VALID_MESSAGE_TYPES = frozenset(
    {"BROADCAST", "SECRET"}
)  # Added, assuming these are the valid types

# --- Prompt Template Filenames ---
PROMPT_TEMPLATE_CONTEXT = "context_prompt.txt"  # Used in prompt_constructor
PROMPT_TEMPLATE_FEW_SHOT = (
    "few_shot_example.txt"  # Used in prompt_constructor (though unused in logic)
)
PROMPT_TEMPLATE_ORDER_INSTRUCTIONS = (
    "order_instructions.txt"  # Used in prompt_constructor
)

# --- Orchestrator Settings & Timeouts ---
NEGOTIATION_MESSAGE_TIMEOUT_SECONDS = 120.0  # Used in orchestrators.negotiation
ORDER_DECISION_TIMEOUT_SECONDS = 180.0  # Used in orchestrators.phase_orchestrator
GAME_STATUS_COMPLETED = "COMPLETED"  # Used in orchestrators.phase_orchestrator
PHASE_TYPE_PROCESS_ONLY = "-"  # Used in orchestrators.phase_orchestrator (phase string to mean "just process")
PHASE_STRING_WINTER = (
    "WINTER"  # Used in orchestrators.phase_orchestrator (for max_years check)
)

# --- Service Configurations & Defaults ---
DEFAULT_TOKEN_BUDGET = 6500  # Used in services.config.GameConfig
DEFAULT_LOG_LEVEL = "INFO"  # Used in services.config.GameConfig
CONTEXT_PROVIDER_AUTO = (
    "auto"  # Used in services.config.AgentConfig, services.context_provider
)
CONTEXT_PROVIDER_MCP = (
    "mcp"  # Used in services.config.AgentConfig, services.context_provider
)
CONTEXT_PROVIDER_INLINE = (
    "inline"  # Used in services.config.AgentConfig, services.context_provider
)
MODEL_CAPABILITIES_KEY_SUPPORTS_TOOLS = "supports_tools"  # Used in services.config

# --- Context Provider Specific ---
CONTEXT_SECTION_HEADER_GAME_STATE = (
    "=== GAME STATE ==="  # Used in services.context_provider
)
CONTEXT_SECTION_HEADER_POSSIBLE_ORDERS = (
    "=== YOUR POSSIBLE ORDERS ==="  # Used in services.context_provider
)
CONTEXT_SECTION_HEADER_STRATEGIC_ANALYSIS = (
    "=== STRATEGIC ANALYSIS ==="  # Used in services.context_provider
)
CONTEXT_SECTION_HEADER_RECENT_MESSAGES = (
    "=== RECENT MESSAGES ==="  # Used in services.context_provider
)
MCP_TOOL_BOARD_STATE = "diplomacy.board_state"  # Used in services.context_provider
MCP_TOOL_POSSIBLE_ORDERS = (
    "diplomacy.possible_orders"  # Used in services.context_provider
)
MCP_TOOL_RECENT_MESSAGES = (
    "diplomacy.recent_messages"  # Used in services.context_provider
)

# --- LLM Coordinator & Usage Tracking ---
LLM_USAGE_DATABASE_PATH = (
    "ai_diplomacy_usage.db"  # Used in services.llm_coordinator, services.usage_tracker
)
LOCAL_LLM_SERIAL_ACCESS_PREFIXES = ["ollama/", "llamacpp/", "gemma"]  # Added "gemma"
LLM_CALL_RESULT_ERROR_NOT_INITIALIZED = (
    "Not initialized"  # Used in services.llm_coordinator
)
LLM_CALL_REQUEST_ID_DEFAULT = "request"  # Used in services.llm_coordinator
LLM_CALL_LOG_RESPONSE_TYPE_DEFAULT = "llm_call"  # Used in services.llm_coordinator
LLM_CALL_ERROR_EMPTY_RESPONSE = (
    "Empty or no response from LLM"  # Used in services.llm_coordinator
)

# Model pricing for cost estimation (input_price_per_1k, output_price_per_1k)
MODEL_PRICING_ESTIMATES = {
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4-turbo": (0.01, 0.03),
    "gpt-3.5-turbo": (0.001, 0.002),
    "claude-3-5-sonnet": (0.003, 0.015),
    "claude-3-opus": (0.015, 0.075),
    "claude-3-sonnet": (0.003, 0.015),
    "claude-3-haiku": (0.00025, 0.00125),
}
DEFAULT_MODEL_PRICE_ESTIMATE_PAIR = (
    0.00015,
    0.0006,
)  # Fallback for services.usage_tracker
