"""
Handles the strategy for the Movement phase of a Diplomacy game.

This module defines the MovementPhaseStrategy class, which is responsible for
managing diplomatic negotiations and collecting movement orders from each agent.
"""

import logging
from typing import Dict, List, TYPE_CHECKING, Set

# Import the new negotiation function
from .negotiation import perform_negotiation_rounds
from ..agents.bloc_llm_agent import BlocLLMAgent
from ai_diplomacy.domain import PhaseState

if TYPE_CHECKING:
    from diplomacy import Game
    from ..game_history import GameHistory
    from .phase_orchestrator import (
        PhaseOrchestrator,
    )  # Import PhaseOrchestrator for type hinting

logger = logging.getLogger(__name__)

__all__ = ["MovementPhaseStrategy"]


class MovementPhaseStrategy:
    async def get_orders(
        self,
        game: "Game",
        phase: "PhaseState",
        orchestrator: "PhaseOrchestrator",
        game_history: "GameHistory",
    ) -> Dict[str, List[str]]:
        logger.info("Executing Movement Phase actions via MovementPhaseStrategy...")
        current_phase_name = phase.name

        await perform_negotiation_rounds(
            game,
            phase,
            game_history,
            orchestrator.agent_manager,
            orchestrator.active_powers,  # active_powers are individual game power names
            orchestrator.config,
        )

        orders_by_power: Dict[str, List[str]] = {}
        processed_bloc_agent_ids: Set[str] = set()

        active_game_powers = orchestrator.active_powers

        # Gracefully handle scenarios where power_to_agent_id_map is missing or empty (as is
        # the case in our unit-tests). In that situation we simply treat each *power name*
        # itself as the look-up key for AgentManager.
        power_to_agent_id_map = getattr(orchestrator.config, "power_to_agent_id_map", {}) or {}

        for power_name in active_game_powers:
            agent_lookup_key = power_to_agent_id_map.get(power_name, power_name)

            agent = orchestrator.agent_manager.get_agent(agent_lookup_key)

            if not agent:
                # No agent available for this power – record warning and continue with
                # empty orders so the rest of the pipeline keeps running.
                logger.warning(
                    f"No agent found for active power {power_name} during movement order generation"
                )
                orders_by_power[power_name] = []
                game_history.add_orders(current_phase_name, power_name, [])
                continue

            if isinstance(agent, BlocLLMAgent):
                if agent.agent_id in processed_bloc_agent_ids:
                    logger.debug(
                        f"Skipping already processed bloc agent {agent.agent_id} (for power {power_name})"
                    )
                    # Order for this power_name should have been added when the bloc was first processed.
                    # If not, it implies an issue or that the power isn't in this bloc as expected.
                    if power_name not in orders_by_power:
                        logger.warning(
                            f"Power {power_name} was expected to have orders from bloc {agent.agent_id} but does not. Check bloc processing logic."
                        )
                        orders_by_power[
                            power_name
                        ] = []  # Default to empty if missed, though this state is unusual.
                    continue
                else:
                    logger.debug(
                        f"Processing BlocLLMAgent {agent.agent_id} for its controlled powers (triggered by {power_name})..."
                    )
                    try:
                        # Decide orders for the entire bloc. This populates the agent's internal cache.
                        await agent.decide_orders(phase)

                        # Construct the phase key to retrieve all bloc orders.
                        # This key must match the one used in BlocLLMAgent.decide_orders caching.
                        # Reconstruct the key carefully as done in BlocLLMAgent.
                        phase_repr_parts = []
                        if phase.board.units:  # Check if there are any units on the board
                            for p_n in sorted(agent.controlled_powers):
                                power_units_locs_list = phase.board.units.get(p_n, [])
                                phase_repr_parts.append(f"{p_n}_units:{tuple(sorted(power_units_locs_list))}")

                        if phase.board.supply_centers:  # Check if there is supply center data
                            sorted_scs_items = sorted(
                                [
                                    (p, tuple(sorted(cs)))
                                    for p, cs in phase.board.supply_centers.items()
                                ]
                            )
                            phase_repr_parts.append(f"scs:{tuple(sorted_scs_items)}")

                        current_phase_key_for_bloc = (
                            phase.key.year,
                            phase.key.season,
                            phase.name,
                            tuple(phase_repr_parts),
                        )

                        all_bloc_orders_obj = agent.get_all_bloc_orders_for_phase(current_phase_key_for_bloc)
                        if not all_bloc_orders_obj and agent.controlled_powers:
                            logger.warning(
                                f"BlocLLMAgent {agent.agent_id} returned no orders from get_all_bloc_orders_for_phase despite having controlled powers. LLM might have failed or returned empty."
                            )

                        for (
                            bloc_member_power_name,
                            order_obj_list,
                        ) in all_bloc_orders_obj.items():
                            if bloc_member_power_name not in agent.controlled_powers:
                                logger.warning(
                                    f"Bloc agent {agent.agent_id} returned orders for {bloc_member_power_name} which it does not control. Ignoring these orders."
                                )
                                continue
                            if bloc_member_power_name not in active_game_powers:
                                logger.warning(
                                    f"Bloc agent {agent.agent_id} returned orders for {bloc_member_power_name} which is not an active power in this phase. Ignoring."
                                )
                                continue

                            orders_str_list = [str(o) for o in order_obj_list]
                            orders_by_power[bloc_member_power_name] = orders_str_list
                            game_history.add_orders(
                                current_phase_name,
                                bloc_member_power_name,
                                orders_str_list,
                            )
                            logger.info(
                                f"AGENT_ORDERS: {bloc_member_power_name} (from Bloc {agent.agent_id}): {orders_str_list}"
                            )
                        processed_bloc_agent_ids.add(agent.agent_id)

                        # Ensure all controlled powers by this bloc that are active in the game have an entry in orders_by_power
                        for controlled_p in agent.controlled_powers:
                            if controlled_p in active_game_powers and controlled_p not in orders_by_power:
                                logger.warning(
                                    f"Controlled power {controlled_p} of bloc {agent.agent_id} did not receive orders. Defaulting to empty list."
                                )
                                orders_by_power[controlled_p] = []
                                game_history.add_orders(
                                    current_phase_name, controlled_p, []
                                )  # Log empty orders

                    except Exception as e:
                        logger.error(
                            f"CRITICAL_BLOC_FAILURE: Error processing bloc agent {agent.agent_id} (for power {power_name}): {e}",
                            exc_info=True,
                        )
                        # For a bloc failure, all its controlled (and active) powers get empty orders
                        for bloc_member_power in agent.controlled_powers:
                            if bloc_member_power in active_game_powers:
                                orders_by_power[bloc_member_power] = []
                                game_history.add_orders(current_phase_name, bloc_member_power, [])
                                logger.info(
                                    f"AGENT_ORDERS: {bloc_member_power} (from failed Bloc {agent.agent_id}): []"
                                )
                        processed_bloc_agent_ids.add(agent.agent_id)  # Mark as processed to avoid re-attempt

            else:  # Standard (non-bloc) LLM agent or other types
                logger.debug(f"Processing agent {agent_lookup_key} for power {power_name} (Movement)...")
                try:
                    orders = await orchestrator._get_orders_for_power(
                        game,
                        power_name,
                        agent,
                        game_history,  # power_name here is the actual power
                    )
                    orders_by_power[power_name] = orders
                    game_history.add_orders(current_phase_name, power_name, orders)
                    logger.info(f"AGENT_ORDERS: {power_name}: {orders}")
                except Exception as e:
                    logger.error(
                        f"❌ Error getting orders for {power_name} (Movement): {e}",
                        exc_info=True,
                    )
                    orders_by_power[power_name] = []
                    game_history.add_orders(
                        current_phase_name, power_name, []
                    )  # Ensure history reflects empty orders
                    logger.info(f"AGENT_ORDERS: {power_name} (failed): []")

        # The specific Neutral Italy handling might need to be revised or integrated
        # if Italy is now part of a bloc managed by NEUTRAL_ITALY_BLOC agent.
        # If NEUTRAL_ITALY_BLOC is a proper agent in power_to_agent_id_map, it should be handled above.
        # The code below is a fallback if ITALY is in game.powers but not in active_game_powers
        # (e.g. if active_powers list is filtered somehow).

        italy_power_name = "ITALY"
        if italy_power_name in game.powers and italy_power_name not in orders_by_power:
            # This implies ITALY was not in active_game_powers or its agent failed to provide orders.
            # If it has an agent, it should have been processed. If no agent, it means it's truly neutral.
            agent_id_for_italy = orchestrator.config.power_to_agent_id_map.get(italy_power_name)
            if not agent_id_for_italy or not orchestrator.agent_manager.get_agent(agent_id_for_italy):
                logger.info(
                    f"Power {italy_power_name} has no assigned agent and was not processed. Assuming neutral hold orders."
                )
                italy_units = phase.board.get_units(italy_power_name)
                if italy_units:
                    hold_orders = [f"{unit_name} H" for unit_name in italy_units]
                    orders_by_power[italy_power_name] = hold_orders
                    logger.info(
                        f"Generated Hold orders for unmanaged neutral {italy_power_name}: {hold_orders}"
                    )
                    game_history.add_orders(current_phase_name, italy_power_name, hold_orders)
                else:
                    orders_by_power[italy_power_name] = []
                    game_history.add_orders(current_phase_name, italy_power_name, [])
            elif (
                italy_power_name not in orders_by_power
            ):  # Has agent, but no orders yet (e.g. bloc failed to return for it)
                logger.warning(
                    f"Power {italy_power_name} has an agent ({agent_id_for_italy}) but no orders were recorded. Defaulting to empty list."
                )
                orders_by_power[italy_power_name] = []
                game_history.add_orders(current_phase_name, italy_power_name, [])

        return orders_by_power
