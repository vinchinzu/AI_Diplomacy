import argparse
import asyncio
import logging
import os
import time
from dotenv import load_dotenv

from diplomacy.client.connection import connect
# It's good practice to ensure ai_diplomacy is in PYTHONPATH or installed
# For now, assuming it's discoverable
from ai_diplomacy.game_history import GameHistory
from ai_diplomacy.agent import DiplomacyAgent
# load_model_client is obsolete and removed.
# from ai_diplomacy.clients import load_model_client
from ai_diplomacy.utils import (
    get_valid_orders, 
    gather_possible_orders, 
    initialize_agent_state_ext,
    # Wrapper functions for agent actions, may need adjustment for network game
    # conduct_negotiations_phase, # Renamed from conduct_negotiations to avoid conflict with a local var
    # planning_phase_action, # Renamed from planning_phase
)
# Placeholder for negotiation and planning functions - will import specific ones later if needed
# from ai_diplomacy.negotiation import conduct_negotiations 
# from ai_diplomacy.planning import planning_phase 


# Basic logging setup (will be refined in main function)
logger = logging.getLogger("NetworkLMAgent")
logger.setLevel(logging.INFO)
# console_handler = logging.StreamHandler()
# console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
# logger.addHandler(console_handler)

def parse_arguments():
    parser = argparse.ArgumentParser(description="Diplomacy Network LM Agent")
    parser.add_argument("--host", type=str, default="localhost", help="Hostname/IP of the central game server")
    parser.add_argument("--port", type=int, default=8432, help="Port of the central game server")
    parser.add_argument("--game_id", type=str, required=True, help="ID of the game to join")
    parser.add_argument("--power_name", type=str, required=True, help="Name of the power this agent will control (e.g., FRANCE)")
    parser.add_argument("--model_id", type=str, required=True, help="llm-compatible model ID for this agent's LLM (e.g., ollama/llama3, gpt-4o)")
    # --ollama_base_url is now obsolete.
    parser.add_argument("--num_negotiation_rounds", type=int, default=3, help="Number of negotiation rounds per movement phase.")
    parser.add_argument("--perform_planning_phase", action="store_true", help="Enable the planning phase action.")
    parser.add_argument("--log_dir", type=str, default=None, help="Directory to save logs. Default: ./logs/network_agent_POWER_NAME_GAME_ID")
    
    args = parser.parse_args()

    # Construct specific log_dir based on power_name and game_id if not provided
    if args.log_dir is None:
        args.log_dir = f"./logs/network_agent_{args.power_name.upper()}_{args.game_id}"
    
    os.makedirs(args.log_dir, exist_ok=True)

    return args

