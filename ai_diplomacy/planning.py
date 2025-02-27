from dotenv import load_dotenv
import logging
import concurrent.futures

from diplomacy.engine.message import Message, GLOBAL

from .clients import load_model_client
from .utils import gather_possible_orders

logger = logging.getLogger("utils")
logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO)

load_dotenv()


def planning_phase(game, game_history, model_error_stats, max_rounds=3):
    """
    Lets each power form a strategic directive for the upcoming phase. 
    """
    active_powers = [
        p_name for p_name, p_obj in game.powers.items() if not p_obj.is_eliminated()
    ]

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=len(active_powers)
    ) as executor: 
        futures = {}
        for power_name in active_powers:
            model_id = game.power_model_map.get(power_name, "o3-mini")
            client = load_model_client(model_id)
            possible_orders = gather_possible_orders(game, power_name)
            if not possible_orders:
                logger.info(f"No orderable locations for {power_name}; skipping.")
                continue
            board_state = game.get_state()

            future = executor.submit(
                client.get_planning_reply,
                game,
                board_state,
                power_name,
                possible_orders,
                game_history,
                game.current_short_phase,
                active_powers,
            )

            futures[future] = power_name
            logger.debug(f"Submitted get_planning_reply task for {power_name}.")
        
        logger.info("Waiting for planning replies...")
        for future in concurrent.futures.as_completed(futures):
            power_name = futures[future]
            try:
                reply = future.result()
                logger.info(f"Received planning reply from {power_name}.")
                if reply:
                    game_history.add_plan(
                        game.current_short_phase, power_name, reply
                    )
            except Exception as e:
                logger.error(f"Error in planning reply for {power_name}: {e}")
                model_error_stats[power_name] += 1
        
    logger.info("Planning phase complete.")
    return game_history