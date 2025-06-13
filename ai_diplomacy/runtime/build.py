"""
Handles the strategy for the Build phase of a Diplomacy game.

This module defines the BuildPhaseStrategy class, which is responsible for
determining build or disband orders for each power based on their supply
center gains or losses.
"""

import logging
import asyncio
from typing import Dict, List, TYPE_CHECKING, Set

from ..agents.bloc_llm_agent import BlocLLMAgent
from ai_diplomacy.domain import PhaseState

if TYPE_CHECKING:
    from diplomacy import Game
    from ..game_history import GameHistory
    from .phase_orchestrator import PhaseOrchestrator

logger = logging.getLogger(__name__)

__all__ = ["BuildPhaseStrategy"]


class BuildPhaseStrategy:
    async def get_orders(
        self,
        game: "Game",
        phase: "PhaseState",
        orchestrator: "PhaseOrchestrator",
        game_history: "GameHistory",
    ) -> Dict[str, List[str]]:
        # Docstring already exists and is good.
        logger.info("Executing Build Phase actions via BuildPhaseStrategy...")
        current_phase_name = phase.name
        orders_by_power: Dict[str, List[str]] = {}

        processed_bloc_agent_ids: Set[str] = set()

        game_state = game.get_state()
        build_info = game_state.get("builds", {})

        # Renamed for clarity based on plan, but logic is same as original powers_with_builds_or_disbands
        powers_with_builds = [
            p for p in orchestrator.active_powers if p in build_info and build_info[p].get("count", 0) != 0
        ]

        if not powers_with_builds:
            logger.info("No powers have builds or disbands this phase.")
            for p_name in orchestrator.active_powers:
                if p_name not in orders_by_power:  # Should be all at this point
                    orders_by_power[p_name] = []
            return orders_by_power

        non_bloc_order_tasks = []
        non_bloc_power_names_for_tasks = []

        for power_name in powers_with_builds:
            agent = orchestrator.agent_manager.get_agent(power_name)
            if not agent:
                logger.warning(f"No agent found for power {power_name} requiring build/disband orders.")
                orders_by_power[power_name] = []
                game_history.add_orders(current_phase_name, power_name, [])  # Record empty orders
                continue

            if isinstance(agent, BlocLLMAgent):
                if agent.agent_id in processed_bloc_agent_ids:
                    logger.debug(
                        f"Skipping already processed bloc agent {agent.agent_id} for power {power_name}"
                    )
                    # This power's orders (if any) will be handled when its bloc agent is processed.
                    continue
                else:
                    logger.debug(
                        f"Processing BlocLLMAgent {agent.agent_id} for builds involving {power_name}..."
                    )
                    try:
                        await agent.decide_orders(phase)
                        current_phase_key_for_bloc = (
                            phase.key.state,
                            phase.key.scs,
                            phase.key.year,
                            phase.key.season,
                            phase.name,
                        )
                        all_bloc_orders_obj = agent.get_all_bloc_orders_for_phase(current_phase_key_for_bloc)

                        for (
                            bloc_power_name,
                            order_obj_list,
                        ) in all_bloc_orders_obj.items():
                            if (
                                bloc_power_name in powers_with_builds
                            ):  # Only add if this power actually has builds
                                orders_str_list = [str(o) for o in order_obj_list]
                                orders_by_power[bloc_power_name] = orders_str_list
                                game_history.add_orders(current_phase_name, bloc_power_name, orders_str_list)
                                logger.debug(
                                    f"✅ {bloc_power_name} (Bloc): Generated {len(orders_str_list)} build/disband orders"
                                )
                        processed_bloc_agent_ids.add(agent.agent_id)
                    except Exception as e:
                        logger.error(
                            f"❌ Error getting build orders for bloc agent {agent.agent_id}, power {power_name}: {e}",
                            exc_info=e,
                        )
                        # Handle errors for bloc members needing builds
                        for bloc_member_power in agent.get_bloc_member_powers():
                            if (
                                bloc_member_power in powers_with_builds
                                and bloc_member_power not in orders_by_power
                            ):
                                orders_by_power[bloc_member_power] = []
                                game_history.add_orders(
                                    current_phase_name, bloc_member_power, []
                                )  # Record empty due to error
            else:  # Not a BlocLLMAgent
                logger.debug(f"Queueing build/disband order generation for {power_name}...")
                non_bloc_order_tasks.append(
                    orchestrator._get_orders_for_power(game, power_name, agent, game_history)
                )
                non_bloc_power_names_for_tasks.append(power_name)

        if non_bloc_order_tasks:
            results = await asyncio.gather(*non_bloc_order_tasks, return_exceptions=True)
            for i, power_name_for_task in enumerate(non_bloc_power_names_for_tasks):
                if isinstance(results[i], Exception):
                    logger.error(
                        f"Error getting build orders for {power_name_for_task}: {results[i]}",
                        exc_info=results[i],
                    )
                    orders_by_power[power_name_for_task] = []
                else:
                    orders_by_power[power_name_for_task] = results[i]

                # Add to game history here as _get_orders_for_power might not do it (consistency)
                game_history.add_orders(
                    current_phase_name,
                    power_name_for_task,
                    orders_by_power.get(power_name_for_task, []),
                )

        # Ensure all powers in orchestrator.active_powers have an entry in orders_by_power,
        # defaulting to empty if not set (e.g. had no builds, or no agent).
        for p_name in orchestrator.active_powers:
            if p_name not in orders_by_power:
                orders_by_power[p_name] = []
                # Do not add to game_history here, as these powers didn't have actions for *this* phase (builds)

        return orders_by_power
