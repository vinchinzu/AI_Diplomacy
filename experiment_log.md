# AI Diplomacy Enhancement - Experiment Log

**Goal:** Integrate improvements for game state tracking, order validation, strategic map analysis, agent state, planning, and negotiation into the AI Diplomacy codebase while maintaining high quality and avoiding downtime.

**Changes Summary (Tasks Completed):**
- Task 1: Enhanced Game History Tracking (Phase/Experience)
- Task 2: Improved Order Validation/Processing (Normalization)
- Task 3: Strategic Map Analysis (Graph/BFS)
- Task 4: Upgraded Agent Architecture (Stateful Agent Class)
- Task 5: Enhanced Negotiation Protocol (Agent State Integration)
- Task 7: Enhanced Prompt Structure (System Prompts)
- Task 9: Implemented Planning Module
- Task 10: Improved Phase Summaries and Display

**Key Implementation Details:**
- **Agent State:** `ai_diplomacy/agent.py` (DiplomacyAgent class stores personality, goals, relationships, journal). System prompts loaded from `ai_diplomacy/prompts/system_prompts/`.
- **Planning:** `ai_diplomacy/planning.py` (planning_phase uses Agent), `ai_diplomacy/agent.py` (generate_plan), `ai_diplomacy/clients.py` (get_plan), `ai_diplomacy/prompts/planning_instructions.txt`.
- **Negotiation:** `ai_diplomacy/negotiations.py` (conduct_negotiations uses Agent state), `ai_diplomacy/clients.py` (get_conversation_reply accepts Agent state), `ai_diplomacy/prompts/conversation_instructions.txt`, `ai_diplomacy/prompts/context_prompt.txt`.
- **Game History:** `ai_diplomacy/game_history.py` (stores plans, messages, etc.)
- **Utilities:** `ai_diplomacy/utils.py` (order normalization), `ai_diplomacy/map_utils.py` (graph analysis)
- **Phase Summaries:** `lm_game.py` (phase_summary_callback), modified Game class to properly record and export summaries.

---

## Experiment 4: Initial State & Update Loop Debug

**Date:** 2025-04-07
**Goal:** Fix initial goal generation failure and ensure state update loop runs.
**Changes:** 
- Added default neutral relationships in `Agent.__init__`.
- Added `Agent.initialize_agent_state` using LLM (called from `lm_game`).
- Added error handling/logging to `Agent.analyze_phase_and_update_state`.
**Observation:** Initial goals still `None specified` due to `TypeError` in `build_context_prompt` call within `initialize_agent_state`. Relationships defaulted correctly. State update loop (`analyze_phase_and_update_state`) was *not* being called in `lm_game.py`.
**Result:** Failure (-$0.00, minimal LLM calls due to error)
**Next Steps:** Add debug logs to `initialize_agent_state` call; Implement the state update loop call in `lm_game.py` after `game.process()`.

## Debugging Table, -$100 on failure, +$500 on success 

| # | Problem                                                                                                | Attempted Solution         | Outcome           | Balance ($) |
|---|--------------------------------------------------------------------------------------------------------|----------------------------|-------------------|-------------|
| 4 | Initial goals `TypeError` in `build_context_prompt`; State update loop not called.                      | Debug logs; Implement loop | Failure           | -$100       |
| 5 | `TypeError` in `add_journal_entry` (wrong args); `JSONDecodeError` (LLM added extra text/markdown fences) | Fix args; Robust JSON parse | Partial Success*  | -$100       |
| 6 | `TypeError: wrong number of args` for state update call.    | Helper fn; Sync loop; Fix | Failure        | -$100      |
| 7 | `AttributeError: 'Game' has no attribute 'get_board_state_str'/'current_year'` and JSON key mismatch | Create board_state_str from board_state; Extract year from phase name; Fix JSON key mismatches | Partial Success** | -$100 |

*Partial Success: Game ran 1 year, but failed during state update phase.
**Partial Success: Game runs without crashing, but LLM responses still don't match expected JSON format.

## Experiment 7: Game State Processing Fixes

**Date:** 2025-04-08
**Goal:** Fix the game state processing and JSON format issues.
**Changes:**
1. Fixed parameter mismatch in `analyze_phase_and_update_state`: Changed from (game, game_history) to (game, board_state, phase_summary, game_history)
2. Made JSON parsing more robust with a dedicated `_extract_json_from_text` helper method
3. Added fallback values in case of JSON parsing failures
4. Fixed missing game attributes: created board_state_str from board_state dict, extracted year from phase name
5. Identified JSON key mismatch between prompt ("relationships"/"goals") and code ("updated_relationships"/"updated_goals")

**Observation:** Game now runs without crashing through basic state updates, but LLM responses don't use the expected JSON keys (they use "relationships"/"goals" while code expects "updated_relationships"/"updated_goals").

**Next Steps:** Fix the JSON key mismatch by either:
1. Updating the state_update_prompt.txt to use "updated_goals" and "updated_relationships", or
2. Modifying the agent.py code to look for "goals" and "relationships" keys and map them to the expected variables.
 