async def play_network_game(args):
    # Load environment variables
    load_dotenv()

    # Setup logging paths using the potentially modified args.log_dir
    general_log_file_path = os.path.join(args.log_dir, f"{args.power_name.upper()}_general.log")
    llm_log_file_path = os.path.join(args.log_dir, f"{args.power_name.upper()}_llm_interactions.csv")

    # Clear existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # File handler for general logs
    file_handler = logging.FileHandler(general_log_file_path)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)

    # Console handler (optional, but good for seeing live activity)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)
    
    logger.info(f"Logging general activity to: {general_log_file_path}")
    logger.info(f"Logging LLM interactions to: {llm_log_file_path}")
    logger.info(f"Parsed arguments: {args}")


    # Establish connection to the server
    try:
        logger.info(f"Attempting to connect to server at {args.host}:{args.port}")
        connection = await connect(args.host, args.port)
        logger.info("Successfully connected to server.")
    except Exception as e:
        logger.error(f"Failed to connect to server: {e}")
        return

    # Authenticate
    try:
        # Using a generic username/password for now, as specified
        username = f"agent_{args.power_name.lower()}"
        password = "password" # Consider making this configurable if security is a concern
        logger.info(f"Attempting to authenticate as user: {username}")
        channel = await connection.authenticate(username, password)
        logger.info(f"Successfully authenticated as {username}.")
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        await connection.close()
        return

    # Wait for and join the game
    game = None
    while not game:
        try:
            found_games = await channel.list_games(game_id=args.game_id)
            if found_games:
                logger.info(f"Game {args.game_id} found. Attempting to join as {args.power_name}.")
                game = await channel.join_game(game_id=args.game_id, power_name=args.power_name)
                logger.info(f"Successfully joined game {args.game_id} as {args.power_name}. Current phase: {game.get_current_phase()}")
            else:
                logger.info(f"Game {args.game_id} not found. Waiting 5 seconds...")
                await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Error finding or joining game {args.game_id}: {e}. Retrying in 10 seconds...")
            await asyncio.sleep(10)
            # Attempt to reconnect if connection might have dropped
            if connection.is_closed():
                logger.info("Connection was closed. Reconnecting...")
                try:
                    connection = await connect(args.host, args.port)
                    channel = await connection.authenticate(username, password)
                    logger.info("Reconnected and re-authenticated.")
                except Exception as recon_e:
                    logger.error(f"Failed to reconnect: {recon_e}. Exiting.")
                    return


    # Initialize GameHistory and DiplomacyAgent
    game_history = GameHistory(log_dir=args.log_dir, power_name_filter=args.power_name) # Log dir for game history specific files

    # client_params and llm_client loading are now obsolete.
    # The model_id (args.model_id) will be used directly or with llm.get_model().
    # Configuration for endpoints (like ollama_base_url) should be handled by `llm` library's environment variables or config.
    # For example, OLLAMA_HOST for llm-ollama plugin.
    
    try:
        # agent = DiplomacyAgent(power_name=args.power_name, client=llm_client) # OLD WAY
        # As in lm_game.py, DiplomacyAgent will be adapted to take model_id.
        agent = DiplomacyAgent(power_name=args.power_name, model_id=args.model_id)
        logger.info(f"DiplomacyAgent initialized for {args.power_name} with model_id: {args.model_id}.")
    except Exception as e:
        logger.error(f"Failed to initialize DiplomacyAgent for {args.power_name} with model_id {args.model_id}: {e}", exc_info=True)
        await connection.close()
        return

    # Initialize agent state (goals, relationships, etc.)
    # This function needs to be compatible with NetworkGame or adapted.
    # Assuming it is, or will be made so.
    try:
        await initialize_agent_state_ext(
            agent=agent, 
            game=game, 
            game_history=game_history, 
            llm_log_file_path=llm_log_file_path,
            # log_dir=args.log_dir # If initialize_agent_state_ext needs it for other logs
        )
        logger.info(f"Agent state initialized for {args.power_name}.")
    except Exception as e:
        logger.error(f"Error initializing agent state: {e}", exc_info=True)
        # Decide if to proceed or exit
        # For now, let's try to proceed, but this could be critical

    logger.info("Starting game loop...")
    
    # Callback for game processed notifications (optional, for now relying on polling phase)
    # async def on_game_processed_callback(game_obj):
    #     logger.info(f"Notification: Game has processed. Current phase: {game_obj.get_current_phase()}")
    # game.add_on_game_processed(on_game_processed_callback)

    last_processed_phase_for_agent_updates = None # Tracks phases for which agent post-processing has been done

    while not game.is_game_done:
        current_phase_fullname = game.get_current_phase()
        phase_type = game.get_phase_type() # 'M', 'R', 'B', 'A', 'S' (Spring, Fall, Retreat, Build, Adjust)
        year = game.get_year()

        logger.info(f"Current game phase: {current_phase_fullname} ({phase_type}{year}) for {args.power_name}")

        # --- Update Game History with new messages ---
        # NetworkGame's .messages property should be updated by the client library
        # GameHistory needs a way to ingest these.
        # Assuming game.messages is a list of message dicts {sender, recipient, message, phase, time_sent (optional)}
        # This part needs to be robust based on how NetworkGame actually stores/provides messages.
        try:
            # Option 1: If game_history has a method to sync from game object
            # game_history.update_from_game_object(game) 
            
            # Option 2: Manual processing (more explicit for now)
            # We need to get messages that game_history hasn't seen yet.
            # For simplicity, let's assume game.messages contains all messages *for the current game state*.
            # GameHistory should ideally handle duplicates or only add new ones.
            
            # A more robust way: game_history.add_messages_from_list(game.messages)
            # where add_messages_from_list checks for duplicates before adding.
            # For now, let's assume GameHistory's add_message is idempotent or handles this.
            
            # Get all messages from the game object (which should be updated by the network client)
            # The format of messages in game.messages needs to be compatible with game_history.add_message
            server_messages = game.messages 
            if isinstance(server_messages, dict): # If messages are stored by phase
                current_phase_messages = server_messages.get(current_phase_fullname, [])
                # Also consider messages from the general phase if current is specific (e.g., S1901M_NEGOTIATE)
                base_phase = current_phase_fullname.split('_')[0]
                if base_phase != current_phase_fullname:
                    current_phase_messages.extend(server_messages.get(base_phase, []))
            elif isinstance(server_messages, list):
                current_phase_messages = server_messages
            else:
                current_phase_messages = []
            
            messages_added_this_cycle = 0
            for msg_dict in current_phase_messages:
                # Adapt msg_dict to what game_history.add_message expects if necessary
                # Expected: sender, recipient, message, phase, time_sent (optional)
                # Example: if msg_dict is from diplomacy.message.Message object
                # game_history.add_message(msg_dict.sender, msg_dict.recipient, msg_dict.message, msg_dict.phase)
                # If it's already a dict:
                was_added = game_history.add_message(
                    sender=msg_dict.get('sender'),
                    recipient=msg_dict.get('recipient'),
                    message=msg_dict.get('message'), # or 'content'
                    phase=msg_dict.get('phase', current_phase_fullname) 
                )
                if was_added:
                    messages_added_this_cycle +=1
            if messages_added_this_cycle > 0:
                logger.info(f"Added {messages_added_this_cycle} new messages to game history from server state.")

        except AttributeError:
            logger.warning("game.messages attribute not found or not in expected format. Message history might be incomplete.")
        except Exception as e:
            logger.error(f"Error updating game history with messages: {e}", exc_info=True)

        # --- Phase-Specific Actions ---
        
        # Check if it's our turn to submit orders or negotiate
        # Some servers might use specific phase suffixes like _NEGOTIATE or _ORDERS
        # For now, assume standard phase types determine actions.

        if phase_type == 'M' and args.num_negotiation_rounds > 0:
            logger.info(f"Entering negotiation for movement phase {current_phase_fullname}")
            try:
                # The conduct_negotiations function from lm_game.py might be too complex
                # as it iterates rounds. Here, we assume server handles rounds, or we do one burst.
                # We'll call agent.generate_negotiation_messages directly.
                
                active_powers = [p for p in game.powers if not game.powers[p].is_eliminated()]

                negotiation_messages = await agent.generate_negotiation_messages(
                    game=game, # NetworkGame object
                    game_history=game_history,
                    active_powers=active_powers,
                    current_phase=current_phase_fullname,
                    log_file_path=llm_log_file_path
                )
                
                if negotiation_messages:
                    logger.info(f"Generated {len(negotiation_messages)} negotiation messages.")
                    for msg_data in negotiation_messages:
                        recipient_power = msg_data.get('recipient')
                        msg_type = msg_data.get('message_type', 'private').lower()
                        
                        if msg_type == 'broadcast':
                            recipient_power = "ALL" # Standard for broadcast
                        elif not recipient_power:
                            logger.warning(f"Skipping message due to missing recipient for non-broadcast: {msg_data}")
                            continue

                        logger.info(f"Sending message to {recipient_power} ({msg_type}): {msg_data.get('content')[:50]}...")
                        await game.send_game_message(
                            recipient=recipient_power,
                            message=msg_data.get('content') 
                        )
                        # Add our own sent messages to game_history immediately
                        game_history.add_message(
                            sender=args.power_name,
                            recipient=recipient_power,
                            message=msg_data.get('content'),
                            phase=current_phase_fullname
                        )
                    logger.info("Finished sending negotiation messages.")
                else:
                    logger.info("No negotiation messages generated.")

                await agent.generate_negotiation_diary_entry(
                    game=game, 
                    game_history=game_history, 
                    current_phase=current_phase_fullname,
                    log_file_path=llm_log_file_path
                )
                logger.info("Negotiation diary entry generated.")

            except Exception as e:
                logger.error(f"Error during negotiation actions for {current_phase_fullname}: {e}", exc_info=True)

        if args.perform_planning_phase and phase_type == 'M': # Typically before movement orders
            logger.info(f"Performing planning phase for {current_phase_fullname}")
            try:
                # This calls agent.generate_plan internally
                current_plan = await agent.generate_plan( # generate_plan is an async method of DiplomacyAgent
                    game=game,
                    game_history=game_history,
                    log_file_path=llm_log_file_path
                )
                logger.info(f"Planning phase completed. Current plan (summary): {current_plan[:100]}...")
            except Exception as e:
                logger.error(f"Error during planning phase for {current_phase_fullname}: {e}", exc_info=True)

        # Order Generation (for M, R, B phases)
        if phase_type in ['M', 'R', 'B']:
            # Check if orders are already set for this power in this phase
            # game.get_orders(power_name) might return None or submitted orders
            power_orders_status = game.get_orders(args.power_name)
            if power_orders_status is not None and power_orders_status != []: # Assuming [] means no orders submitted yet, None could also mean that.
                                                                            # Some servers might return a specific "submitted" status.
                logger.info(f"Orders for {args.power_name} already submitted for {current_phase_fullname}. Skipping order generation.")
            else:
                logger.info(f"Generating orders for {current_phase_fullname}")
                try:
                    possible_orders_dict = gather_possible_orders(game, args.power_name)
                    board_state = game.get_state() # Get current board state from NetworkGame
                    model_error_stats = {} # Placeholder for error tracking

                    orders = await get_valid_orders( # This is from ai_diplomacy.utils
                        game=game,
                        board_state=board_state,
                        power_name=args.power_name,
                        possible_orders=possible_orders_dict,
                        model_id=agent.model_id, # Pass model_id
                        agent_system_prompt=agent.system_prompt, # Pass agent's system_prompt
                        game_history=game_history,
                        model_error_stats=model_error_stats, # This will likely need adjustment for model_id keys
                        log_file_path=llm_log_file_path,
                        phase=current_phase_fullname,
                        agent_goals=agent.goals,
                        agent_relationships=agent.relationships,
                        agent_private_diary_str=agent.format_private_diary_for_prompt()
                    )

                    if orders:
                        logger.info(f"Generated orders: {orders}")
                        await game.set_orders(power_name=args.power_name, orders=orders, wait=False)
                        logger.info(f"Orders submitted for {args.power_name} in {current_phase_fullname}.")
                        
                        await agent.generate_order_diary_entry(
                            game=game,
                            current_phase=current_phase_fullname,
                            orders=orders,
                            log_file_path=llm_log_file_path
                        )
                        logger.info("Order diary entry generated.")
                    else:
                        logger.warning(f"No valid orders generated for {args.power_name}. Submitting empty set (server should default to HOLDS).")
                        await game.set_orders(power_name=args.power_name, orders=[], wait=False)

                except Exception as e:
                    logger.error(f"Error during order generation for {current_phase_fullname}: {e}", exc_info=True)
        
        # --- Waiting for the current phase to complete and a new one to start ---
        logger.info(f"Actions for {current_phase_fullname} submitted/skipped. Waiting for phase to advance...")
        
        phase_before_wait = game.get_current_phase() 
        
        while phase_before_wait == game.get_current_phase() and not game.is_game_done:
            await asyncio.sleep(1) # Poll for phase change. Server notifications might make this more efficient.
                                   # Increased from 0.1 to 1 to reduce polling frequency slightly.

        if game.is_game_done:
            logger.info("Game is done. Exiting main loop.")
            break
        
        new_phase_fullname = game.get_current_phase()
        logger.info(f"Phase changed from {phase_before_wait} to {new_phase_fullname}")

        # --- Post-Processing for the phase that just ended (phase_before_wait) ---
        # This is where we analyze results and update long-term agent state
        if last_processed_phase_for_agent_updates != phase_before_wait:
            logger.info(f"Performing post-processing and agent updates for just-ended phase: {phase_before_wait}")
            try:
                # Update game_history with any orders/results from the completed phase if not done by messages
                # game.get_all_orders() or game.phase_orders might give this.
                # GameHistory might need an explicit method game_history.add_orders_from_phase(game, phase_before_wait)
                
                # For example, if game.phase_orders[phase_before_wait] exists:
                if hasattr(game, 'phase_orders') and phase_before_wait in game.phase_orders:
                    phase_order_data = game.phase_orders[phase_before_wait]
                    # game_history.add_orders(phase_order_data, phase_before_wait) # Assuming such a method
                    logger.info(f"Order data for {phase_before_wait} found in game object. GameHistory needs to integrate this.")


                await agent.generate_phase_result_diary_entry(
                    game=game, # Game object should now reflect results of phase_before_wait
                    current_phase=phase_before_wait, # The phase that just ended
                    log_file_path=llm_log_file_path
                )
                logger.info(f"Phase result diary entry generated for {phase_before_wait}.")

                # Diary consolidation at year end
                # A Winter phase (W) or Adjustment phase (A) typically signifies end of a game year.
                ended_phase_type = game.get_phase_type_from_phase_str(phase_before_wait)
                if ended_phase_type in ['W', 'A']: # W1901A (Winter Adjustments) or F1901M then W1901B
                    year_of_ended_phase = game.get_year_from_phase(phase_before_wait)
                    await agent.consolidate_year_diary_entries(
                        current_year=year_of_ended_phase, 
                        log_file_path=llm_log_file_path
                    )
                    logger.info(f"Year-end diary consolidation for {year_of_ended_phase} after phase {phase_before_wait}.")

                await agent.analyze_phase_and_update_state(
                    game=game,
                    game_history=game_history,
                    current_phase=phase_before_wait, # Analyze the phase that just finished
                    log_file_path=llm_log_file_path
                )
                logger.info(f"Agent goals, relationships, and state updated after {phase_before_wait}.")
                
                last_processed_phase_for_agent_updates = phase_before_wait
            except Exception as e:
                logger.error(f"Error during post-phase processing for {phase_before_wait}: {e}", exc_info=True)
        
        await asyncio.sleep(0.1) # Brief pause before starting next cycle

    # --- Game Loop Finished ---
    logger.info("Game loop finished.")
    if game.is_game_done:
        final_state_summary = game.get_state() # This is a large dict
        logger.info(f"Game {args.game_id} is completed.")
        logger.info(f"Final Ranks: {game.get_ranks()}") # If NetworkGame has get_ranks()
        # Perform final analysis or save final state if needed
        # For example, final diary entry:
        try:
            # A dummy "final thoughts" diary entry
            final_phase_name = game.get_current_phase() # Should be something like "COMPLETED"
            agent.private_diary.add_entry(
                phase=final_phase_name,
                entry_type="GameEndReflection",
                content=f"The game has concluded. My final rank is {game.get_rank(args.power_name) if hasattr(game, 'get_rank') else 'unknown'}. Powers: {list(game.powers.keys())}"
            )
            agent.save_private_diary(args.log_dir) # Save final diary
        except Exception as e:
            logger.error(f"Error during final agent cleanup: {e}", exc_info=True)


    await connection.close()
    logger.info("Connection closed.")


