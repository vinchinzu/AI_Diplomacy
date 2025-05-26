# AI Diplomacy Refactor Progress

## Stage 0: Stabilize current code‑base ✅ COMPLETED & CLEANED

### Goal
Single entry‑point for every LLM call; deterministic core engine; frozen PhaseState boundary.

### What we accomplished

#### 1. Directory Structure ✅
```
ai_diplomacy/
├─ core/                 ← NO LLM IMPORTS ✅
│   ├─ __init__.py       
│   └─ state.py          (PhaseState dataclass) ✅
│
├─ agents/               ← per‑country logic ✅
│   ├─ __init__.py       
│   ├─ base.py           (BaseAgent ABC) ✅
│   └─ scripted_agent.py (ScriptedAgent implementation) ✅
│
├─ services/             ← reusable infrastructure ✅
│   ├─ __init__.py       
│   ├─ llm_coordinator.py (centralized LLM calls) ✅
│   ├─ config.py         (Pydantic configuration) ✅
│   └─ usage_tracker.py  (Datasette analytics) ✅
```

#### 2. Key Components Implemented ✅

**PhaseState (core/state.py):**
- ✅ Immutable dataclass with frozen=True
- ✅ No external dependencies (especially no LLM imports)
- ✅ Clean API: get_power_units(), get_power_centers(), is_power_eliminated()
- ✅ from_game() class method to create from diplomacy.Game object

**BaseAgent (agents/base.py):**
- ✅ Abstract base class defining agent contract
- ✅ Core methods: decide_orders(), negotiate(), update_state()
- ✅ Clean boundary: agents receive PhaseState, return Orders/Messages
- ✅ No side effects allowed

**ScriptedAgent (agents/scripted_agent.py):**
- ✅ Concrete implementation using hand-written heuristics
- ✅ Useful for testing and as baseline for LLM agents
- ✅ Implements full BaseAgent interface

**LLMCoordinator (services/llm_coordinator.py):**
- ✅ Single entry point for all LLM calls
- ✅ Model pooling and caching
- ✅ Serial locking for local models (Ollama, etc.)
- ✅ Usage tracking to SQLite database
- ✅ Two main APIs: call_text() and call_json()
- ✅ Maintains legacy call_llm_with_json_parsing() for transition

**Configuration System (services/config.py):**
- ✅ Pydantic-based validation
- ✅ GameConfig and AgentConfig classes
- ✅ Support for legacy args conversion
- ✅ Model capability registry (MCP tool support detection)

**Usage Analytics (services/usage_tracker.py):**
- ✅ SQLite database analysis utilities
- ✅ Datasette integration helpers
- ✅ Cost estimation for common models
- ✅ Game summaries and phase breakdowns

#### 3. Testing ✅
- ✅ Created test_stage0.py to verify all components work
- ✅ All tests pass successfully
- ✅ Verified clean boundaries and no import cycles

#### 4. Code Quality ✅
- ✅ Ran `ruff check` and fixed major issues in Stage 0 code
- ✅ Ran `ty check` and resolved type safety issues
- ✅ Fixed unused imports and variables
- ✅ Stage 0 code now has only 9 minor linting issues (down from 125+ total)
- ✅ All tests still pass after cleanup

### Key Achievements
1. **Clean Boundaries:** Core engine isolated from LLM dependencies, agents isolated from game engine
2. **Single LLM Entry Point:** All LLM calls go through LLMCoordinator
3. **Immutable State:** PhaseState provides clean, frozen snapshots to agents
4. **Agent Abstraction:** BaseAgent defines stable contract, implemented by LLM and scripted agents
5. **Configuration Management:** Pydantic-based config with validation and agent factory
6. **Usage Tracking:** Built-in analytics and Datasette integration
7. **Code Quality:** Clean, well-tested code with minimal linting issues
8. **Live Integration:** Real LLM agents making API calls and playing Diplomacy

---

## Stage 1: Clean agent boundary ✅ COMPLETED

### Goal
Agents isolated from engine & infrastructure; stable BaseAgent API.

### What we accomplished

#### 1. New Agent Architecture ✅
- **LLMAgent (agents/llm_agent.py)** - Clean LLM-based agent implementing BaseAgent
- **AgentFactory (agents/factory.py)** - Configuration-driven agent creation
- **GameManager (core/manager.py)** - Bridge between agents and game engine
- **Clean boundaries** - Agents receive PhaseState, return Orders/Messages

#### 2. BaseAgent Interface Implementation ✅
- **LLMAgent** fully implements BaseAgent interface:
  - `decide_orders(phase: PhaseState) -> List[Order]` ✅
  - `negotiate(phase: PhaseState) -> List[Message]` ✅  
  - `update_state(phase: PhaseState, events: List[Dict]) -> None` ✅
- **ScriptedAgent** already implemented from Stage 0 ✅
- **Immutable PhaseState** ensures no side effects ✅

#### 3. Configuration-Driven Creation ✅
- **AgentFactory** creates agents based on AgentConfig ✅
- **Mixed agent types** - LLM and scripted agents in same game ✅
- **Validation** - Agent configs validated before creation ✅
- **Error handling** - Graceful fallbacks for agent creation failures ✅

