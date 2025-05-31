"""
Handles the strategy for the Build phase of a Diplomacy game.

This module defines the BuildPhaseStrategy class, which is responsible for
determining build or disband orders for each power based on their supply
center gains or losses.
"""
import logging
import asyncio
from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from diplomacy import Game
    from ..game_history import GameHistory
    from .phase_orchestrator import PhaseOrchestrator

logger = logging.getLogger(__name__)

__all__ = ["BuildPhaseStrategy"]

class BuildPhaseStrategy:
    async def get_orders(
        self, game: "Game", orchestrator: "PhaseOrchestrator", game_history: "GameHistory"
    ) -> Dict[str, List[str]]:
        # Docstring already exists and is good.
        logger.info("Executing Build Phase actions via BuildPhaseStrategy...")
        current_phase_name = game.get_current_phase()
        orders_by_power: Dict[str, List[str]] = {}
        
        game_state = game.get_state()
        build_info = game_state.get('builds', {})

        powers_with_builds_or_disbands = [
            p for p in orchestrator.active_powers 
            if p in build_info and build_info[p].get('count', 0) != 0
        ]

        if not powers_with_builds_or_disbands:
            logger.info("No powers have builds or disbands this phase.")
            # Ensure all active powers are in the output, even if with empty orders
            for p_name in orchestrator.active_powers:
                if p_name not in orders_by_power:
                    orders_by_power[p_name] = []
            return orders_by_power

        tasks_to_run = []
        powers_for_tasks = [] # To map results back correctly

        for power_name in powers_with_builds_or_disbands:
            agent = orchestrator.agent_manager.get_agent(power_name)
            if agent:
                tasks_to_run.append(
                    orchestrator._get_orders_for_power(game, power_name, agent, game_history)
                )
                powers_for_tasks.append(power_name)
            else:
                logger.warning(
                    f"No agent found for active power {power_name} during build order generation."
                )
                orders_by_power[power_name] = [] # Pre-fill for powers with no agent
        
        if not tasks_to_run:
            logger.info("No valid agents found for powers requiring build/disband orders.")
            # Ensure all active powers are in the output
            for p_name in orchestrator.active_powers:
                if p_name not in orders_by_power:
                    orders_by_power[p_name] = []
            return orders_by_power
        
        results = await asyncio.gather(*tasks_to_run, return_exceptions=True)

        for i, power_name_for_task in enumerate(powers_for_tasks):
            if isinstance(results[i], Exception):
                logger.error(
                    f"Error getting build orders for {power_name_for_task}: {results[i]}",
                    exc_info=results[i],
                )
                orders_by_power[power_name_for_task] = []
            else:
                orders_by_power[power_name_for_task] = results[i]
            
            game_history.add_orders(
                current_phase_name, power_name_for_task, orders_by_power.get(power_name_for_task, [])
            )

        # For powers that were in active_powers but didn't have builds/disbands
        # (or had no agent and were pre-filled)
        for p_name in orchestrator.active_powers:
            if p_name not in orders_by_power:
                orders_by_power[p_name] = []

        return orders_by_power 