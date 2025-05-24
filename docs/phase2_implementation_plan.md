# Implementation Plan: Phase 2 Refactoring & Features

## Introduction
Briefly state the main goals for Phase 2:
- Further simplify the codebase for readability and maintainability.
- Implement the "Multiple LLMs per Country" feature.
- Opportunistically apply modern Python features.
This plan outlines the proposed approach for these efforts.

## 1. Simplify Classes and Functions
This part of the refactoring aims to improve the overall codebase quality by enhancing readability, maintainability, and reducing complexity. We will target several key areas:

### 1.1. `ai_diplomacy/agent.py` (`DiplomacyAgent` class)
    - **Re-attempt Core Refactoring (Blocked Earlier)**:
        - The previously attempted refactoring (extracting prompt construction and response parsing logic from main methods into dedicated private helpers) should be re-attempted. This is crucial for readability.
        - **Affected Methods**: `generate_negotiation_diary_entry`, `generate_order_diary_entry`, `generate_phase_result_diary_entry`, `analyze_phase_and_update_state`, `consolidate_year_diary_entries`.
        - **Example Helper Structure**:
            ```python
            # For generate_negotiation_diary_entry
            # async def _construct_negotiation_diary_prompt(self, game, game_history, current_phase) -> str: ...
            # def _parse_negotiation_diary_response(self, response_data: dict) -> Tuple[str, Optional[dict]]: ...
            ```
        - **Introduce `_call_llm_and_log` Helper**: Re-introduce a standardized private method within `DiplomacyAgent` to handle the `llm.get_model().async_prompt()` call and the subsequent logging via `log_llm_response`.
            ```python
            # async def _call_llm_and_log(self, prompt: Optional[str], log_file_path: str, 
            #                             response_type: str, current_phase: str, 
            #                             model_id_override: Optional[str] = None) -> str:
            #     raw_response_text = ""
            #     final_model_id = model_id_override or self.model_id
            #     success_status = "Failure: Initialized"
            #     if not prompt:
            #         success_status = "Failure: NoPromptConstructed"
            #         # ... logging ...
            #     else:
            #         try:
            #             model_to_use = llm.get_model(final_model_id)
            #             system_p = self.system_prompt 
            #             llm_api_response = await model_to_use.async_prompt(prompt, system=system_p)
            #             raw_response_text = llm_api_response.text() if llm_api_response else ""
            #             success_status = "Success: LLMCallCompleted" if raw_response_text.strip() else "Failure: EmptyLLMResponseText"
            #         except Exception as e:
            #             # ... logging ...
            #             success_status = f"Failure: LLMException ({type(e).__name__})"
            #     # ... log_llm_response call ...
            #     return raw_response_text
            ```
    - **Review `_extract_json_from_text`**: Assess for simplifications or more targeted parsing (e.g., using `json_repair` more directly if standard parsing fails often).
    - **State Management**: Clarify logic in `analyze_phase_and_update_state`, particularly how goals and relationships are updated based on LLM output, ensuring robust validation against allowed values.

### 1.2. `ai_diplomacy/game_history.py` (`GameHistory` class)
    - **Method Review**: Examine methods like `get_messages_this_round`, `get_ignored_messages_by_power`, `get_strategic_directives` for clarity, efficiency, and potential simplification.
    - **Readability**: Ensure clear naming for methods and internal variables. Add comments where logic is complex.
    - **Network Compatibility**: Verify that the class design and methods are suitable for use with `network_lm_agent.py`, especially regarding how messages and game events are added and retrieved in a networked environment.

### 1.3. `ai_diplomacy/prompt_constructor.py`
    - **Relevance**: Evaluate the role of `build_context_prompt` and `construct_order_generation_prompt` now that `agent.py` has its own prompt construction helpers and `llm` is integrated.
    - **Consolidation/Deprecation**:
        - `construct_order_generation_prompt`: Its logic is now largely within `utils.get_valid_orders`. This function in `prompt_constructor.py` might be redundant.
        - `build_context_prompt`: This is used by many agent methods to gather common contextual information. It could remain in `prompt_constructor.py` or be moved into `DiplomacyAgent` as a private helper if it's only used there. Given its utility, keeping it in `prompt_constructor.py` might be fine if it's well-defined.
    - **Goal**: Reduce indirection if possible, ensuring prompts are constructed close to where they are used or by the entity (Agent) that "owns" the context.

### 1.4. `ai_diplomacy/utils.py`
    - **`get_valid_orders`**: This function was significantly refactored. Re-assess its readability and the clarity of its internal helpers (`_extract_moves_from_llm_response`, `_validate_extracted_orders`, `_fallback_orders_utility`).
    - **Utility Function Cohesion**: Review if `utils.py` is becoming a "miscellaneous" module. Group related functions or consider splitting into more focused utility modules if needed (e.g., `order_utils.py`, `logging_utils.py`). For now, its size is likely manageable.
    - **Remove Redundancy**: Double-check for any functions that might have become redundant after `llm` integration or other refactorings.

