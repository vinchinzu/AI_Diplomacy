# ai_diplomacy/initialization.py
import logging
import json

# Forward declaration for type hinting, actual imports in function if complex
if False: # TYPE_CHECKING
    from diplomacy import Game
    from diplomacy.models.game import GameHistory
    from .agent import DiplomacyAgent
import llm # Import the llm library

from .agent import ALL_POWERS, ALLOWED_RELATIONSHIPS
# run_llm_and_log is obsolete
from .utils import log_llm_response 
from .prompt_constructor import build_context_prompt

logger = logging.getLogger(__name__)

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
            model = llm.get_async_model(agent.model_id) # Use get_async_model for async operations
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
        
        except Exception as e_llm_call:
            logger.error(f"[{power_name}] LLM call or parsing failed during initialization: {e_llm_call}", exc_info=True)
            success_status = f"Failure: LLMErrorOrParse ({type(e_llm_call).__name__})"
            response_text = ""  # Ensure response_text is always defined
            # update_data remains {}

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
