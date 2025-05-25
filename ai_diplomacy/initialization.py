# ai_diplomacy/initialization.py
import logging
import json
import os # Add os import
import asyncio
import llm

# Forward declaration for type hinting, actual imports in function if complex
from typing import TYPE_CHECKING, List, Dict, Any, Optional, Tuple, Coroutine
if TYPE_CHECKING:
    from diplomacy import Game
    from diplomacy.models.game import GameHistory
    from .agent import DiplomacyAgent

from .agent import ALL_POWERS, ALLOWED_RELATIONSHIPS
# run_llm_and_log is obsolete
from .utils import log_llm_response 
from .prompt_constructor import build_context_prompt
from .llm_coordinator import _local_llm_lock # Import the lock

logger = logging.getLogger(__name__)

# Placeholder for Power enum if you have one, otherwise use strings
ALL_POWERS = ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"]

async def initialize_agent_state_ext(
    agent: 'DiplomacyAgent', 
    game: 'Game', 
    game_history: 'GameHistory', 
    log_file_path: str
):
    """Uses the LLM to set initial goals and relationships for the agent."""
    power_name = agent.power_name
    logger.info(f"[{power_name}] Initializing agent state using LLM (external function)..." )
    current_phase = game.get_current_phase() if game else "UnknownPhase"

    full_prompt = ""  # Ensure full_prompt is defined in the outer scope for finally block
    response = ""     # Ensure response is defined for finally block
    success_status = "Failure: Initialized" # Default status

    try:
        # Use a simplified prompt for initial state generation
        allowed_labels_str = ", ".join(ALLOWED_RELATIONSHIPS)
        initial_prompt = f"You are the agent for {power_name} in a game of Diplomacy at the very start (Spring 1901). " \
                         f"Analyze the initial board position and suggest 2-3 strategic high-level goals for the early game. " \
                         f"Consider your power's strengths, weaknesses, and neighbors. " \
                         f"Also, provide an initial assessment of relationships with other powers. " \
                         f"IMPORTANT: For each relationship, you MUST use exactly one of the following labels: {allowed_labels_str}. " \
                         f"Format your response as a JSON object with two keys: 'initial_goals' (a list of strings) and 'initial_relationships' (a dictionary mapping power names to one of the allowed relationship strings)."

        board_state = game.get_state() if game else {}
        possible_orders = game.get_all_possible_orders() if game else {}

        logger.debug(f"[{power_name}] Preparing context for initial state. Board state type: {type(board_state)}, possible_orders type: {type(possible_orders)}, game_history type: {type(game_history)}")
        # Ensure agent.client and its methods can handle None for game/board_state/etc. if that's a possibility
        # For initialization, game should always be present.

        formatted_diary = agent.format_private_diary_for_prompt()

        context = build_context_prompt(
            game=game,
            board_state=board_state, 
            power_name=power_name,
            possible_orders=possible_orders, 
            game_history=game_history, 
            agent_goals=None, 
            agent_relationships=None, 
            agent_private_diary=formatted_diary, 
        )
        full_prompt = initial_prompt + "\n\n" + context
        
        raw_response_text = "" # Initialize for logging
        parsed_successfully = False
        update_data = {} # Initialize to ensure it exists

        try:
            # Validate model ID by attempting to get the model
            # Use get_async_model for async operations
            model = llm.get_async_model(agent.model_id, options={"host": os.environ.get("OLLAMA_HOST")}) 
            if not model: # Should not happen if get_async_model raises on error
                raise llm.UnknownModelError(f"Model {agent.model_id} could not be retrieved.")
            logger.info(f"Successfully validated model {agent.model_id} for {agent.power_name}.")

            # Assuming build_context_prompt does not include the system prompt, 
            # and agent.system_prompt is the one to use.
            # If full_prompt from build_context_prompt already includes system prompt,
            # then system=None or system=agent.system_prompt might need adjustment based on model behavior.
            logger.debug(f"Full prompt for {agent.power_name}: {full_prompt}")

            # model.prompt() is called synchronously for async models from llm-ollama,
            # it returns a response object whose methods (like .text()) are awaitable.
            prompt_response_obj = model.prompt(full_prompt, system=agent.system_prompt)
            response_text = await prompt_response_obj.text() # Await the .text() method
            logger.debug(f"[{power_name}] LLM response for initial state: {response_text[:300]}...")

            update_data = agent._extract_json_from_text(response_text)
            if not isinstance(update_data, dict): # Ensure it's a dict
                logger.error(f"[{power_name}] _extract_json_from_text returned non-dict: {type(update_data)}. Treating as parsing failure. Data: {str(update_data)[:300]}")
                update_data = {} # Reset to empty dict
                success_status = "Failure: NotADictAfterParse"
                parsed_successfully = False
            else:
                logger.debug(f"[{power_name}] Successfully parsed JSON for initial state: {update_data}")
                parsed_successfully = True # Parsed to a dict
                # Success status will be refined based on whether data is applied
        
        except llm.UnknownModelError as e:
            logger.error(f"Agent {agent.power_name} has unknown model_id: {agent.model_id}. Error: {e}")
            # Potentially skip this agent or raise an error to stop initialization
            # For now, we'll log and continue, but the agent might fail later.
            # Consider adding a 'failed_agents' list or similar handling.
            continue # Skip to the next agent if model validation fails
        except Exception as e:
            logger.error(f"Unexpected error validating model for agent {agent.power_name} ({agent.model_id}): {e}")
            continue # Skip to the next agent

        initial_goals_applied = False
        initial_relationships_applied = False

        if parsed_successfully:
            initial_goals = update_data.get('initial_goals') or update_data.get('goals')
            initial_relationships = update_data.get('initial_relationships') or update_data.get('relationships')

            if isinstance(initial_goals, list) and initial_goals:
                agent.goals = initial_goals
                agent.add_journal_entry(f"[{current_phase}] Initial Goals Set by LLM: {agent.goals}")
                logger.info(f"[{power_name}] Goals updated from LLM: {agent.goals}")
                initial_goals_applied = True
            else:
                logger.warning(f"[{power_name}] LLM did not provide valid 'initial_goals' list (got: {initial_goals}).")

            if isinstance(initial_relationships, dict) and initial_relationships:
                valid_relationships = {}
                # ... (rest of relationship validation logic from before) ...
                for p_key, r_val in initial_relationships.items():
                    p_upper = str(p_key).upper()
                    r_title = str(r_val).title() if isinstance(r_val, str) else str(r_val)
                    if p_upper in ALL_POWERS and p_upper != power_name:
                        if r_title in ALLOWED_RELATIONSHIPS:
                            valid_relationships[p_upper] = r_title
                        else:
                            valid_relationships[p_upper] = "Neutral"
                if valid_relationships:
                    agent.relationships = valid_relationships
                    agent.add_journal_entry(f"[{current_phase}] Initial Relationships Set by LLM: {agent.relationships}")
                    logger.info(f"[{power_name}] Relationships updated from LLM: {agent.relationships}")
                    initial_relationships_applied = True
                else:
                    logger.warning(f"[{power_name}] No valid relationships found in LLM response.")
            else:
                 logger.warning(f"[{power_name}] LLM did not provide valid 'initial_relationships' dict (got: {initial_relationships}).")
            
            if initial_goals_applied or initial_relationships_applied:
                success_status = "Success: Applied LLM data"
            elif parsed_successfully: # Parsed but nothing useful to apply
                success_status = "Success: Parsed but no data applied"
            # If not parsed_successfully, success_status is already "Failure: JSONDecodeError"

        # Fallback if LLM data was not applied or parsing failed
        if not initial_goals_applied:
            if not agent.goals: # Only set defaults if no goals were set during agent construction or by LLM
                agent.goals = ["Survive and expand", "Form beneficial alliances", "Secure key territories"]
                agent.add_journal_entry(f"[{current_phase}] Set default initial goals as LLM provided none or parse failed.")
                logger.info(f"[{power_name}] Default goals set.")
        
        if not initial_relationships_applied:
             # Check if relationships are still default-like before overriding
            is_default_relationships = True # Assume default unless proven otherwise
            if agent.relationships: 
                # Check if all existing relationships are "Neutral"
                if not all(r == "Neutral" for r in agent.relationships.values()):
                    is_default_relationships = False
            
            if is_default_relationships: # Only override if current state is effectively default
                agent.relationships = {p: "Neutral" for p in ALL_POWERS if p != power_name}
                agent.add_journal_entry(f"[{current_phase}] Set default neutral relationships as LLM provided none valid or parse failed.")
                logger.info(f"[{power_name}] Default neutral relationships set (or kept).")
            else:
                logger.info(f"[{power_name}] Agent relationships were not default, retaining existing ones after failed/empty LLM update for relationships: {agent.relationships}")


    except Exception as e: # Catch-all for unexpected errors in the main try block
        logger.error(f"[{power_name}] Critical error during external agent state initialization: {e}", exc_info=True)
        success_status = f"Failure: Exception ({type(e).__name__})"
        # Ensure fallback logic for goals/relationships if not already set
        if not agent.goals: # If goals are still empty
            agent.goals = ["Survive and expand", "Form beneficial alliances", "Secure key territories"]
            logger.info(f"[{power_name}] Set fallback goals after top-level error: {agent.goals}")
        
        # Check if relationships are empty or all Neutral
        is_relationships_effectively_empty_or_default = True
        if agent.relationships:
            if not all(r == "Neutral" for r in agent.relationships.values()):
                 is_relationships_effectively_empty_or_default = False
        
        if is_relationships_effectively_empty_or_default:
            agent.relationships = {p: "Neutral" for p in ALL_POWERS if p != power_name}
            logger.info(f"[{power_name}] Set/reset to fallback neutral relationships after top-level error: {agent.relationships}")
    finally:
        if log_file_path: 
            log_llm_response(
                log_file_path=log_file_path,
                model_name=agent.model_id, # Use agent's model_id
                power_name=power_name,
                phase=current_phase,
                response_type="initial_state_setup", 
                raw_input_prompt=full_prompt,
                raw_response=response_text, # Log the raw text from LLM
                success=success_status
            )

    # Final log of state after initialization attempt
    logger.info(f"[{power_name}] Post-initialization state: Goals={agent.goals}, Relationships={agent.relationships}")