#### 4. Live LLM Integration ✅
- **Real LLM calls** - Test showed actual OpenAI API calls working ✅
- **JSON parsing** - LLM responses properly parsed for orders/messages ✅
- **Error handling** - Graceful fallbacks when LLM calls fail ✅
- **Usage tracking** - All LLM calls logged to SQLite database ✅

### Success Criteria
- ✅ LLM agent logic extracted to agents/llm_agent.py
- ✅ All agents use BaseAgent interface
- ✅ No direct game object access from agents
- ✅ Agent creation driven by configuration
- ✅ LLM functionality working with real API calls

---

## Stage 2: Introduce pluggable "context provider" ✅ COMPLETED

### Goal
Make MCP an add‑on, not mandatory; support both inline and MCP context.

### What we accomplished

#### 1. ContextProvider Architecture ✅
- **ContextProvider abstract base class** - Clean interface for context provision
- **InlineContextProvider** - Traditional approach embedding all context in prompts  
- **MCPContextProvider** - MCP tools-based context (ready for Stage 3)
- **ContextProviderFactory** - Auto-selection and fallback logic

#### 2. Configuration-Driven Context ✅
- **AgentConfig.context_provider** - "inline", "mcp", or "auto" selection
- **resolve_context_provider()** - Smart auto-resolution based on model capabilities
- **Graceful fallbacks** - MCP requests fall back to inline when not available

#### 3. LLM Agent Integration ✅
- **Updated LLMAgent** to use context providers for all decisions
- **Backward compatibility** - Legacy prompt methods still available
- **Real LLM testing** - Agents successfully making API calls with new system

#### 4. Live Testing ✅
- **Mixed configurations** - Different agents using different context providers
- **Real API calls** - OpenAI GPT-4o-mini successfully generating orders
- **Proper fallbacks** - MCP configs correctly falling back to inline
- **Error handling** - Graceful handling of missing API keys

### Success Criteria
- ✅ ContextProvider abstraction implemented with clean interface
- ✅ Agents work seamlessly with both inline and MCP context approaches
- ✅ No code changes needed when switching providers (configuration-driven)
- ✅ Configuration controls context strategy with auto-selection
- ✅ Real LLM agents working with new context system

---

## Legacy Cleanup: Remove old modules ✅ COMPLETED

### Goal
Clean up legacy files and imports to fully commit to the new layered structure.

### What we accomplished

#### 1. Updated Import Dependencies ✅
- **agent_manager.py** - Updated to use new AgentFactory and BaseAgent
- **game_results.py** - Updated to work with BaseAgent interface
- **utils.py** - Updated to use new services.llm_coordinator
- **initialization.py** - Simplified to deprecated stubs, created constants.py
- **planning.py** - Deprecated and removed (planning now handled by agents)

#### 2. Created New Modules ✅
- **constants.py** - Centralized ALL_POWERS and ALLOWED_RELATIONSHIPS
- **Updated __init__.py** - Backward compatibility exports for DiplomacyAgent

#### 3. Removed Legacy Files ✅
- **agent.py** - Deleted legacy agent implementation
- **llm_coordinator.py** - Deleted legacy coordinator (kept services version)
- **planning.py** - Deleted deprecated planning module

#### 4. Updated Game Orchestrator ✅
- **Planning phase** - Updated to gracefully handle deprecated planning
- **Agent interface** - Compatible with new BaseAgent system

#### 5. Comprehensive Testing ✅
- **All stage tests pass** - Stages 0, 1, and 2 tests all passing
- **Import compatibility** - All major imports work correctly
- **Database functionality** - Usage tracking still functional
- **Backward compatibility** - DiplomacyAgent alias works

### Success Criteria
- ✅ Legacy files safely removed without breaking functionality
- ✅ All imports updated to use new services and agents
- ✅ Comprehensive test suite still passes
- ✅ Backward compatibility maintained through __init__.py exports
- ✅ Clean codebase ready for Stage 3 (MCP integration)

---

## Stage 3: Optional MCP integration (PLANNED)

### Goal
Allow tool‑capable models to call live tools; MCP remains optional.

### Planned Tasks
1. **MCP server setup**
   - FastAPI server exposing diplomacy.board_state tool
   - JSON snapshot endpoint

2. **MCP client integration**
   - Thin wrapper around Python MCP SDK
   - Tool discovery and execution
   - Integration with LLMCoordinator

3. **Model capability detection**
   - Expand model registry
   - Automatic provider selection
   - Graceful fallback for non-tool models

### Success Criteria
- [ ] MCP server exposes game state as tools
- [ ] Tool-capable models can call MCP tools
- [ ] Non-tool models use inline context seamlessly
- [ ] No breaking changes to existing functionality

---

## Implementation Guidelines

### Boundary Rules Enforced
1. **core/ ↔ agents/**: No LLM imports in core/ ✅
2. **Agent API**: Agents receive PhaseState, return data ✅
3. **services ↔ agents**: Services provide stable APIs ✅

### Testing Strategy
- Unit tests for each component
- Integration tests for full game flow
- Test both LLM and scripted agents
- Verify boundaries are maintained

### Migration Path
- Keep existing code working during transition
- Gradual migration of components
- Backwards compatibility where possible
- Clear deprecation warnings

---

## Next Actions
1. Start Stage 1: Extract LLMAgent from current DiplomacyAgent
2. Create agent factory for configuration-driven creation
3. Update game orchestrator to use new agent system
4. Run integration tests to ensure compatibility 