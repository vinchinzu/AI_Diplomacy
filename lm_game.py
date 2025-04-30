import argparse
import logging
import time
import dotenv
import os
import json
from collections import defaultdict
import concurrent.futures

# Suppress Gemini/PaLM gRPC warnings
os.environ["GRPC_PYTHON_LOG_LEVEL"] = "40"  # ERROR level only

from diplomacy import Game
from diplomacy.engine.message import GLOBAL, Message
from diplomacy.utils.export import to_saved_game_format

from ai_diplomacy.clients import load_model_client
from ai_diplomacy.utils import (
    get_valid_orders,
    gather_possible_orders,
    assign_models_to_powers,
)
from ai_diplomacy.negotiations import conduct_negotiations
from ai_diplomacy.planning import planning_phase
from ai_diplomacy.game_history import GameHistory
from ai_diplomacy.agent import DiplomacyAgent

dotenv.load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)
# Silence noisy dependencies
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("root").setLevel(logging.WARNING) # Assuming root handles AFC


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Run a Diplomacy game simulation with configurable parameters."
    )
    parser.add_argument(
        "--max_year",
        type=int,
        default=1901,
        help="Maximum year to simulate. The game will stop once this year is reached.",
    )
    parser.add_argument(
        "--num_negotiation_rounds",
        type=int,
        default=0,
        help="Number of negotiation rounds per phase.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Output filename for the final JSON result. If not provided, a timestamped name will be generated.",
    )
    parser.add_argument(
        "--models",
        type=str,
        default="",
        help=(
            "Comma-separated list of model names to assign to powers in order. "
            "The order is: AUSTRIA, ENGLAND, FRANCE, GERMANY, ITALY, RUSSIA, TURKEY."
        ),
    )
    parser.add_argument(
        "--planning_phase", 
        action="store_true",
        help="Enable the planning phase for each power to set strategic directives.",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()
    max_year = args.max_year

    logger.info(
        "Starting a new Diplomacy game for testing with multiple LLMs, now concurrent!"
    )
    start_whole = time.time()

    model_error_stats = defaultdict(
        lambda: {"conversation_errors": 0, "order_decoding_errors": 0}
    )

    # Create a fresh Diplomacy game
    game = Game()
    game_history = GameHistory()

    # Ensure game has phase_summaries attribute
    if not hasattr(game, "phase_summaries"):
        game.phase_summaries = {}

    # Determine the result folder based on a timestamp
    timestamp_str = time.strftime("%Y%m%d_%H%M%S")
    result_folder = f"./results/{timestamp_str}"
    os.makedirs(result_folder, exist_ok=True)

    # File paths
    manifesto_path = f"{result_folder}/game_manifesto.txt"
    # Use provided output filename or generate one based on the timestamp
    game_file_path = args.output if args.output else f"{result_folder}/lmvsgame.json"
    overview_file_path = f"{result_folder}/overview.jsonl"

    # Handle power model mapping
    if args.models:
        # Expected order: AUSTRIA, ENGLAND, FRANCE, GERMANY, ITALY, RUSSIA, TURKEY
        powers_order = [
            "AUSTRIA",
            "ENGLAND",
            "FRANCE",
            "GERMANY",
            "ITALY",
            "RUSSIA",
            "TURKEY",
        ]
        provided_models = [name.strip() for name in args.models.split(",")]
        if len(provided_models) != len(powers_order):
            logger.error(
                f"Expected {len(powers_order)} models for --power-models but got {len(provided_models)}. Exiting."
            )
            return
        game.power_model_map = dict(zip(powers_order, provided_models))
    else:
        game.power_model_map = assign_models_to_powers()

    # == Goal 1: Centralize Agent Instances ==
    agents = {}
    logger.info("Initializing Diplomacy Agents for each power...")
    for power_name, model_id in game.power_model_map.items():
        if not game.powers[power_name].is_eliminated(): # Only create for active powers initially
            try:
                client = load_model_client(model_id)
                # TODO: Potentially load initial goals/relationships from config later
                agent = DiplomacyAgent(power_name=power_name, client=client) 
                agents[power_name] = agent
                logger.info(f"Initialized agent for {power_name} with model {model_id}")
                # == Add call to initialize agent state using LLM ==
                try:
                    agents[power_name].initialize_agent_state(game, game_history)
                except Exception as e:
                     logger.error(f"Failed to initialize agent state for {power_name}: {e}", exc_info=True)
                     # Decide if we should continue without initialized state or exit? For now, continue.
            except Exception as e:
                logger.error(f"Failed to initialize agent for {power_name} with model {model_id}: {e}")
        else:
             logger.info(f"Skipping agent initialization for eliminated power: {power_name}")
    # =======================================

    while not game.is_game_done:
        phase_start = time.time()
        current_phase = game.get_current_phase()

        # Ensure the current phase is registered in the history
        game_history.add_phase(current_phase)
        
        # Store the current phase's short name once for consistent use
        current_short_phase = game.current_short_phase
        
        logger.info(
            f"PHASE: {current_phase} (time so far: {phase_start - start_whole:.2f}s)"
        )

        # DEBUG: Print the short phase to confirm
        logger.debug(f"DEBUG: current_short_phase is '{current_short_phase}'")

        # Prevent unbounded simulation based on year
        year_str = current_phase[1:5]
        year_int = int(year_str)
        if year_int > max_year:
            logger.info(f"Reached year {year_int}, stopping the test game early.")
            break

        # If it's a movement phase (e.g. ends with "M"), conduct negotiations
        if game.current_short_phase.endswith("M"):
            
            if args.planning_phase:
                logger.debug("Starting planning phase block...")
                game_history = planning_phase(
                    game,
                    agents, # Pass agents dict
                    game_history,
                    model_error_stats,
                )
            logger.debug("Starting negotiation phase block...")
            game_history = conduct_negotiations(
                game,
                agents, # Pass agents dict
                game_history,
                model_error_stats,
                max_rounds=args.num_negotiation_rounds,
            )

        # Gather orders from each power concurrently
        active_powers = [
            (p_name, p_obj)
            for p_name, p_obj in game.powers.items()
            if not p_obj.is_eliminated()
        ]

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(active_powers)
        ) as executor:
            futures = {}
            for power_name, _ in active_powers:
                # model_id = game.power_model_map.get(power_name, "o3-mini") # Client now managed by agent
                # client = load_model_client(model_id) # Client now managed by agent
                
                # == Goal 2: Inject Agent State into Order Generation ==
                if power_name not in agents:
                     logger.warning(f"Agent not found for active power {power_name}. Skipping order generation.")
                     continue
                agent = agents[power_name]
                client = agent.client # Use the agent's client
                # ======================================================

                possible_orders = gather_possible_orders(game, power_name)
                if not possible_orders:
                    logger.debug(f"No orderable locations for {power_name}; skipping order generation.")
                    continue
                board_state = game.get_state()

                future = executor.submit(
                    get_valid_orders,
                    game,
                    client,
                    board_state,
                    power_name,
                    possible_orders,
                    game_history,  # Pass game_history object
                    model_error_stats,
                    # == Goal 2: Inject Agent State into Order Generation ==
                    agent_goals=agent.goals,
                    agent_relationships=agent.relationships,
                    # ======================================================
                )
                futures[future] = power_name
                logger.debug(f"Submitted get_valid_orders task for {power_name}.")

            for future in concurrent.futures.as_completed(futures):
                p_name = futures[future]
                try:
                    orders = future.result()
                    logger.debug(f"Validated orders for {p_name}: {orders}")
                    if orders:
                        game.set_orders(p_name, orders)
                        logger.debug(
                            f"Set orders for {p_name} in {game.current_short_phase}: {orders}"
                        )
                    else:
                        logger.debug(f"No valid orders returned for {p_name}.")
                except Exception as exc:
                    logger.error(f"LLM request failed for {p_name}: {exc}")

        # Process orders
        logger.info(f"Processing orders for {current_phase}...")
        
        # Process with a custom summary callback that captures our custom game_history data
        def phase_summary_callback(system_prompt, user_prompt):
            # This will be called by the game engine's _generate_phase_summary method
            # Get messages for this phase from game_history
            current_phase_obj = None
            for phase in game_history.phases:
                if phase.name == current_short_phase:
                    current_phase_obj = phase
                    break
                
            if not current_phase_obj:
                return f"Phase {current_short_phase} Summary: (No game history data available)"
            
            # 1) Gather the current board state, sorted by # of centers
            power_info = []
            for power_name, power in game.powers.items():
                units_list = list(power.units)
                centers_list = list(power.centers)
                power_info.append(
                    (power_name, len(centers_list), units_list, centers_list)
                )
            # Sort by descending # of centers
            power_info.sort(key=lambda x: x[1], reverse=True)

            # 2) Build text lines for the top "Board State Overview"
            top_lines = ["Current Board State (Ordered by SC Count):"]
            for (p_name, sc_count, units, centers) in power_info:
                top_lines.append(
                    f" • {p_name}: {sc_count} centers (needs 18 to win). "
                    f"Units={units} Centers={centers}"
                )

            # 3) Map orders to "successful", "failed", or "other" outcomes
            success_dict = {}
            fail_dict = {}
            other_dict = {}

            orders_dict = game.order_history.get(current_short_phase, {})
            results_for_phase = game.result_history.get(current_short_phase, {})

            for pwr, pwr_orders in orders_dict.items():
                for order_str in pwr_orders:
                    # Extract the unit from the string
                    tokens = order_str.split()
                    if len(tokens) < 3:
                        # Something malformed
                        other_dict.setdefault(pwr, []).append(order_str)
                        continue
                    unit_name = " ".join(tokens[:2])
                    # We retrieve the order results for that unit
                    results_list = results_for_phase.get(unit_name, [])
                    # Check if the results contain e.g. "dislodged", "bounce", "void"
                    # We consider success if the result list is empty or has no negative results
                    if not results_list or all(res not in ["bounce", "void", "no convoy", "cut", "dislodged", "disrupted"] for res in results_list):
                        success_dict.setdefault(pwr, []).append(order_str)
                    elif any(res in ["bounce", "void", "no convoy", "cut", "dislodged", "disrupted"] for res in results_list):
                        fail_dict.setdefault(pwr, []).append(f"{order_str} - {', '.join(str(r) for r in results_list)}")
                    else:
                        other_dict.setdefault(pwr, []).append(order_str)

            # 4) Build textual lists of successful, failed, and "other" moves
            def format_moves_dict(title, moves_dict):
                lines = [title]
                if not moves_dict:
                    lines.append("  None.")
                    return "\n".join(lines)
                for pwr in sorted(moves_dict.keys()):
                    lines.append(f"  {pwr}:")
                    for mv in moves_dict[pwr]:
                        lines.append(f"    {mv}")
                return "\n".join(lines)

            success_section = format_moves_dict("Successful Moves:", success_dict)
            fail_section = format_moves_dict("Unsuccessful Moves:", fail_dict)
            other_section = format_moves_dict("Other / Unclassified Moves:", other_dict)

            # 5) Combine everything into the final summary text
            summary_parts = []
            summary_parts.append("\n".join(top_lines))
            summary_parts.append("\n" + success_section)
            summary_parts.append("\n" + fail_section)
            
            # Only include "Other" section if it has content
            if other_dict:
                summary_parts.append("\n" + other_section)

            return f"Phase {current_short_phase} Summary:\n\n" + "\n".join(summary_parts)
        
        # Process with our custom callback
        game.process(phase_summary_callback=phase_summary_callback)

        # Log the results
        logger.info(f"Results for {current_phase}:")
        for power_name, power in game.powers.items():
            logger.info(f"{power_name}: {power.centers}")

        # Ensure messages from game_history are added to the game's message system
        # This is required for messages to appear in the Messages tab
        for phase in game_history.phases:
            if phase.name == current_short_phase:
                for msg in phase.messages:
                    try:
                        # Only add if not already present (avoid duplicates)
                        if not any(m.sender == msg.sender and 
                                  m.recipient == msg.recipient and 
                                  m.message == msg.content 
                                  for m in game.messages.values()):
                            game.add_message(Message(
                                phase=current_short_phase,
                                sender=msg.sender,
                                recipient=msg.recipient,
                                message=msg.content,
                                time_sent=int(time.time())
                            ))
                    except Exception as e:
                        logger.warning(f"Could not add message to game: {e}")

        # Add orders to game history
        for power_name in game.order_history[current_short_phase]:
            orders = game.order_history[current_short_phase][power_name]
            results = []
            for order in orders:
                # Example move: "A PAR H" -> unit="A PAR", order_part="H"
                tokens = order.split(" ", 2)
                if len(tokens) < 3:
                    continue
                unit = " ".join(tokens[:2])  # e.g. "A PAR"
                order_part = tokens[2]  # e.g. "H" or "S A MAR"
                results.append(
                    [str(x) for x in game.result_history[current_short_phase][unit]]
                )
            game_history.add_orders(
                current_short_phase,
                power_name,
                game.order_history[current_short_phase][power_name],
            )

        logger.info(f"--- Orders Submitted for {current_phase} ---")
        for power, orders in game.order_history.get(current_short_phase, {}).items():
            order_str = ", ".join(orders) if orders else "(No orders/NOP)"
            logger.info(f"  {power:<8}: {order_str}")
        logger.info("-----------------------------------")

        # == Goal 3: Implement LLM-Powered State Update ==
        # Analyze the results of the phase that just completed
        completed_phase_name = current_phase # The phase name BEFORE processing
        logger.info(f"Starting state update analysis for completed phase {completed_phase_name}...")
        
        # Ensure phase summary exists (it should be generated by the callback during game.process)
        phase_summary = game.phase_summaries.get(completed_phase_name, f"Summary for {completed_phase_name} not found.")
        if f"Summary for {completed_phase_name} not found" in phase_summary:
             logger.warning(phase_summary)

        current_board_state = game.get_state() # State *after* processing

        # Update state concurrently for active agents
        active_agent_powers = [p for p in active_powers if p[0] in agents] # Filter for powers with active agents

        if active_agent_powers: # Only run if there are agents to update
             logger.info(f"Beginning concurrent state analysis for {len(active_agent_powers)} agents...")
             with concurrent.futures.ThreadPoolExecutor(max_workers=len(active_agent_powers)) as executor:
                  analysis_futures = {}
                  for power_name, _ in active_agent_powers:
                       agent = agents[power_name]
                       logger.debug(f"Submitting state analysis task for {power_name}")
                       # Submit the analysis task - assumes analyze_phase_and_update_state exists in DiplomacyAgent
                       future = executor.submit(
                            agent.analyze_phase_and_update_state,
                            game, 
                            current_board_state,
                            phase_summary, 
                            game_history
                       )
                       analysis_futures[future] = power_name
                  
                  # Wait for analyses to complete and log any errors
                  for future in concurrent.futures.as_completed(analysis_futures):
                      power_name = analysis_futures[future]
                      try:
                          future.result() # Check for exceptions during analysis
                          logger.debug(f"State analysis completed successfully for {power_name}.")
                      except Exception as e:
                          logger.error(f"Error during state analysis for {power_name}: {e}")

             logger.info(f"Finished concurrent state analysis for {len(active_agent_powers)} agents.")
             logger.info(f"Completed state update analysis for phase {completed_phase_name}.")
        else:
             logger.info(f"No active agents found to perform state update analysis for phase {completed_phase_name}.")
        # ===============================================

        # Append the strategic directives to the manifesto file
        strategic_directives = game_history.get_strategic_directives()
        if strategic_directives:
            out_str = f"Strategic directives for {current_phase}:\n"
            for power, directive in strategic_directives.items():
                out_str += f"{power}: {directive}\n\n"
            out_str += f"------------------------------------------\n"
            with open(manifesto_path, "a") as f:
                f.write(out_str)

        # Check if we've exceeded the max year
        year_str = current_phase[1:5]
        year_int = int(year_str)
        if year_int > max_year:
            logger.info(f"Reached year {year_int}, stopping the test game early.")
            break

    # Game is done
    total_time = time.time() - start_whole
    logger.info(f"Game ended after {total_time:.2f}s. Saving results...")

    # Now save the game with our added data
    output_path = game_file_path
    # If the file already exists, append a timestamp to the filename
    if os.path.exists(output_path):
        logger.info("Game file already exists, saving with unique filename.")
        timestamp = int(time.time())
        base, ext = os.path.splitext(output_path)
        output_path = f"{base}_{timestamp}{ext}"

    # Generate the saved game JSON using the standard export function
    saved_game = to_saved_game_format(game)
    
    # Verify phase_summaries are available in game.phase_summaries
    logger.info(f"Game has {len(game.phase_summaries)} phase summaries: {list(game.phase_summaries.keys())}")

    # CRITICAL: Add phase_summaries as a top-level property in the saved game
    # The frontend expects this exact structure
    saved_game['phase_summaries'] = game.phase_summaries
    logger.info(f"Added phase_summaries to saved game with {len(game.phase_summaries)} phases")

    # Also add summaries to individual phases for backward compatibility
    summary_phases_count = 0
    for i, phase in enumerate(saved_game['phases']):
        phase_name = phase['name']
        if phase_name in game.phase_summaries:
            saved_game['phases'][i]['summary'] = game.phase_summaries[phase_name]
            summary_phases_count += 1
            logger.debug(f"Added summary to phase {phase_name} in export")
    logger.info(f"Added summaries to {summary_phases_count}/{len(saved_game['phases'])} phases in the export")

    # Save the modified game data
    logger.info(f"Saving game to {output_path}...")
    with open(output_path, "w") as f:
        json.dump(saved_game, f, indent=4)

    # Dump error stats and power model mapping to the overview file
    with open(overview_file_path, "w") as overview_file:
        overview_file.write(json.dumps(model_error_stats) + "\n")
        overview_file.write(json.dumps(game.power_model_map) + "\n")
        overview_file.write(json.dumps(vars(args)) + "\n")

    logger.info(f"Saved game data, manifesto, and error stats in: {result_folder}")
    logger.info("Done.")


if __name__ == "__main__":
    main()