async def initialize_agent_state_concurrently(
    agent: 'DiplomacyAgent',
    game: 'Game', # diplomacy.Game object
    game_history: 'GameHistory',
    power_name: str,
    initial_prompt_template: str
) -> Tuple[str, bool, str, Dict[str, Any]]:
    logger.info(f"[{power_name}] Initializing state with LLM...")
    full_prompt = "" # Initialize full_prompt
    update_data = {}
    success_status = "Unknown" # Default status
    response_text = "" # Initialize response_text

    try:
        # Ensure the prompt template is a string and not None
        if initial_prompt_template is None or not isinstance(initial_prompt_template, str):
            logger.error(f"[{power_name}] Initial prompt template is not a valid string or is None.")
            success_status = "Failure: InvalidPromptTemplate"
            return power_name, False, success_status, update_data

        full_prompt = initial_prompt_template.format(
            power_name=power_name,
            game_state=game.get_state(),
            all_powers=", ".join(ALL_POWERS),
            # Assuming game_history has a method to get a summary or relevant parts for the prompt
            negotiation_history_summary=game_history.get_negotiation_summary(power_name) if game_history else "No negotiation history available."
        )

        # Log the prompt being sent for initialization (optional, can be verbose)
        logger.debug(f"[{power_name}] Initialization prompt:\\n{full_prompt}")

        async with _local_llm_lock:
            if os.environ.get("OLLAMA_SERIAL_MODE", "false").lower() == "true":
                 logger.debug(f"[{power_name}] Ollama model call (initialize_agent_state_concurrently) acquired lock (serial mode enabled)...")

            model = llm.get_async_model(agent.model_id, options={"host": os.environ.get("OLLAMA_HOST")}) # Use get_async_model for async operations
            response_obj = model.prompt(full_prompt, system=agent.system_prompt)
            response_text = await response_obj.text() # Assign to response_text

        logger.info(f"[{power_name}] LLM response received for initialization.")
        logger.debug(f"[{power_name}] Raw LLM response for state initialization: {response_text}")

        # Attempt to parse the JSON response
        try:
            # First, try to find JSON within ```json ... ``` or ``` ... ```
            json_match = agent.extract_json_from_text(response_text)
            if json_match:
                parsed_data = json.loads(json_match)
                logger.info(f"[{power_name}] Successfully parsed JSON from LLM response for initialization.")
                update_data = parsed_data # Store parsed data
                success_status = "Success: Parsed"
            else:
                logger.warning(f"[{power_name}] No JSON block found in LLM response for initialization. Trying direct parse.")
                # Try parsing the whole response as JSON if no block is found
                try:
                    parsed_data = json.loads(response_text)
                    logger.info(f"[{power_name}] Successfully parsed entire LLM response as JSON for initialization.")
                    update_data = parsed_data
                    success_status = "Success: ParsedDirectly"
                except json.JSONDecodeError:
                    logger.error(f"[{power_name}] Failed to parse LLM response as JSON directly for initialization.")
                    success_status = "Failure: JSONDecode"
        except json.JSONDecodeError as e_json:
            logger.error(f"[{power_name}] JSON parsing failed for initialization: {e_json}", exc_info=True)
            success_status = "Failure: JSONDecode"
        except Exception as e_parse: # Catch any other parsing related errors
            logger.error(f"[{power_name}] An unexpected error occurred during LLM response parsing for initialization: {e_parse}", exc_info=True)
            success_status = "Failure: ParseError"

    except llm.UnknownModelError as e_model:
        logger.error(f"[{power_name}] Unknown model error during initialization: {e_model}", exc_info=True)
        success_status = f"Failure: UnknownModel ({agent.model_id})"
    except Exception as e_llm_call:
        logger.error(f"[{power_name}] LLM call or parsing failed during initialization: {e_llm_call}", exc_info=True)
        success_status = f"Failure: LLMErrorOrParse ({type(e_llm_call).__name__})"
        # response_text is already defined

    return power_name, True if "Success" in success_status else False, success_status, update_data


