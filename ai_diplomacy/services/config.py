"""
Configuration management using Pydantic for validation and type safety.
Supports both game-level and agent-level configuration.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, validator
import yaml
import logging

logger = logging.getLogger(__name__)


class GameConfig(BaseModel):
    """Game-level configuration."""
    random_seed: Optional[int] = None
    use_mcp: bool = False
    token_budget: int = 6500
    max_years: Optional[int] = None
    log_level: str = "INFO"
    
    class Config:
        extra = "allow"  # Allow additional fields for flexibility


class AgentConfig(BaseModel):
    """Configuration for a single agent."""
    country: str = Field(..., description="Country/power name (e.g., FRANCE)")
    type: str = Field(..., description="Agent type: 'llm', 'scripted', etc.")
    model_id: Optional[str] = Field(None, description="LLM model identifier")
    context_provider: str = Field("auto", description="Context provider: 'inline', 'mcp', 'auto'")
    personality_prompt: Optional[str] = Field(None, description="Path to personality prompt template")
    tool_whitelist: List[str] = Field(default_factory=list, description="Allowed MCP tools")
    
    @validator('country')
    def country_uppercase(cls, v):
        return v.upper()
    
    @validator('type')
    def validate_agent_type(cls, v):
        allowed_types = {'llm', 'scripted', 'human'}
        if v not in allowed_types:
            raise ValueError(f"Agent type must be one of {allowed_types}")
        return v
    
    @validator('context_provider')
    def validate_context_provider(cls, v):
        allowed_providers = {'inline', 'mcp', 'auto'}
        if v not in allowed_providers:
            raise ValueError(f"Context provider must be one of {allowed_providers}")
        return v
    
    class Config:
        extra = "allow"


class DiplomacyConfig(BaseModel):
    """Main configuration container."""
    game: GameConfig = Field(default_factory=GameConfig)
    agents: List[AgentConfig] = Field(default_factory=list)
    
    @validator('agents')
    def validate_unique_countries(cls, v):
        countries = [agent.country for agent in v]
        if len(countries) != len(set(countries)):
            raise ValueError("Each country can only be assigned to one agent")
        return v
    
    @classmethod
    def from_yaml(cls, path: str) -> "DiplomacyConfig":
        """Load configuration from YAML file."""
        try:
            with open(path, 'r') as f:
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
            random_seed=getattr(args, 'random_seed', None),
            use_mcp=getattr(args, 'use_mcp', False),
            token_budget=getattr(args, 'max_diary_tokens', 6500),
            max_years=getattr(args, 'max_years', None),
            log_level=getattr(args, 'log_level', 'INFO')
        )
        
        agents = []
        
        # Handle single power mode
        if hasattr(args, 'power_name') and args.power_name:
            agents.append(AgentConfig(
                country=args.power_name,
                type='llm',
                model_id=getattr(args, 'model_id', None),
                context_provider='auto'
            ))
        else:
            # Handle multi-agent configuration from fixed_models
            if hasattr(args, 'fixed_models') and args.fixed_models:
                countries = ['FRANCE', 'GERMANY', 'RUSSIA', 'ENGLAND', 'ITALY', 'AUSTRIA', 'TURKEY']
                for i, model_id in enumerate(args.fixed_models):
                    if i < len(countries):
                        agents.append(AgentConfig(
                            country=countries[i],
                            type='llm',
                            model_id=model_id,
                            context_provider='auto'
                        ))
        
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
        return [agent for agent in self.agents if agent.type == 'llm']
    
    def to_yaml(self, path: str) -> None:
        """Save configuration to YAML file."""
        with open(path, 'w') as f:
            yaml.dump(self.dict(), f, default_flow_style=False)


# Model capability registry for context provider selection
MODEL_CAPABILITIES = {
    'supports_tools': {
        'gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo',
        'claude-3-5-sonnet', 'claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku'
    }
}


def supports_tools(model_id: str) -> bool:
    """Check if a model supports tool calling."""
    return model_id in MODEL_CAPABILITIES['supports_tools']


def resolve_context_provider(agent_config: AgentConfig) -> str:
    """Resolve 'auto' context provider to concrete implementation."""
    if agent_config.context_provider != 'auto':
        return agent_config.context_provider
    
    if agent_config.model_id and supports_tools(agent_config.model_id):
        return 'mcp'
    else:
        return 'inline'


# Removed SettingsConfigDict usage for compatibility 