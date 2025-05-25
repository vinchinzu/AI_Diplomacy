from dotenv import load_dotenv
import logging
import os
from typing import Dict, List, Tuple, Set, Optional
from diplomacy import Game
import csv
# TYPE_CHECKING for BaseModelClient removed as it's obsolete.
# from typing import TYPE_CHECKING
# if TYPE_CHECKING:
    # from .agent import DiplomacyAgent # Keep if DiplomacyAgent hint is still needed elsewhere
import llm # Import the llm library
import re
import ast
import json
from .prompt_constructor import construct_order_generation_prompt
from .llm_coordinator import LocalLLMCoordinator # Added import


logger = logging.getLogger("utils")
logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO)

load_dotenv()


def assign_models_to_powers(fixed_models_str: Optional[str] = None) -> Dict[str, str]:
    """
    DEPRECATED: Model assignment is now primarily handled by AgentManager using GameConfig
    which loads from a TOML file and considers command-line arguments.
    This function remains for potential standalone utilities that might not have a full GameConfig.
    It provides a very basic assignment logic.
    """
    logger.warning(
        "DEPRECATION WARNING: utils.assign_models_to_powers() is deprecated. "
        "Model assignment is primarily handled by AgentManager and GameConfig. "
        "This function provides a basic fallback and may be removed in the future."
    )
    powers = ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"]
    assigned_models: Dict[str, str] = {}
    model_list: List[str] = []

    # Simplified logic: Use fixed_models_str if provided, else a hardcoded default.
    if fixed_models_str:
        model_list = [m.strip() for m in fixed_models_str.split(',') if m.strip()]
        logger.info(f"[Deprecated utils.assign_models] Using fixed_models_str: {model_list}")
    
    if not model_list:
        # Try POWER_MODELS env var as a secondary fallback for this deprecated function
        power_models_env = os.environ.get("POWER_MODELS")
        if power_models_env:
            model_list = [m.strip() for m in power_models_env.split(',') if m.strip()]
            logger.info(f"[Deprecated utils.assign_models] Using POWER_MODELS env var: {model_list}")
        else:
            # Final fallback to a single model for all powers
            default_model_for_util = os.environ.get("MODEL_NAME", "ollama/gemma3:4b")
            logger.info(f"[Deprecated utils.assign_models] No fixed_models_str or POWER_MODELS. Defaulting all to: {default_model_for_util}")
            for power in powers:
                assigned_models[power] = default_model_for_util
            return assigned_models

    if not model_list: # Should not happen if default_model_for_util logic is hit
        logger.error("[Deprecated utils.assign_models] Model list empty. Cannot assign.")
        return {}

    for i, power in enumerate(powers):
        assigned_models[power] = model_list[i % len(model_list)]
    
    logger.info(f"[Deprecated utils.assign_models] Final assignments: {assigned_models}")
    return assigned_models

def gather_possible_orders(game: Game, power_name: str) -> Dict[str, List[str]]:
    """
    Returns a dictionary mapping each orderable location to the list of valid orders.
    """
    orderable_locs = game.get_orderable_locations(power_name)
    all_possible = game.get_all_possible_orders()

    result = {}
    for loc in orderable_locs:
        result[loc] = all_possible.get(loc, [])
    return result

# Helper function to provide fallback orders (all units HOLD)
def _fallback_orders_utility(possible_orders: Dict[str, List[str]]) -> List[str]:
    """Generates a list of HOLD orders for all units if possible, else first option."""
    fallback = []
    for loc, orders_list in possible_orders.items():
        if orders_list:
            holds = [o for o in orders_list if o.endswith(" H")]
            fallback.append(holds[0] if holds else orders_list[0])
    return fallback

