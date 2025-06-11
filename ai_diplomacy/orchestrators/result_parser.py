import logging
from typing import Dict, List, Optional
from diplomacy import Game

logger = logging.getLogger(__name__)


class GameResultParser:
    """
    Extracts adjudicated order results from a processed Game object.

    This class centralizes the brittle logic of finding results, which may
    be stored in different attributes depending on the game library version.
    """

    def extract_adjudicated_orders(
        self, game: Game, power_names: List[str]
    ) -> Dict[str, List[List[str]]]:
        """
        Finds and returns the adjudicated orders for the given powers.

        This method attempts to find adjudicated orders from various attributes
        of the processed 'game' object.

        Returns a dictionary mapping power_name to a list of its results.
        If results for a power cannot be found, it returns an empty list for that power.
        """
        all_results: Dict[str, List[List[str]]] = {}
        raw_orders: Optional[Dict[str, List[str]]] = None

        # The logic to extract orders is centralized here. This part is brittle
        # because it depends on the internals of the diplomacy library.
        # We try a few common attributes where results might be stored.

        # Attempt 1: 'resolved_orders' attribute
        if hasattr(game, "resolved_orders"):
            resolved_orders = getattr(game, "resolved_orders")
            if isinstance(resolved_orders, dict):
                logger.debug("Extracting orders from 'game.resolved_orders'")
                raw_orders = {p: list(o) for p, o in resolved_orders.items()}

        # Attempt 2: game.get_orders() if 'resolved_orders' not found
        if raw_orders is None:
            try:
                orders = game.get_orders()
                if orders and isinstance(orders, dict):
                    logger.debug("Extracting orders from 'game.get_orders()'")
                    raw_orders = {p: list(o) for p, o in orders.items()}
            except Exception as e:
                logger.debug(f"Could not get orders via game.get_orders(): {e}")

        # Attempt 3: 'orders' attribute if still not found
        if raw_orders is None and hasattr(game, "orders"):
            orders_attr = getattr(game, "orders")
            if isinstance(orders_attr, dict):
                logger.debug("Extracting orders from 'game.orders'")
                raw_orders = {p: list(o) for p, o in orders_attr.items()}

        if not raw_orders:
            logger.warning(
                "Could not extract adjudicated orders from game object. Returning empty dictionary for all powers."
            )
            # Following the logic of not finding any orders, so returning empty for all.
            return {power_name: [] for power_name in power_names}

        for power_name in power_names:
            if power_name in raw_orders:
                # The format List[List[str]] is unusual, but matches the user's request.
                # It wraps each order string in its own list.
                all_results[power_name] = [[order] for order in raw_orders[power_name]]
            else:
                logger.warning(
                    f"Could not find orders for '{power_name}' in extracted orders source."
                )
                all_results[power_name] = []

        return all_results
