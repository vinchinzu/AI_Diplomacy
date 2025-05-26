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

class LLMInvalidOutputError(Exception):
    """Custom exception for invalid or unparsable LLM output in development mode."""
    def __init__(self, message, prompt=None, raw_response=None, proposed_moves=None, invalid_moves=None):
        super().__init__(message)
        self.prompt = prompt
        self.raw_response = raw_response
        self.proposed_moves = proposed_moves
        self.invalid_moves = invalid_moves

# Helper function to validate extracted orders (adapted from BaseModelClient)
def _validate_extracted_orders(
    game: Game, # Added game parameter for validation
    power_name: str,
    model_id: str, # For logging
    moves: List[str], 
    possible_orders: Dict[str, List[str]],
    fallback_utility_fn, # Function to call for fallback orders
    dev_mode: bool = False, # Added dev_mode
    # For detailed error reporting in dev_mode
    original_prompt: Optional[str] = None,
    raw_llm_response: Optional[str] = None
) -> List[str]:
    """
    Filter out invalid moves, fill missing with HOLD, else fallback.
    In dev_mode, raises LLMInvalidOutputError on critical failures.
    Returns a list of orders to be set for the power.
    """
    if not isinstance(moves, list):
        logger.warning(f"[{model_id}] Proposed moves for {power_name} not a list: {moves}.")
        if dev_mode:
            raise LLMInvalidOutputError(
                f"LLM output for {power_name} ({model_id}) was not a list of moves.",
                prompt=original_prompt,
                raw_response=raw_llm_response,
                proposed_moves=moves
            )
        return fallback_utility_fn(possible_orders)

    logger.debug(f"[{model_id}] Validating LLM proposed moves for {power_name}: {moves}")
    validated = []
    invalid_moves_found = []
    used_locs = set()

    # Create a flat list of all possible orders for quick lookup
    all_possible_orders = []
    for loc_orders in possible_orders.values():
        all_possible_orders.extend(loc_orders)
    all_possible_orders_set = set(all_possible_orders)

    for move_str in moves:
        if not move_str or not isinstance(move_str, str) or move_str.strip() == "": # Skip empty or non-string moves
            continue
        
        move_str = move_str.strip()
        
        # Check if the move is in the possible orders list (most reliable check)
        if move_str in all_possible_orders_set:
            validated.append(move_str)
            # Extract unit location from the move (first two parts: "A PAR" from "A PAR H")
            tokens = move_str.split()
            if len(tokens) >= 2:
                used_locs.add(tokens[1][:3]) # Add unit location (e.g., "PAR" from "A PAR H")
        else:
            logger.debug(f"[{model_id}] Invalid move from LLM for {power_name}: {move_str}")
            invalid_moves_found.append(move_str)
            
            # Additional diagnostic logging to help understand why the move is invalid
            tokens = move_str.split()
            if len(tokens) >= 2:
                unit_type = tokens[0]  # A or F
                unit_loc = tokens[1]   # PAR, BRE, etc.
                
                # Check if this power even has a unit at this location
                board_state = game.get_state()
                power_units = board_state.get("units", {}).get(power_name, [])
                expected_unit = f"{unit_type} {unit_loc}"
                
                if expected_unit not in power_units:
                    logger.warning(f"[{model_id}] {power_name} tried to order unit '{expected_unit}' but doesn't control it. {power_name} units: {power_units}")
                else:
                    logger.warning(f"[{model_id}] {power_name} has unit '{expected_unit}' but order '{move_str}' is not in possible orders for that unit.")

    if invalid_moves_found:
        logger.info(f"[{model_id}] Some LLM-proposed moves for {power_name} were invalid. Invalid: {invalid_moves_found}")
        if dev_mode:
            # Provide more detailed error information
            board_state = game.get_state()
            power_units = board_state.get("units", {}).get(power_name, [])
            error_details = []
            
            for invalid_move in invalid_moves_found:
                tokens = invalid_move.split()
                if len(tokens) >= 2:
                    unit_type = tokens[0]
                    unit_loc = tokens[1]
                    expected_unit = f"{unit_type} {unit_loc}"
                    
                    if expected_unit not in power_units:
                        error_details.append(f"'{invalid_move}' - {power_name} doesn't control unit {expected_unit}")
                    else:
                        error_details.append(f"'{invalid_move}' - not a valid order for unit {expected_unit}")
                else:
                    error_details.append(f"'{invalid_move}' - malformed order")
            
            detailed_message = f"LLM for {power_name} ({model_id}) produced invalid moves:\n" + "\n".join(error_details)
            detailed_message += f"\n\n{power_name} controls these units: {power_units}"
            
            raise LLMInvalidOutputError(
                detailed_message,
                prompt=original_prompt,
                raw_response=raw_llm_response,
                proposed_moves=moves,
                invalid_moves=invalid_moves_found
            )
    
    # Fill missing with hold (only if not in dev_mode or if no invalid_moves_found in dev_mode)
    if not (dev_mode and invalid_moves_found):
        for loc, orders_list in possible_orders.items():
            # Extract unit location from the key (e.g., "A PAR" -> "PAR")
            loc_parts = loc.split()
            if len(loc_parts) >= 2:
                unit_loc_prefix = loc_parts[1][:3]  # e.g., "PAR" from "A PAR"
            else:
                unit_loc_prefix = loc[:3]  # fallback
                
            if unit_loc_prefix not in used_locs and orders_list:
                hold_candidates = [o for o in orders_list if o.endswith(" H")]
                if hold_candidates:
                    validated.append(hold_candidates[0])
                    logger.debug(f"[{model_id}] Added HOLD for unassigned unit at {loc} for {power_name}.")
                elif orders_list:
                    validated.append(orders_list[0])
                    logger.debug(f"[{model_id}] Added first available order for unassigned unit at {loc} for {power_name}.")

    if not validated:
        logger.warning(f"[{model_id}] No valid orders could be confirmed for {power_name} after validation and hold fill. Using fallback.")
        if dev_mode: # If dev_mode is on and we still have no validated orders (e.g., LLM returned empty, or all were invalid and caught above)
             raise LLMInvalidOutputError(
                f"LLM for {power_name} ({model_id}) resulted in no valid orders even after attempting hold fills (or holds were skipped due to prior errors in dev_mode).",
                prompt=original_prompt,
                raw_response=raw_llm_response,
                proposed_moves=moves,
                invalid_moves=invalid_moves_found
            )
        return fallback_utility_fn(possible_orders)
    
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
    # --- New GameConfig dependent parameters ---
    config: 'GameConfig', # Pass GameConfig for dev_mode and other settings
    # --- End GameConfig dependent parameters ---
    agent_goals: Optional[List[str]] = None, # Already present
    agent_relationships: Optional[Dict[str, str]] = None, # Already present
    agent_private_diary_str: Optional[str] = None, # Already present
    log_file_path: str = None, # Already present
    phase: str = None, # Already present
    # dev_mode: bool = False # Added dev_mode, now part of config
) -> List[str]:
    """
    Generates orders using the specified LLM model, then validates and returns them.
    If generation or validation fails, returns fallback orders unless in dev_mode.
    """
    dev_mode = config.dev_mode # Get dev_mode from GameConfig
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

    raw_response = ""
    llm_proposed_moves = None

    try:
        # Using the coordinator's request method which internally uses llm_call_internal
        # Parameters for llm_call_internal are game_id, agent_name, phase_str
        # Here, power_name can be used as agent_name for the call.
        # phase is already available as a parameter.
        raw_response = await coordinator.request(
            model_id=model_id,
            prompt_text=prompt,
            system_prompt_text=agent_system_prompt,
            game_id=game_id,
            agent_name=power_name, # Using power_name as agent_name
            phase_str=phase,       # Using phase as phase_str
            request_identifier=f"{power_name}-{phase}-order_gen"
        )

        llm_proposed_moves = _extract_moves_from_llm_response(raw_response, power_name, model_id)
        if llm_proposed_moves is None and dev_mode:
            raise LLMInvalidOutputError(
                f"Failed to extract any moves from LLM response for {power_name} ({model_id}).",
                prompt=prompt,
                raw_response=raw_response
            )

    except Exception as e:
        logger.error(f"[{model_id}] Error during LLM call for {power_name}: {e}", exc_info=True)
        if dev_mode:
            # If the error is already our custom one, re-raise it. Otherwise, wrap it.
            if isinstance(e, LLMInvalidOutputError):
                raise
            raise LLMInvalidOutputError(
                f"LLM call failed for {power_name} ({model_id}): {e}",
                prompt=prompt,
                raw_response=raw_response # raw_response might be empty if error was before/during call
            ) from e
        # Fallback if not dev_mode or if we want to ensure _validate_extracted_orders handles it
        # No, if LLM call fails, llm_proposed_moves will be None, and _validate will use fallback.

    # Validate and fill missing orders (pass dev_mode and raw_response for error reporting)
    return _validate_extracted_orders(
        game=game,
        power_name=power_name, 
        model_id=model_id,
        moves=llm_proposed_moves if llm_proposed_moves is not None else [], # Pass empty list if None
        possible_orders=possible_orders, 
        fallback_utility_fn=_fallback_orders_utility,
        dev_mode=dev_mode,
        original_prompt=prompt,
        raw_llm_response=raw_response
    )


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