# Known Issues and Future Enhancements

This file tracks known issues, planned improvements, and ideas for future development of the AI Diplomacy project.

## Gameplay and Agent Behavior

### 1. Italy as a True Neutral Power (Non-LLM)

*   **Current State:** Italy is currently handled as an LLM-controlled power. A temporary hack was added to `MovementPhaseStrategy` to make it issue Hold orders if it's not an "active LLM power". This is not a robust solution.
*   **Desired State:**
    *   Italy should be configurable as a truly neutral, non-LLM power that defaults to specific behaviors (e.g., always holding units).
    *   This should not require an LLM model to be assigned to Italy.
*   **Proposed Solution Ideas:**
    *   Introduce a `NeutralAgent` or `ScriptedAgent` type (e.g., `HoldAgent(BaseAgent)`).
    *   In `run_wwi_test.py` (or a general game configuration), assign this agent type to Italy.
    *   `AgentManager` would create this simple agent, which would not make LLM calls.
    *   Phase strategies would naturally call this agent's `decide_orders` method, which would return Hold orders.
    *   This approach avoids special-casing "ITALY" within phase strategies and is more extensible to other neutral/scripted powers.
*   **Notes:**
    *   Consider how a neutral power handles dislodgements and mandatory disbands. A simple "HoldAgent" might not be sufficient if it needs to make choices for retreats or disbands. The game engine might auto-disband if no orders are given.
    *   The WWI scenario in `scenarios.py` might need adjustment to reflect Italy's controller if it's no longer an LLM bloc name.

### 2. Coordinated Bloc-Level Moves for LLM Agents

*   **Current State:** In scenarios like WWI two-player, even if multiple game powers (e.g., England, France, Russia for Entente) share the same LLM model configuration, they are treated as individual agents. Each agent receives a separate prompt and generates orders for its own units. Coordination is implicit, relying on the shared LLM potentially having a consistent strategy if prompted similarly.
*   **Desired State:** For bloc-based scenarios (e.g., two "players" controlling multiple game powers), the LLM agent representing a bloc should be able to generate a single, coordinated set of orders for all game powers within that bloc.
*   **Proposed Solution Ideas:**
    *   **Bloc-Agent Abstraction:** Introduce a new agent type, e.g., `BlocLLMAgent(BaseAgent)`, that is aware it controls multiple game powers.
    *   **Unified Prompting:** `BlocLLMAgent.decide_orders` would construct a single prompt for the LLM that includes the state and units of all its constituent game powers (e.g., England, France, Russia). The prompt would ask for a coordinated set of orders for all these units.
    *   **Complex Order Parsing:** The LLM response would need to be parsed to extract orders for each individual game power within the bloc. The JSON structure for orders would need to accommodate this (e.g., a top-level key for each power, or orders tagged by power).
    *   **AgentManager & Orchestrator Updates:**
        *   `AgentManager` would need to be able to create and manage `BlocLLMAgent` instances, mapping a single bloc agent to multiple game powers. (Implemented)
        *   `PhaseOrchestrator` and phase strategies would need to interact with these bloc agents, potentially by still iterating through game powers but knowing that the "agent" for several of them is the same instance. The `_get_orders_for_power` might need to be adapted or a new `_get_orders_for_bloc` introduced. (Implemented - see Progress below)
*   **Progress & Resolution:**
    *   The `BlocLLMAgent` class has been implemented, capable of generating coordinated orders for multiple game powers it controls.
    *   The `PhaseOrchestrator`'s phase strategies (`MovementPhaseStrategy`, `RetreatPhaseStrategy`, `BuildPhaseStrategy`) have been updated to correctly handle `BlocLLMAgent` instances.
    *   **Mechanism:**
        1.  Before iterating through powers that need orders, a `current_phase_state` is created from the game state.
        2.  When a power is encountered that is managed by a `BlocLLMAgent`, the system checks if this specific bloc agent instance has already been processed for the current phase.
        3.  If not processed, `await agent.decide_orders(current_phase_state)` is called *once* for the entire bloc. This triggers the LLM call and caches the orders for all members of the bloc within the `BlocLLMAgent` instance.
        4.  A `current_phase_key_for_bloc` (a tuple representing the unique phase state) is constructed.
        5.  `agent.get_all_bloc_orders_for_phase(current_phase_key_for_bloc)` is then called to retrieve the cached, coordinated orders for all powers controlled by this bloc agent.
        6.  These orders are then assigned to the respective `orders_by_power` dictionary and recorded in `GameHistory`.
        7.  The `BlocLLMAgent` instance is marked as processed for the current phase to prevent redundant calls.
    *   This approach ensures that a single, coordinated decision-making process occurs for the bloc, and the resulting orders are efficiently distributed to the relevant game powers.
*   **Status:** Resolved. The core requirements for coordinated bloc-level moves by LLM agents have been implemented.
*   **Challenges:**
    *   **Prompt Complexity:** Crafting a prompt that effectively allows an LLM to manage and coordinate 3-4 powers simultaneously is challenging. Token limits could be an issue. (This remains an ongoing challenge in prompt engineering but the mechanism to support it is in place).
    *   **LLM Capability:** Requires an LLM capable of high-level strategic coordination across multiple entities in a complex game. (This remains an ongoing challenge in LLM development but the mechanism to support it is in place).
    *   **Order Validation:** Validating orders for multiple powers from a single response. (Handled by the `BlocLLMAgent`'s parsing and the game engine's subsequent validation of individual power orders).
*   **Notes:** This was a significant architectural change and has improved the strategic coherence of AI players in bloc-based scenarios.

## Build Phase

### 3. Neutral Power Build/Disband Logic

*   **Current State:** The `BuildPhaseStrategy` has been updated to correctly identify powers needing builds/disbands using `game.get_state()['builds']`. If Italy is neutral and not an LLM agent, it won't have build/disband orders generated by an agent. The game engine will likely auto-disband if necessary.
*   **Desired State:** A neutral power (like a holding Italy) should have clear, predictable logic for builds and disbands if it somehow gains or loses centers.
*   **Proposed Solution:**
    *   If using a `NeutralAgent` or `HoldAgent`, its `decide_orders` method for a build phase could implement simple logic:
        *   **Builds:** If it has builds, try to build in empty home supply centers. If multiple options, pick based on a predefined preference or randomly.
        *   **Disbands:** If it needs to disband, pick units to disband based on a simple heuristic (e.g., farthest from home SCs, or random).
    *   Alternatively, rely on the game engine's default behavior for un-ordered disbands, which is usually sufficient for a passive neutral. For builds, if no build orders are submitted for a power that *can* build, it simply forgoes the builds.

## Other

*   **(Placeholder for other issues/ideas)** 