# Helper function to extract moves from LLM response (adapted from BaseModelClient)
def _extract_moves_from_llm_response(raw_response: str, power_name: str, model_id: str) -> Optional[List[str]]:
    """
    Attempt multiple parse strategies to find JSON array of moves.
    """
    logger.debug(f"[{model_id}] Attempting to extract moves for {power_name} from raw response: {raw_response[:300]}...")
    # Regex for "PARSABLE OUTPUT:{...}"
    pattern = r"PARSABLE OUTPUT:\s*(\{[\s\S]*\})"
    matches = re.search(pattern, raw_response, re.DOTALL)

    if not matches:
        logger.debug(f"[{model_id}] Regex for 'PARSABLE OUTPUT:' failed for {power_name}. Trying alternative patterns.")
        pattern_alt = r"PARSABLE OUTPUT\s*\{(.*?)\}\s*$" # Check for inline JSON
        matches = re.search(pattern_alt, raw_response, re.DOTALL)

    if not matches: # Check for triple-backtick code fences
        logger.debug(f"[{model_id}] Regex for inline 'PARSABLE OUTPUT' failed. Trying triple-backtick code fences for {power_name}.")
        code_fence_pattern = r"```json\n(.*?)\n```"
        matches = re.search(code_fence_pattern, raw_response, re.DOTALL)
        if matches: logger.debug(f"[{model_id}] Found triple-backtick JSON block for {power_name}.")

    json_text = None
    if matches:
        json_text = matches.group(1).strip()
        if not json_text.startswith("{"): # Ensure it's a valid JSON object start
             json_text = "{" + json_text # Add missing brace if needed (e.g. from pattern_alt)
        if not json_text.endswith("}"):
             json_text = json_text + "}"
    
    if not json_text:
        logger.debug(f"[{model_id}] No JSON text found in LLM response for {power_name}.")
        return None

    try:
        data = json.loads(json_text)
        return data.get("orders", None)
    except json.JSONDecodeError as e:
        logger.warning(f"[{model_id}] JSON decode failed for {power_name}: {e}. JSON text was: '{json_text}'. Trying bracket fallback.")
        bracket_pattern = r'["\']orders["\']\s*:\s*\[([^\]]*)\]' # orders: ['A BUD H']
        bracket_match = re.search(bracket_pattern, json_text, re.DOTALL)
        if bracket_match:
            try:
                raw_list_str = "[" + bracket_match.group(1).strip() + "]"
                moves = ast.literal_eval(raw_list_str)
                if isinstance(moves, list):
                    logger.debug(f"[{model_id}] Bracket fallback parse succeeded for {power_name}.")
                    return moves
            except Exception as e2:
                logger.warning(f"[{model_id}] Bracket fallback parse also failed for {power_name}: {e2}")
    
    logger.warning(f"[{model_id}] All move extraction attempts failed for {power_name}.")
    return None