### 1.5. Game Orchestration Scripts (`lm_game.py`, `network_lm_agent.py`)
    - **Main Loop Clarity**:
        - In `lm_game.py`, the main `while not game.is_game_done:` loop is quite long. Consider extracting logical blocks (e.g., negotiation handling, planning phase execution, order generation for all powers, post-phase processing) into separate async functions called from the main loop.
        - Similarly, for `network_lm_agent.py`, the main game loop could be broken down.
    - **Setup and Initialization**: Ensure the setup of agents and game objects is clear and easy to follow.
    - **Error Handling**: Verify that error handling around LLM calls and game processing is robust and provides informative logs.

## 2. Design and Implement "Multiple LLMs per Country"
This feature will allow a single country to be controlled by multiple LLM agents (or model instances), enabling more complex decision-making processes like internal debates or specialized roles.

### 2.1. Configuration
    - **Proposal**:
        - Extend `--models` syntax for `lm_game.py`:
            `POWER_NAME:model_id1[role1];model_id2[role2],OTHER_POWER:model_id3[role_default]`
            Example: `FRANCE:gpt-4o[primary];claude-3.5-sonnet[advisor_strategy],ITALY:ollama/llama3`
            If no role is specified, a default role (e.g., "primary") is assumed.
        - For `network_lm_agent.py`, the `--model_id` argument could be extended similarly if a single agent process is to manage multiple LLMs for its assigned power. Alternatively, multiple agent processes could connect for the same power, each with a different model and role (server would need to support this). Simpler initial approach: one agent process, multiple models.
            `--model_id "gpt-4o[primary];claude-3.5-sonnet[advisor_strategy]"`
    - Update parsing logic in `lm_game.py` (for `--models`) and `network_lm_agent.py` (for `--model_id`) to handle this new format. A simple utility function could parse these strings.

### 2.2. `DiplomacyAgent` Modifications
    - **Internal Model Storage**:
        - Change `self.model_id: str` to `self.model_configs: List[Dict[str, str]]`. Each dict could be `{'id': 'model_id_str', 'role': 'role_name_str'}`.
        - The `__init__` method will parse the input `model_id` string (which may contain multiple model definitions) into this list.
    - **System Prompts**:
        - `self.system_prompt` could become `self.system_prompts: Dict[str, Optional[str]]`, mapping a role (or model_id if roles are not distinct enough) to its system prompt string.
        - Agent loading logic would need to find role-specific system prompt files (e.g., `france_primary_system_prompt.txt`, `france_advisor_strategy_system_prompt.txt`) or use a default/power-specific prompt if a role-specific one isn't found.

### 2.3. Interaction Strategies (Initial Focus: Ensemble)
    - **A. Simple Ensemble/Parallel Execution**:
        - **Concept**: All assigned LLMs (or those with relevant roles for a given task) are prompted with the same input (or role-differentiated input if prompts are tailored). Responses are then synthesized.
        - **Implementation**:
            - The `DiplomacyAgent`'s methods (e.g., for planning, negotiation message generation, order rationale) would iterate through relevant `self.model_configs`.
            - For each, it would call `model = llm.get_model(config['id'])` and then `await model.async_prompt(...)`, possibly using role-specific system prompts.
            - `asyncio.gather` or `asyncio.TaskGroup` (see 3.2) would be used for parallel execution.
        - **Response Synthesis**:
            - **Orders**: This is the most complex. The `get_valid_orders` function (in `utils.py`) would need to be called by the agent *after* it has determined the final orders. The agent itself would synthesize order proposals from its multiple LLMs.
                - *Initial Idea*: Primary LLM proposes orders. Advisors critique or suggest alternatives. A final decision mechanism (e.g., primary decides after advice, or a simple voting/ranking if multiple LLMs propose full order sets) would be needed. For simplicity, perhaps only the 'primary' role LLM generates the actual order JSON, while others provide text advice that the 'primary' LLM considers in a second step or as part of its initial prompt.
            - **Messages**: Send all unique, coherent messages generated by LLMs with a "diplomat" or "communications" role. Or, have a "primary" LLM draft messages based on advice from others.
            - **Plans/Diary Entries**: Could be generated by a "primary" LLM, potentially incorporating textual advice from "advisor" LLMs.
    - **B. Primary + Advisors (Future Option)**: One LLM is designated as the primary decision-maker. Other LLMs act as advisors, providing critiques, alternative suggestions, or specialized analysis (e.g., one for military strategy, one for diplomatic readings). The primary LLM considers this advice before making a final decision.
    - **C. Multi-Turn Internal Debate (Advanced - Future Option)**: LLMs engage in a structured internal "debate" over several turns or steps to refine strategies or messages before an external action is taken. This is significantly more complex.
    - **Recommendation**: Start with Simple Ensemble for tasks like advice generation for planning or negotiation strategy. For order generation, a "primary LLM decides, others advise" model might be more practical initially than complex voting on full order sets.