async def initialize_agents_concurrently(
    agents: Dict[str, 'DiplomacyAgent'],
    game: 'Game',
    game_history: 'GameHistory',
    initial_prompt_template_str: str # Assuming this is the correct signature
) -> None:
    """
    Initializes multiple agents concurrently by calling their LLMs for initial state.
    """
    tasks = []
    for power_name, agent_instance in agents.items():
        logger.info(f"Preparing initialization task for {power_name}...")
        try:
            # Validate model ID by attempting to get the model
            # This should be done before adding the task, so if it fails, the agent isn't added.
            # Note: llm.get_async_model might not raise an error immediately for all plugins
            # if the model doesn't exist; it might only raise when an operation is attempted.
            # A more robust check might involve a quick health check or info call if available.
            _ = llm.get_async_model(agent_instance.model_id, options={"host": os.environ.get("OLLAMA_HOST")})
            logger.info(f"Model {agent_instance.model_id} seems valid for {power_name} (get_async_model succeeded). Scheduling state initialization.")

            task = initialize_agent_state_ext( 
                agent_instance,
                game,
                game_history,
                # log_file_path parameter was removed from initialize_agent_state_ext, ensure it's not needed or re-add if required.
                # For now, assuming it uses agent_instance.config or similar if needed.
                power_name, # Pass power_name, it was missing in the call signature of initialize_agent_state_ext
                initial_prompt_template_str # Pass initial_prompt_template_str
            )
            tasks.append(task)
            logger.info(f"Task for {power_name} added to initialization queue.")
        except llm.UnknownModelError as e:
            logger.error(f"Skipping initialization for {power_name}: Unknown model_id '{agent_instance.model_id}'. Error: {e}")
            continue # Skip to the next agent if model validation fails during get_async_model
        except Exception as e:
            logger.error(f"Skipping initialization for {power_name} due to unexpected error validating model '{agent_instance.model_id}': {e}", exc_info=True)
            continue # Skip to the next agent

    if not tasks:
        logger.warning("No agent tasks were created for initialization. Check model configurations or errors during validation.")
        return

    logger.info(f"Starting concurrent initialization for {len(tasks)} agents...")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Concurrent initialization tasks completed.")

    for result in results:
        if isinstance(result, Exception):
            logger.error(f"An exception occurred during an agent's initialization task: {result}", exc_info=result)
            # Handle individual task exception (e.g., log, mark agent as failed)
            continue

        power_name, success, status_detail, update_data_from_llm = result
        agent_to_update = agents.get(power_name)

        if agent_to_update:
            if success and update_data_from_llm:
                logger.info(f"Applying initial state update for {power_name}. Status: {status_detail}")
                logger.debug(f"[{power_name}] Data for state update from LLM: {update_data_from_llm}")
                agent_to_update.update_state_from_llm(update_data_from_llm, game.current_phase)
                # Log confirmation of state update based on parsed data
                initial_goals_applied = 'goals' in update_data_from_llm or 'updated_goals' in update_data_from_llm
                initial_rels_applied = 'relationships' in update_data_from_llm or 'updated_relationships' in update_data_from_llm
                logger.info(f"[{power_name}] Initial goals applied: {initial_goals_applied}, Initial relationships applied: {initial_rels_applied}")

            else:
                logger.error(f"Initialization failed or no data returned for {power_name}. Status: {status_detail}. Raw response was: (Check prior logs for raw response if available)")
                # Agent state remains default. Consider fallback or error state.
        else:
            logger.error(f"Agent {power_name} not found in agents dictionary after initialization task. This should not happen.")