# Helper function to validate extracted orders (adapted from BaseModelClient)
def _validate_extracted_orders(
    game: Game, # Added game parameter for validation
    power_name: str,
    model_id: str, # For logging
    moves: List[str], 
    possible_orders: Dict[str, List[str]],
    fallback_utility_fn # Function to call for fallback orders
) -> List[str]:
    """
    Filter out invalid moves, fill missing with HOLD, else fallback.
    Returns a list of orders to be set for the power.
    """
    if not isinstance(moves, list):
        logger.warning(f"[{model_id}] Proposed moves for {power_name} not a list: {moves}. Using fallback.")
        return fallback_utility_fn(possible_orders)

    logger.debug(f"[{model_id}] Validating LLM proposed moves for {power_name}: {moves}")
    validated = []
    invalid_moves_found = []
    used_locs = set()

    for move_str in moves:
        if not move_str or not isinstance(move_str, str) or move_str.strip() == "": # Skip empty or non-string moves
            continue
        
        # Check if it's in possible orders (simple check, game.is_valid_order is more robust)
        # if any(move_str in loc_orders for loc_orders in possible_orders.values()):
        #     validated.append(move_str)
        #     parts = move_str.split()
        #     if len(parts) >= 2:
        #         used_locs.add(parts[1][:3]) #  e.g., 'A PAR H' -> 'PAR'
        # else:
        #     logger.debug(f"[{model_id}] Invalid move from LLM for {power_name} (not in possible_orders): {move_str}")
        #     invalid_moves_found.append(move_str)
            
        # More robust validation using game object
        tokens = move_str.split(" ", 2)
        is_valid_order_flag = False
        if len(tokens) >= 3:
            unit_token = " ".join(tokens[:2])
            order_part_token = tokens[2]
            try:
                # game._valid_order is not public, use game.is_valid_order if available and suitable,
                # or rely on the possible_orders list which should be pre-validated by the engine.
                # For now, let's check against possible_orders for simplicity if direct validation is tricky.
                # A more robust solution would be to use game.get_all_possible_orders() and check against that.
                if any(move_str == po for loc_orders in possible_orders.values() for po in loc_orders):
                    is_valid_order_flag = True
                else: # Try direct validation if diplomacy.py version supports is_valid_order well
                    if hasattr(game, 'is_valid_order') and callable(game.is_valid_order):
                         is_valid_order_flag = game.is_valid_order(power_name, move_str) # This might need adaptation based on exact signature
                    else: # Fallback to old _valid_order logic if is_valid_order not available
                        is_valid_order_flag = (game._valid_order(game.powers[power_name], unit_token, order_part_token, report=0) == 1)


            except Exception as e_val:
                logger.warning(f"[{model_id}] Error validating order '{move_str}' for {power_name}: {e_val}")
                is_valid_order_flag = False
        
        if is_valid_order_flag:
            validated.append(move_str)
            if len(tokens) >=2: used_locs.add(tokens[1][:3]) # Add unit location
        else:
            logger.debug(f"[{model_id}] Invalid move from LLM for {power_name}: {move_str}")
            invalid_moves_found.append(move_str)


    # Fill missing with hold
    for loc, orders_list in possible_orders.items():
        unit_loc_prefix = loc.split(" ")[1][:3] if " " in loc else loc[:3] # e.g. "A PAR" -> PAR
        if unit_loc_prefix not in used_locs and orders_list:
            hold_candidates = [o for o in orders_list if o.endswith(" H")]
            validated.append(hold_candidates[0] if hold_candidates else orders_list[0])
            logger.debug(f"[{model_id}] Added HOLD for unassigned unit at {loc} for {power_name}.")

    if not validated and invalid_moves_found:
        logger.warning(f"[{model_id}] All LLM moves for {power_name} were invalid. Using fallback. Invalid: {invalid_moves_found}")
        return fallback_utility_fn(possible_orders)
    elif not validated: # No moves from LLM, and no invalid ones (e.g. LLM returned empty list)
        logger.warning(f"[{model_id}] No valid LLM moves provided for {power_name} and no invalid ones to report. Using fallback.")
        return fallback_utility_fn(possible_orders)

    if invalid_moves_found: # Some valid, some invalid
         logger.info(f"[{model_id}] Some LLM-proposed moves for {power_name} were invalid. Using validated subset and fallbacks for missing. Invalid: {invalid_moves_found}")
    
    return validated


