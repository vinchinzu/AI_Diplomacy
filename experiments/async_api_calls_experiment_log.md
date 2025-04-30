# Experiment Log: Asynchronous API Calls for Performance Enhancement

**Date Started:** 2025-04-29

**Owner:** Cascade

**Goal:**
Improve the runtime performance of the Diplomacy game simulation (`lm_game.py`) by converting blocking LLM API calls to non-blocking asynchronous operations using `asyncio` and asynchronous client libraries. This aims to reduce the wall-clock time spent waiting for network I/O during phases involving multiple LLM interactions (initialization, planning, negotiation, order generation, state updates).

**Hypothesis:**
Replacing synchronous API calls managed by `ThreadPoolExecutor` with native `asyncio` operations will lead to significantly faster phase completion times, especially for negotiation and order generation where multiple calls happen concurrently.

**Key Implementation Details:**

*   Use `asyncio` library for managing asynchronous tasks.
*   Replace synchronous LLM client libraries (e.g., `openai`, `anthropic`) with their asynchronous counterparts (e.g., `openai.AsyncOpenAI`, `anthropic.AsyncAnthropic`).
*   Refactor client methods (`generate_response`, `get_orders`, `get_conversation_reply`, etc.) to be `async def` and use `await`.
*   Refactor calling functions in `agent.py`, `negotiations.py`, `planning.py`, and `lm_game.py` to use `async def` and `await`.
*   Replace `concurrent.futures.ThreadPoolExecutor` with `asyncio.gather` for managing concurrent async tasks.
*   Run the main simulation loop within `asyncio.run()`.
*   Maintain existing logging and error handling.

**Phased Implementation Plan:**

1.  **Agent Initialization:** Convert `agent.initialize_agent_state` and related client calls to async. Update `lm_game.py` to run initializations concurrently with `asyncio.gather`.
2.  **Negotiation:** Convert `negotiations.conduct_negotiations` and `client.get_conversation_reply` to async.
3.  **Order Generation:** Convert `client.get_orders` call chain to async.
4.  **Planning:** Convert `planning.planning_phase` call chain to async.
5.  **State Update:** Convert `agent.analyze_phase_and_update_state` call chain to async.

**Success Metric:**
Significant reduction (e.g., >30%) in total simulation runtime (`total_time` logged at the end of `lm_game.py`) for a standard game configuration (e.g., `--max_year 1902 --num_negotiation_rounds 2`). Compare before/after timings.

**Rollback Plan:**
Revert changes using Git version control if significant issues arise or performance does not improve as expected.

---

## Debugging & Results Table

| Phase Implemented      | Status     | Notes                                                                 | Wager Outcome |
| ---------------------- | ---------- | --------------------------------------------------------------------- | ------------- |
| 1. Agent Initialization | In Progress | Starting refactor of clients, agent init, and main loop concurrency. | -$100         |
| 2. Negotiation         | Pending    |                                                                       |               |
| 3. Order Generation    | Pending    |                                                                       |               |
| 4. Planning            | Pending    |                                                                       |               |
| 5. State Update        | Pending    |                                                                       |               |
| **Overall Result**     | **TBD**    | **Did total runtime decrease significantly?**                           | **+$500/-$100** |
