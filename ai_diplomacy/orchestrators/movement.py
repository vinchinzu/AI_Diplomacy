"""
Handles the strategy for the Movement phase of a Diplomacy game.

This module defines the MovementPhaseStrategy class, which is responsible for
managing diplomatic negotiations and collecting movement orders from each agent.
"""
import logging
import asyncio
from typing import Dict, List, TYPE_CHECKING, Set

# Import the new negotiation function
from .negotiation import perform_negotiation_rounds
from ..agents.bloc_llm_agent import BlocLLMAgent
from ..core.state import PhaseState

if TYPE_CHECKING:
    from diplomacy import Game
    from ..game_history import GameHistory
    from .phase_orchestrator import PhaseOrchestrator # Import PhaseOrchestrator for type hinting

logger = logging.getLogger(__name__)

__all__ = ["MovementPhaseStrategy"]

class MovementPhaseStrategy:
    async def get_orders(
        self, game: "Game", orchestrator: "PhaseOrchestrator", game_history: "GameHistory"
    ) -> Dict[str, List[str]]:
        # Docstring already exists and is good.
        logger.info("Executing Movement Phase actions via MovementPhaseStrategy...")
        current_phase_name = game.get_current_phase()

        # Call the standalone negotiation function
        await perform_negotiation_rounds(
            game,
            game_history,
            orchestrator.agent_manager,
            orchestrator.active_powers,
            orchestrator.config
        )

        orders_by_power: Dict[str, List[str]] = {}
        processed_bloc_agent_ids: Set[str] = set()
        current_phase_state = PhaseState.from_game(game)

        for power_name in orchestrator.active_powers:
            agent = orchestrator.agent_manager.get_agent(power_name)
            if agent:
                if isinstance(agent, BlocLLMAgent):
                    if agent.agent_id in processed_bloc_agent_ids:
                        logger.debug(f"Skipping already processed bloc agent {agent.agent_id} for power {power_name}")
                        continue
                    else:
                        logger.debug(f"Processing BlocLLMAgent {agent.agent_id} for {power_name} (Movement)...")
                        try:
                            await agent.decide_orders(current_phase_state)
                            current_phase_key_for_bloc = (
                                current_phase_state.state,
                                current_phase_state.scs,
                                current_phase_state.year,
                                current_phase_state.season,
                                current_phase_state.name,
                            )
                            all_bloc_orders_obj = agent.get_all_bloc_orders_for_phase(current_phase_key_for_bloc)
                            for bloc_power_name, order_obj_list in all_bloc_orders_obj.items():
                                orders_str_list = [str(o) for o in order_obj_list]
                                orders_by_power[bloc_power_name] = orders_str_list
                                game_history.add_orders(current_phase_name, bloc_power_name, orders_str_list)
                                logger.debug(f"✅ {bloc_power_name} (Bloc): Generated {len(orders_str_list)} orders (Movement)")
                            processed_bloc_agent_ids.add(agent.agent_id)
                        except Exception as e:
                            logger.error(
                                f"❌ Error getting orders for bloc agent {agent.agent_id}, power {power_name} (Movement): {e}", exc_info=e
                            )
                            # Decide how to handle errors for bloc members, potentially mark all as empty
                            for bloc_member_power in agent.get_bloc_member_powers():
                                if bloc_member_power not in orders_by_power: # Don't overwrite if another power in the bloc succeeded
                                    orders_by_power[bloc_member_power] = []
                else: # Not a BlocLLMAgent
                    logger.debug(f"Generating orders for {power_name} (Movement)...")
                    try:
                        # _get_orders_for_power is a helper on the orchestrator
                        orders = await orchestrator._get_orders_for_power(
                            game, power_name, agent, game_history
                        )
                        orders_by_power[power_name] = orders
                        game_history.add_orders(current_phase_name, power_name, orders)
                        logger.debug(f"✅ {power_name}: Generated {len(orders)} orders (Movement)")
                    except Exception as e:
                        logger.error(
                            f"❌ Error getting orders for {power_name} (Movement): {e}", exc_info=e
                        )
                        orders_by_power[power_name] = []
            else:
                logger.warning(
                    f"No agent found for active power {power_name} during movement order generation."
                )
                orders_by_power[power_name] = []
            # Removed the common game_history.add_orders call from here, as it's now handled within conditionals

        # Handle Neutral Italy specifically - if it exists in game but not as an active LLM power
        # This is a simplified approach for the WWI test scenario.
        # A more robust solution would involve agent types (e.g., NeutralAgent).
        #TODO
        italy_power_name = "ITALY" # Standard name
        if italy_power_name in game.powers and italy_power_name not in orchestrator.active_powers:
            italy_units = game.get_units(italy_power_name)
            if italy_units:
                hold_orders = [f"{unit_name} H" for unit_name in italy_units]
                orders_by_power[italy_power_name] = hold_orders
                logger.info(f"Generated Hold orders for neutral {italy_power_name}: {hold_orders}")
                game_history.add_orders(current_phase_name, italy_power_name, hold_orders)
            else:
                orders_by_power[italy_power_name] = [] # No units, no orders
                game_history.add_orders(current_phase_name, italy_power_name, [])

        return orders_by_power 