async def get_valid_orders(
    game: Game,
    model_id: str, # Changed from client
    agent_system_prompt: Optional[str], # Added system prompt
    board_state, # Already present
    power_name: str, # Already present
    possible_orders: Dict[str, List[str]], # Already present
    game_history, # Already present, assumed to be GameHistory instance
    game_id: str, # Added game_id parameter
    agent_goals: Optional[List[str]] = None, # Already present
    agent_relationships: Optional[Dict[str, str]] = None, # Already present
    agent_private_diary_str: Optional[str] = None, # Already present
    log_file_path: str = None, # Already present
    phase: str = None, # Already present
) -> List[str]:
    """
    Generates orders using the specified LLM model, then validates and returns them.
    If generation or validation fails, returns fallback orders.
    """
    # Import the coordinator here to avoid circular imports - No longer needed if imported at top
    # from .llm_coordinator import LocalLLMCoordinator 
    
    # Instantiate or get a global coordinator instance
    # For simplicity in this fix, let's assume one is instantiated here or globally available.
    # If you have a single global instance (e.g., in agent.py or a central app module),
    # you might need to pass it as a parameter to get_valid_orders.
    # For now, creating a local instance to make it runnable:
    coordinator = LocalLLMCoordinator()

    prompt = construct_order_generation_prompt(
        system_prompt=agent_system_prompt,
        game=game,
        board_state=board_state,
        power_name=power_name,
        possible_orders=possible_orders,
        game_history=game_history,
        agent_goals=agent_goals,
        agent_relationships=agent_relationships,
        agent_private_diary_str=agent_private_diary_str
    )

    if not prompt:
        logger.error(f"[{model_id}] Prompt construction failed for {power_name}. Using fallback orders.")
        # model_error_stats.setdefault(model_id, {}).setdefault("prompt_errors", 0)
        # model_error_stats[model_id]["prompt_errors"] += 1
        return _fallback_orders_utility(possible_orders)

    raw_response_text = "" # Initialize
    llm_call_result = None

    try:
        request_identifier = f"{power_name}-{phase}-order_gen"
        # TODO: Replace placeholders for game_id, agent_name, and phase_str with actual values.
        # This might involve adding game_id as a parameter to get_valid_orders.
        # current_game_id_placeholder = "unknown_game_id_utils" # Placeholder
        
        llm_call_result = await coordinator.call_llm_with_json_parsing(
            model_id=model_id,
            prompt=prompt,
            system_prompt=agent_system_prompt,
            request_identifier=request_identifier,
            expected_json_fields=["orders"], # Expecting a list of orders
            # --- Parameters for new llm_call_internal & file logging ---
            game_id=game_id, # Replaced placeholder with game_id parameter
            agent_name=power_name, # Use power_name as agent_name
            phase_str=phase if phase else "unknown_phase_utils", # Use provided phase or placeholder
            response_type="order_generation",
            log_to_file_path=log_file_path
        )

        if llm_call_result.success and llm_call_result.parsed_json:
            # The _extract_moves_from_llm_response logic might be redundant
            # if call_llm_with_json_parsing already gives us the parsed "orders" field.
            # We'll try to get "orders" directly from parsed_json first.
            extracted_moves = llm_call_result.parsed_json.get("orders")
            if extracted_moves is None: # Fallback to old extraction if "orders" not top-level
                 logger.warning(f"[{model_id}] 'orders' field not found directly in parsed JSON for {power_name}. Trying raw response parsing.")
                 extracted_moves = _extract_moves_from_llm_response(llm_call_result.raw_response, power_name, model_id)
            raw_response_text = llm_call_result.raw_response # For logging or further debugging
        elif llm_call_result.success: # Success but no JSON or "orders" field
            logger.warning(f"[{model_id}] LLM call succeeded for {power_name} but no valid JSON 'orders' found. Raw: {llm_call_result.raw_response[:100]}...")
            extracted_moves = _extract_moves_from_llm_response(llm_call_result.raw_response, power_name, model_id)
            raw_response_text = llm_call_result.raw_response
        else: # LLM call failed
            logger.error(f"[{model_id}] LLM call failed for {power_name} in get_valid_orders: {llm_call_result.error_message}")
            # model_error_stats.setdefault(model_id, {}).setdefault("llm_api_errors", 0)
            # model_error_stats[model_id]["llm_api_errors"] += 1
            raw_response_text = llm_call_result.raw_response if llm_call_result.raw_response else f"Error: {llm_call_result.error_message}"
            extracted_moves = None # Ensure fallback if call failed

    except Exception as e:
        logger.error(f"[{model_id}] Unexpected error for {power_name} in get_valid_orders: {e}", exc_info=True)
        # model_error_stats.setdefault(model_id, {}).setdefault("unknown_errors", 0)
        # model_error_stats[model_id]["unknown_errors"] += 1
        # Log the raw response if available, otherwise log the error
        # log_llm_response is now called by coordinator.call_llm_with_json_parsing
        return _fallback_orders_utility(possible_orders)

    if not extracted_moves:
        logger.warning(f"[{model_id}] No moves extracted for {power_name}. Using fallback. Raw response snippet: {raw_response_text[:200]}")
        # log_llm_response is handled by call_llm_with_json_parsing
        return _fallback_orders_utility(possible_orders)

    return _validate_extracted_orders(game, power_name, model_id, extracted_moves, possible_orders, _fallback_orders_utility)