### 2.4. Adaptation of Agent Methods
    - **`generate_plan`**: Each relevant LLM could generate a plan segment or advice. The agent then synthesizes these into a single plan, or the "primary" LLM does.
    - **Negotiation Message Generation (within `conduct_negotiations` in `negotiations.py` which calls agent methods)**:
        - The agent's internal method (e.g., `_generate_message_for_power`) could be adapted. If multiple LLMs have a "diplomacy" role, they could all draft messages. The agent could then select the "best" one, or send all non-contradictory ones.
    - **Order Generation (within `get_valid_orders` in `utils.py`, called by game loops)**:
        - This is the most critical. The `DiplomacyAgent` would first use its ensemble to *decide on a strategy or intent*. Then, one designated "order executioner" LLM (or the primary) would generate the actual JSON orders based on this internal consensus. `get_valid_orders` would then be called with these agent-decided orders.
        - Alternatively, if multiple LLMs generate full order sets, a voting/merging mechanism would be needed within the agent before calling `get_valid_orders` for validation.
    - **Diary/State Updates**:
        - A "primary" LLM could be responsible for generating diary entries and proposing state updates, possibly after being prompted with summaries of advice from other LLMs in its ensemble.

### 2.5. Logging for Multi-LLM Interactions
    - `log_llm_response` should be called for each individual LLM interaction.
    - Consider adding a 'role' field to the `log_llm_response` parameters and CSV output to distinguish which LLM (e.g., "primary", "advisor_strategy") produced a given response.
    - The agent's internal decision-making log (journal/diary) should record how different LLM outputs were synthesized into a final decision.

### 2.6. Python 3.11+ `asyncio.TaskGroup`
    - Note its utility for managing parallel `async_prompt` calls in the ensemble strategy, providing better error handling than `asyncio.gather` alone.

## 3. Python 3.13+ Modernizations (Opportunistic)
Adopt modern Python features (3.10-3.13+) where they offer clear advantages in readability, performance, or conciseness.

### 3.1. Structural Pattern Matching (Python 3.10+)
    - **Use Cases**: Parsing complex, nested JSON responses from LLMs; handling different types of game events or messages.
    - **Example Opportunity**: In `DiplomacyAgent._extract_json_from_text` or specific response parsing helpers, after an initial `json.loads`, pattern matching could elegantly destructure the data:
      ```python
      # match parsed_data:
      #     case {"orders": list(orders), "reasoning": str(reason)}:
      #         # process orders and reasoning
      #     case {"error": str(err_msg)}:
      #         # handle error
      #     case _:
      #         # default case
      ```

### 3.2. `asyncio.TaskGroup` (Python 3.11+)
    - **Use Cases**: Managing concurrent asynchronous operations, especially for the multi-LLM ensemble strategy.
    - **Example Opportunity**: When an agent needs to get advice or responses from multiple LLMs in parallel:
      ```python
      # async with asyncio.TaskGroup() as tg:
      #     response1_task = tg.create_task(llm_call_to_model1(...))
      #     response2_task = tg.create_task(llm_call_to_model2(...))
      # results = [response1_task.result(), response2_task.result()]
      ```

### 3.3. Typing Improvements (Python 3.9+)
    - `typing.Self` (Python 3.11+): For methods that return an instance of the class.
    - `ParamSpec` and `Concatenate` (Python 3.10+): For decorators or higher-order functions if they become complex.
    - `TypeGuard` (Python 3.10+): For type narrowing in complex conditional logic.
    - Continued and more rigorous use of `dataclasses` and `TypedDict` for structured data.

### 3.4. `tomllib` (Python 3.11+)
    - **Use Cases**: If a more complex configuration file format than `.env` or simple JSON is needed (e.g., for detailed multi-LLM setups, per-power strategy templates), TOML is a good candidate, and `tomllib` provides built-in support.

### 3.5. Exception Groups and `except*` (Python 3.11+)
    - **Use Cases**: When using `asyncio.TaskGroup`, multiple tasks might raise exceptions. `except*` allows handling these grouped exceptions more gracefully.

### 3.6. General Pythonic Improvements
    - Consistent use of list comprehensions and generator expressions where appropriate.
    - Effective use of context managers (`with` statement).
    - Adherence to PEP 8 and code formatting (e.g., using Black or Ruff).

## Conclusion
This plan outlines the next major steps in refactoring and enhancing the AI Diplomacy project. It aims to improve code quality while introducing a significant new feature (multi-LLM agents). The plan is subject to refinement as implementation progresses and new insights are gained.
```
