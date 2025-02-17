from dotenv import load_dotenv
import logging

logger = logging.getLogger("utils")
logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO)

load_dotenv()


def assign_models_to_powers():
    """
    Example usage: define which model each power uses.
    Return a dict: { power_name: model_id, ... }
    POWERS = ['AUSTRIA', 'ENGLAND', 'FRANCE', 'GERMANY', 'ITALY', 'RUSSIA', 'TURKEY']
    """

    return {
        "FRANCE": "o3-mini",
        "GERMANY": "claude-3-5-sonnet-20241022",
        "ENGLAND": "gemini-2.0-flash",
        "RUSSIA": "gemini-2.0-flash-lite-preview-02-05",
        "ITALY": "gpt-4o",
        "AUSTRIA": "gpt-4o-mini",
        "TURKEY": "claude-3-5-haiku-20241022",
    }


def gather_possible_orders(game, power_name):
    """
    Returns a dictionary mapping each orderable location to the list of valid orders.
    """
    orderable_locs = game.get_orderable_locations(power_name)
    all_possible = game.get_all_possible_orders()

    result = {}
    for loc in orderable_locs:
        result[loc] = all_possible.get(loc, [])
    return result


def get_valid_orders_with_retry(
    game,
    client,
    board_state,
    power_name,
    possible_orders,
    conversation_text_for_orders,
    phase_summaries,
    model_error_stats,
    max_retries=3,
):
    """
    Tries up to 'max_retries' to generate and validate orders.
    If invalid, we append the error feedback to the conversation
    context for the next retry. If still invalid, return fallback.
    """
    error_feedback = ""
    for attempt in range(max_retries):
        # Incorporate any error feedback into the conversation text
        augmented_conversation_text = conversation_text_for_orders
        if error_feedback:
            augmented_conversation_text += (
                "\n\n[ORDER VALIDATION FEEDBACK]\n" + error_feedback
            )

        # Ask the LLM for orders
        orders = client.get_orders(
            game=game,
            board_state=board_state,
            power_name=power_name,
            possible_orders=possible_orders,
            conversation_text=augmented_conversation_text,
            phase_summaries=phase_summaries,
            model_error_stats=model_error_stats,
        )

        print(f"orders: {orders}")

        # Validate each order
        invalid_info = []
        for move in orders:
            # Example move: "A PAR H" -> unit="A PAR", order_part="H"
            tokens = move.split(" ", 2)
            if len(tokens) < 3:
                invalid_info.append(
                    f"Order '{move}' is malformed; expected 'A PAR H' style."
                )
                continue
            unit = " ".join(tokens[:2])  # e.g. "A PAR"
            order_part = tokens[2]  # e.g. "H" or "S A MAR"

            # Use the internal game validation method
            if order_part == "B":
                validity = 1  # hack because game._valid_order doesn't support 'B'
            else:
                validity = game._valid_order(
                    game.powers[power_name], unit, order_part, report=1
                )
            if validity != 1:
                import pdb

                pdb.set_trace()
                invalid_info.append(
                    f"Order '{move}' returned validity={validity}. (None/-1=invalid, 0=partial, 1=valid)"
                )

        if not invalid_info:
            # All orders are fully valid
            return orders
        else:
            # Build feedback for the next retry
            error_feedback = (
                f"Attempt {attempt + 1}/{max_retries} had invalid orders:\n"
                + "\n".join(invalid_info)
            )

    # If we finish the loop without returning, fallback
    logger.warning(
        f"[{power_name}] Exhausted {max_retries} attempts for valid orders, using fallback."
    )
    model_error_stats[power_name]["order_decoding_errors"] += 1
    fallback = client.fallback_orders(possible_orders)
    return fallback