if __name__ == "__main__":
    args = parse_arguments()
    try:
        asyncio.run(play_network_game(args))
    except KeyboardInterrupt:
        logger.info("Agent terminated by user (KeyboardInterrupt).")
    except Exception as e:
        logger.error(f"Unhandled exception in main: {e}", exc_info=True)
    finally:
        logger.info("Network LM Agent shut down.")
        logging.shutdown()


# This initial setup includes:
# *   Imports for `argparse`, `asyncio`, `logging`, `os`, `time`, `dotenv`.
# *   Imports for `connect`, `GameHistory`, `DiplomacyAgent`, `load_model_client`, and some utilities from `ai_diplomacy`. I've commented out specific negotiation/planning imports for now as their exact usage with `NetworkGame` needs to be confirmed.
# *   Argument parsing for all specified options, including constructing `args.log_dir`.
# *   The `play_network_game` async function skeleton:
#     *   Loads `.env`.
#     *   Sets up basic file and console logging, directing logs to the agent-specific `log_dir`.
#     *   Establishes connection and authenticates with the server.
#     *   Includes a loop to wait for and join the specified game.
#     *   Initializes `GameHistory`, `llm_client` (with Ollama URL override), and `DiplomacyAgent`.
#     *   Calls `initialize_agent_state_ext`.
#     *   Includes a placeholder for the main game loop.
# *   An `if __name__ == "__main__":` block to parse arguments and run `play_network_game`.
# *   Basic error handling for connection, authentication, and LLM client loading.

