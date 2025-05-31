"""
Configuration management using Pydantic for validation and type safety.
Supports both game-level and agent-level configuration.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
import yaml
import logging
from .. import constants # Import constants

logger = logging.getLogger(__name__)

__all__ = [
    "GameConfig",
    "AgentConfig",
    "DiplomacyConfig",
    "supports_tools",
    "resolve_context_provider",
]

class GameConfig(BaseModel):
    """Game-level configuration."""

    random_seed: Optional[int] = None
    use_mcp: bool = False
    token_budget: int = constants.DEFAULT_TOKEN_BUDGET
    max_years: Optional[int] = None
    log_level: str = constants.DEFAULT_LOG_LEVEL

    model_config = {"extra": "allow"}  # Allow additional fields for flexibility


class AgentConfig(BaseModel):
    """Configuration for a single agent."""

    country: str = Field(..., description="Country/power name (e.g., FRANCE)")
    type: str = Field(..., description="Agent type: 'llm', 'scripted', etc.")
    model_id: Optional[str] = Field(None, description="LLM model identifier")
    context_provider: str = Field(
        constants.CONTEXT_PROVIDER_AUTO, description="Context provider: 'inline', 'mcp', 'auto'"
    )
    personality_prompt: Optional[str] = Field(
        None, description="Path to personality prompt template"
    )
    tool_whitelist: List[str] = Field(
        default_factory=list, description="Allowed MCP tools"
    )
    verbose_llm_debug: bool = Field(False, description="Enable verbose LLM request/response logging")

    @field_validator("country")
    @classmethod
    def country_uppercase(cls, v):
        return v.upper()

    @field_validator("type")
    @classmethod
    def validate_agent_type(cls, v):
        allowed_types = {"llm", "scripted", "human"}
        if v not in allowed_types:
            raise ValueError(f"Agent type must be one of {allowed_types}")
        return v

    @field_validator("context_provider")
    @classmethod
    def validate_context_provider(cls, v):
        allowed_providers = {constants.CONTEXT_PROVIDER_INLINE, constants.CONTEXT_PROVIDER_MCP, constants.CONTEXT_PROVIDER_AUTO}
        if v not in allowed_providers:
            raise ValueError(f"Context provider must be one of {allowed_providers}")
        return v

    model_config = {"extra": "allow"}


class DiplomacyConfig(BaseModel):
    """Main configuration container."""

    game: GameConfig = Field(default_factory=GameConfig)
    agents: List[AgentConfig] = Field(default_factory=list)

    @field_validator("agents")
    @classmethod
    def validate_unique_countries(cls, v):
        countries = [agent.country for agent in v]
        if len(countries) != len(set(countries)):
            raise ValueError("Each country can only be assigned to one agent")
        return v

    @classmethod
    def from_yaml(cls, path: str) -> "DiplomacyConfig":
        """Load configuration from YAML file."""
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)
            return cls(**data)
        except FileNotFoundError:
            logger.warning(f"Config file {path} not found, using defaults")
            return cls()
        except Exception as e:
            logger.error(f"Error loading config from {path}: {e}")
            raise

    @classmethod
    def from_legacy_args(cls, args) -> "DiplomacyConfig":
        """Create configuration from legacy argparse.Namespace object."""
        # Convert legacy arguments to new format
        game_config = GameConfig(
            random_seed=getattr(args, "random_seed", None),
            use_mcp=getattr(args, "use_mcp", False),
            token_budget=getattr(args, "max_diary_tokens", constants.DEFAULT_TOKEN_BUDGET),
            max_years=getattr(args, "max_years", None),
            log_level=getattr(args, "log_level", constants.DEFAULT_LOG_LEVEL),
        )

        agents = []

        # Handle single power mode
        if hasattr(args, "power_name") and args.power_name:
            agents.append(
                AgentConfig(
                    country=args.power_name,
                    type="llm",
                    model_id=getattr(args, "model_id", None),
                    context_provider=constants.CONTEXT_PROVIDER_AUTO,
                )
            )
        else:
            # Handle multi-agent configuration from fixed_models
            if hasattr(args, "fixed_models") and args.fixed_models:
                countries = [
                    "FRANCE",
                    "GERMANY",
                    "RUSSIA",
                    "ENGLAND",
                    "ITALY",
                    "AUSTRIA",
                    "TURKEY",
                ]
                for i, model_id in enumerate(args.fixed_models):
                    if i < len(countries):
                        agents.append(
                            AgentConfig(
                                country=countries[i],
                                type="llm",
                                model_id=model_id,
                                context_provider=constants.CONTEXT_PROVIDER_AUTO,
                            )
                        )

        return cls(game=game_config, agents=agents)

    def get_agent_config(self, country: str) -> Optional[AgentConfig]:
        """Get configuration for a specific country."""
        country_upper = country.upper()
        for agent in self.agents:
            if agent.country == country_upper:
                return agent
        return None

    def get_llm_agents(self) -> List[AgentConfig]:
        """Get all LLM-based agent configurations."""
        return [agent for agent in self.agents if agent.type == "llm"]

    def to_yaml(self, path: str) -> None:
        """Save configuration to YAML file."""
        with open(path, "w") as f:
            yaml.dump(self.dict(), f, default_flow_style=False)


# Model capability registry for context provider selection
MODEL_CAPABILITIES = {
    constants.MODEL_CAPABILITIES_KEY_SUPPORTS_TOOLS: {
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
        "claude-3-5-sonnet",
        "claude-3-opus",
        "claude-3-sonnet",
        "claude-3-haiku",
    }
}


def supports_tools(model_id: str) -> bool:
    """Check if a model supports tool calling."""
    return model_id in MODEL_CAPABILITIES[constants.MODEL_CAPABILITIES_KEY_SUPPORTS_TOOLS]


def resolve_context_provider(agent_config: AgentConfig) -> str:
    """Resolve 'auto' context provider to concrete implementation."""
    if agent_config.context_provider != constants.CONTEXT_PROVIDER_AUTO:
        return agent_config.context_provider

    # Check if model_id is not None before calling supports_tools
    if agent_config.model_id is not None and supports_tools(agent_config.model_id):
        return constants.CONTEXT_PROVIDER_MCP
    else:
        return constants.CONTEXT_PROVIDER_INLINE


# Removed SettingsConfigDict usage for compatibility