def normalize_and_compare_orders(
    issued_orders: Dict[str, List[str]],
    accepted_orders_dict: Dict[str, List[str]],
    game: Game,
) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    """
    Normalizes and compares issued orders against accepted orders from the game engine.
    Uses the map's built-in normalization methods to ensure consistent formatting.

    Args:
        issued_orders: Dictionary of orders issued by power {power_name: [orders]}
        accepted_orders_dict: Dictionary of orders accepted by the engine,
                              typically from game.get_state()["orders"].
        game: The current Game object containing the map.

    Returns:
        Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]: (orders_not_accepted, orders_not_issued)
            - orders_not_accepted: Orders issued but not accepted by engine (normalized).
            - orders_not_issued: Orders accepted by engine but not issued (normalized).
    """
    game_map = game.map

    def normalize_order(order: str) -> str:
        # Inner function to normalize a single order string using the game map.
        if not order:
            return order

        try:
            # Use map's normalization methods directly
            normalized = game_map.norm(order)
            # Further split and normalize parts for complex orders if necessary
            # (This part might need refinement depending on how complex orders are handled
            #  and represented after initial normalization by game_map.norm)

            # Example (simplified, game_map.norm often handles this):
            # Split support orders
            # parts = normalized.split(" S ")
            # normalized_parts = []
            # for part in parts:
            #     move_parts = part.split(" - ")
            #     move_parts = [game_map.norm(p.strip()) for p in move_parts]
            #     move_parts = [game_map.aliases.get(p, p) for p in move_parts]
            #     normalized_parts.append(" - ".join(move_parts))
            # return " S ".join(normalized_parts)

            return normalized  # Return the directly normalized string for now
        except Exception as e:
            logger.warning(f"Could not normalize order '{order}': {e}")
            return order  # Return original if normalization fails

    orders_not_accepted = {}
    orders_not_issued = {}

    all_powers = set(issued_orders.keys()) | set(accepted_orders_dict.keys())

    for pwr in all_powers:
        # Normalize issued orders for the power, handling potential absence
        issued_set = set()
        if pwr in issued_orders:
            try:
                issued_set = {normalize_order(o) for o in issued_orders.get(pwr, []) if o}
            except Exception as e:
                logger.error(f"Error normalizing issued orders for {pwr}: {e}")

        # Normalize accepted orders for the power, handling potential absence
        accepted_set = set()
        if pwr in accepted_orders_dict:
            try:
                accepted_set = {normalize_order(o) for o in accepted_orders_dict.get(pwr, []) if o}
            except Exception as e:
                logger.error(f"Error normalizing accepted orders for {pwr}: {e}")

        # Compare the sets
        missing_from_engine = issued_set - accepted_set
        missing_from_issued = accepted_set - issued_set

        if missing_from_engine:
            orders_not_accepted[pwr] = missing_from_engine
        if missing_from_issued:
            orders_not_issued[pwr] = missing_from_issued

    return orders_not_accepted, orders_not_issued


# == New LLM Response Logging Function ==
def log_llm_response(
    log_file_path: str,
    model_name: str,
    power_name: Optional[str], # Optional for non-power-specific calls like summary
    phase: str,
    response_type: str,
    raw_input_prompt: str, # Kept for compatibility, but will not be logged
    raw_response: str,
    success: str,  # Changed from bool to str
):
    """
    Log only the LLM response and minimal metadata to the CSV. Do NOT log the full prompt/context to avoid huge files.
    """
    import csv
    import os
    # Only log minimal fields
    log_fields = ["model", "power", "phase", "response_type", "raw_response", "success"]
    log_row = [model_name, power_name or "", phase, response_type, raw_response, success]
    file_exists = os.path.isfile(log_file_path)
    with open(log_file_path, mode="a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(log_fields)
        writer.writerow(log_row)


# run_llm_and_log is now obsolete and removed.
# LLM calls are made directly using llm.get_model().async_prompt()
# and logging is handled by calling log_llm_response() immediately after.