# Next, I will focus on implementing the main game loop logic within `play_network_game`. This will involve handling phases, negotiations, planning (if enabled), order generation, and waiting for phase progression. I'll also need to consider how `GameHistory` is updated in a network setting.
# I will now proceed to implement the game loop within the `play_network_game` function.
# This will involve:
# 1.  Looping while `not game.is_game_done`.
# 2.  Getting the current phase.
# 3.  Implementing logic for negotiation, planning, and order submission based on the phase type.
# 4.  Waiting for the game to advance to the next phase.
# 5.  Updating game history and agent state after each phase.

# I will also need to ensure that the imported functions like `conduct_negotiations_phase` (I'll use this distinct name if I create/adapt a wrapper) and `planning_phase_action` are either compatible with `NetworkGame` or adapted. For now, I'll assume they can be called, and focus on the agent's interaction flow.

# I'll need to import `conduct_negotiations_phase` and `planning_phase_action` from `ai_diplomacy.utils` (or wherever they are defined, assuming they are the intended wrappers for network play). If they are not yet adapted for network play, this implementation will highlight the necessary interfaces.

# Let's refine the imports and then implement the loop.
# It seems `conduct_negotiations` and `planning_phase` are not directly in `ai_diplomacy.utils` but are higher-level concepts that might be part of `lm_game.py` or need to be new functions. I will assume for now that I need to implement simplified versions or call agent methods directly for some of these actions, and use placeholders where the exact function from `ai_diplomacy` is not clear or might need adaptation.

# For `conduct_negotiations`, the core is `agent.generate_negotiation_messages` and then sending them using `game.send_game_message`.
# For `planning_phase`, it's `agent.generate_plan`.
# For `get_valid_orders`, `ai_diplomacy.utils.get_valid_orders` is available.
# `initialize_agent_state_ext` is also available.Okay, I've created the initial structure for `network_lm_agent.py`, including argument parsing, logging setup, server connection, authentication, game joining, and initialization of `GameHistory` and `DiplomacyAgent`.

# Now, I will implement the main game loop within the `play_network_game` function. This loop will handle different game phases, conduct negotiations, perform planning, generate orders, and update the agent's state and history.

# I will need to ensure the functions called (like for negotiation or planning) are compatible with the `NetworkGame` object. The `NetworkGame` object is expected to be updated by notifications from the server. The agent will primarily react to these changes and submit its decisions (messages, orders) back to the server.

# Let's proceed with fleshing out the `play_network_game` function, specifically the game loop.
