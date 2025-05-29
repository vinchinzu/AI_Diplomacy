import logging
import asyncio
from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from diplomacy import Game
    from ..game_history import GameHistory
    from .phase_orchestrator import PhaseOrchestrator

logger = logging.getLogger(__name__)

class RetreatPhaseStrategy:
    async def get_orders(
        self, game: "Game", orchestrator: "PhaseOrchestrator", game_history: "GameHistory"
    ) -> Dict[str, List[str]]:
        """Handles the logic for a retreat phase."""
        logger.info("Executing Retreat Phase actions via RetreatPhaseStrategy...")
        current_phase_name = game.get_current_phase()
        orders_by_power: Dict[str, List[str]] = {}
        order_tasks = []

        # Identify powers that actually need to retreat first
        powers_needing_retreat = [
            p for p in orchestrator.active_powers if game.powers[p].must_retreat
        ]

        if not powers_needing_retreat:
            logger.info("No powers need to retreat this phase.")
            # Ensure all active powers are in the output, even if with empty orders
            for p_name in orchestrator.active_powers:
                orders_by_power[p_name] = []
            return orders_by_power

        for power_name in powers_needing_retreat:
            agent = orchestrator.agent_manager.get_agent(power_name)
            if agent:
                order_tasks.append(
                    orchestrator._get_orders_for_power(game, power_name, agent, game_history)
                )
            else:
                logger.warning(
                    f"No agent found for active power {power_name} during retreat order generation."
                )
                # Ensure every power in powers_needing_retreat has an entry in orders_by_power for safety,
                # even if it's empty due to no agent.
                orders_by_power[power_name] = [] 

        # Gather results from all order generation tasks
        results = await asyncio.gather(*order_tasks, return_exceptions=True)

        for i, power_name in enumerate(powers_needing_retreat):
            # Skip if agent was not found and no task was created for this power
            if not orchestrator.agent_manager.get_agent(power_name):
                continue # orders_by_power[power_name] already set to []
            
            if isinstance(results[i], Exception):
                logger.error(
                    f"Error getting retreat orders for {power_name}: {results[i]}",
                    exc_info=results[i],
                )
                orders_by_power[power_name] = []
            else:
                orders_by_power[power_name] = results[i]
            
            game_history.add_orders(
                current_phase_name, power_name, orders_by_power.get(power_name, [])
            )

        # For powers that were in active_powers but didn't need to retreat,
        # ensure they have an empty order list in the final dict if they weren't added.
        for p_name in orchestrator.active_powers:
            if p_name not in orders_by_power:
                orders_by_power[p_name] = []

        return orders_by_power 