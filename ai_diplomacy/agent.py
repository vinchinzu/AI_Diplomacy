import logging
import os
from typing import List, Dict, Optional
import json
import re

# Assuming BaseModelClient is importable from clients.py in the same directory
from .clients import BaseModelClient 
# Import load_prompt from utils
from .utils import load_prompt

logger = logging.getLogger(__name__)

# == Best Practice: Define constants at module level ==
ALL_POWERS = frozenset({"AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"})

class DiplomacyAgent:
    """
    Represents a stateful AI agent playing as a specific power in Diplomacy.
    It holds the agent's goals, relationships, and private journal,
    and uses a BaseModelClient instance to interact with the LLM.
    """
    def __init__(
        self, 
        power_name: str, 
        client: BaseModelClient, 
        initial_goals: Optional[List[str]] = None,
        initial_relationships: Optional[Dict[str, str]] = None,
    ):
        """
        Initializes the DiplomacyAgent.

        Args:
            power_name: The name of the power this agent represents (e.g., 'FRANCE').
            client: An instance of a BaseModelClient subclass for LLM interaction.
            initial_goals: An optional list of initial strategic goals.
            initial_relationships: An optional dictionary mapping other power names to 
                                     relationship statuses (e.g., 'ALLY', 'ENEMY', 'NEUTRAL').
        """
        if power_name not in ALL_POWERS:
            raise ValueError(f"Invalid power name: {power_name}. Must be one of {ALL_POWERS}")

        self.power_name: str = power_name
        self.client: BaseModelClient = client
        # Initialize goals as empty list, will be populated by initialize_agent_state
        self.goals: List[str] = initial_goals if initial_goals is not None else [] 
        # Initialize relationships to Neutral if not provided
        if initial_relationships is None:
            self.relationships: Dict[str, str] = {p: "Neutral" for p in ALL_POWERS if p != self.power_name}
        else:
            self.relationships: Dict[str, str] = initial_relationships
        self.private_journal: List[str] = []

        # --- Load and set the appropriate system prompt ---
        # Get the directory containing the current file (agent.py)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Construct path relative to the current file's directory
        prompts_dir = os.path.join(current_dir, "prompts") 
        power_prompt_filename = os.path.join(prompts_dir, f"{power_name.lower()}_system_prompt.txt")
        default_prompt_filename = os.path.join(prompts_dir, "system_prompt.txt")

        system_prompt_content = load_prompt(power_prompt_filename)

        if not system_prompt_content:
            logger.warning(f"Power-specific prompt '{power_prompt_filename}' not found or empty. Loading default system prompt.")
            # system_prompt_content = load_prompt("system_prompt.txt")
            system_prompt_content = load_prompt(default_prompt_filename)
        else:
             logger.info(f"Loaded power-specific system prompt for {power_name}.")
        # ----------------------------------------------------

        if system_prompt_content: # Ensure we actually have content before setting
             self.client.set_system_prompt(system_prompt_content)
        else:
             logger.error(f"Could not load default system prompt either! Agent {power_name} may not function correctly.")
        logger.info(f"Initialized DiplomacyAgent for {self.power_name} with goals: {self.goals}")
        self.add_journal_entry(f"Agent initialized. Initial Goals: {self.goals}")

    def add_journal_entry(self, entry: str):
        """Adds a formatted entry string to the agent's private journal."""
        # Ensure entry is a string
        if not isinstance(entry, str):
            entry = str(entry)
        self.private_journal.append(entry)
        logger.debug(f"[{self.power_name} Journal]: {entry}")

    def initialize_agent_state(self, game: 'Game', game_history: 'GameHistory'):
        """Uses the LLM to set initial goals based on the starting game state."""
        logger.info(f"[{self.power_name}] Initializing agent state using LLM...")
        try:
            # Use a simplified prompt for initial state generation
            # TODO: Create a dedicated 'initial_state_prompt.txt'
            initial_prompt = f"You are the agent for {self.power_name} in a game of Diplomacy at the very start (Spring 1901). \
                             Analyze the initial board position and suggest 2-3 strategic high-level goals for the early game. \
                             Consider your power's strengths, weaknesses, and neighbors. \
                             Also, provide an initial assessment of relationships with other powers (Ally, Neutral, Potential Threat, Enemy). \
                             Format your response as a JSON object with two keys: 'initial_goals' (a list of strings) and 'initial_relationships' (a dictionary mapping power names to relationship strings)."

            # == Fix: Get required state info from game object ==
            board_state = game.get_state()
            possible_orders = game.get_all_possible_orders()

            # == Add detailed logging before call ==
            logger.debug(f"[{self.power_name}] Preparing context for initial state. Got board_state type: {type(board_state)}, possible_orders type: {type(possible_orders)}, game_history type: {type(game_history)}")
            logger.debug(f"[{self.power_name}] Calling build_context_prompt with game: {game is not None}, board_state: {board_state is not None}, power_name: {self.power_name}, possible_orders: {possible_orders is not None}, game_history: {game_history is not None}")

            context = self.client.build_context_prompt(
                game=game,
                board_state=board_state, # Pass board_state
                power_name=self.power_name,
                possible_orders=possible_orders, # Pass possible_orders
                game_history=game_history, # Pass game_history
                agent_goals=None, # No goals yet
                agent_relationships=None, # No relationships yet (defaults used in prompt)
            )
            full_prompt = initial_prompt + "\n\n" + context

            response = self.client.generate_response(full_prompt)
            logger.debug(f"[{self.power_name}] LLM response for initial state: {response}")

            # Extract JSON potentially wrapped in markdown fences or with extra text
            json_match = re.search(r"```json\n(.*?)\n```", response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # If no fences, try to find the first '{' and last '}'
                start = response.find('{')
                end = response.rfind('}')
                if start != -1 and end != -1:
                    json_str = response[start:end+1]
                else:
                     # Fallback to raw response if no JSON structure identified
                    json_str = response 

            logger.debug(f"[{self.power_name}] Attempting to parse JSON: {json_str}")
            update_data = json.loads(json_str)

            initial_goals = update_data.get('initial_goals')
            initial_relationships = update_data.get('initial_relationships')

            if isinstance(initial_goals, list):
                self.goals = initial_goals
                # == Fix: Correct add_journal_entry call signature ==
                self.add_journal_entry(f"[{game.current_short_phase}] Initial Goals Set: {self.goals}")
            else:
                logger.warning(f"[{self.power_name}] LLM did not provide valid 'initial_goals' list.")

            if isinstance(initial_relationships, dict):
                # Validate relationship keys
                valid_relationships = {p: r for p, r in initial_relationships.items() if p in ALL_POWERS and p != self.power_name}
                self.relationships = valid_relationships
                 # == Fix: Correct add_journal_entry call signature ==
                self.add_journal_entry(f"[{game.current_short_phase}] Initial Relationships Set: {self.relationships}")
            else:
                 logger.warning(f"[{self.power_name}] LLM did not provide valid 'initial_relationships' dict.")

        except json.JSONDecodeError as e:
            logger.error(f"[{self.power_name}] Failed to parse LLM JSON response for initial state: {e}")
            logger.error(f"[{self.power_name}] Raw response was: {response}")
        except Exception as e:
            logger.error(f"[{self.power_name}] Error during initial state generation: {e}", exc_info=True)


    def analyze_phase_and_update_state(self, game: 'Game', game_history: 'GameHistory'):
        """Analyzes the outcome of the last phase and updates goals/relationships using the LLM."""
        # Use self.power_name internally
        power_name = self.power_name 
        logger.info(f"[{power_name}] Analyzing phase {game.current_short_phase} outcome to update state...")
        self.log_state(f"Before State Update ({game.current_short_phase})")

        try:
            # 1. Construct the prompt using the dedicated state update prompt file
            prompt_template = self.client.load_prompt('state_update_prompt.txt')
            if not prompt_template:
                 logger.error(f"[{power_name}] Could not load state_update_prompt.txt. Skipping state update.")
                 return
 
            # Get previous phase safely
            prev_phase = game.get_prev_phase()
            if not prev_phase:
                 logger.warning(f"[{power_name}] No previous phase found to analyze for {game.current_short_phase}. Skipping state update.")
                 return
                 
            last_phase_summary = game_history.get_phase_summary(prev_phase)
            if not last_phase_summary:
                logger.warning(f"[{power_name}] No summary available for previous phase {prev_phase}. Skipping state update.")
                return

            # == Fix: Get required state info from game object for context ==
            board_state = game.get_state()
            possible_orders = game.get_all_possible_orders()

            context = self.client.build_context_prompt(
                game=game,
                board_state=board_state, # Pass board_state
                power_name=power_name,
                possible_orders=possible_orders, # Pass possible_orders
                game_history=game_history, # Pass game_history
                agent_goals=self.goals,
                agent_relationships=self.relationships
            )

            # Add previous phase summary to the information provided to the LLM
            prompt = prompt_template.format(
                power_name=power_name,
                current_goals=self.goals,
                current_relationships=self.relationships,
                phase_summary=last_phase_summary, # Provide summary of what just happened
                game_context=context # Provide current game state
            )
            logger.debug(f"[{power_name}] State update prompt:\n{prompt}")

            # Use the client's raw generation capability
            response = self.client.generate_response(prompt)
            logger.debug(f"[{power_name}] Raw LLM response for state update: {response}")

            # Extract JSON potentially wrapped in markdown fences or with extra text
            json_match = re.search(r"```json\n(.*?)\n```", response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # If no fences, try to find the first '{' and last '}'
                start = response.find('{')
                end = response.rfind('}')
                if start != -1 and end != -1:
                    json_str = response[start:end+1]
                else:
                     # Fallback to raw response if no JSON structure identified
                    json_str = response

            logger.debug(f"[{power_name}] Attempting to parse JSON for state update: {json_str}")
            update_data = json.loads(json_str)

            updated_goals = update_data.get('updated_goals')
            updated_relationships = update_data.get('updated_relationships')

            if isinstance(updated_goals, list):
                # Simple overwrite for now, could be more sophisticated (e.g., merging)
                self.goals = updated_goals
                # == Fix: Correct add_journal_entry call signature ==
                self.add_journal_entry(f"[{game.current_short_phase}] Goals updated based on {prev_phase}: {self.goals}")
            else:
                logger.warning(f"[{power_name}] LLM did not provide valid 'updated_goals' list in state update.")

            if isinstance(updated_relationships, dict):
                # Validate and update relationships
                valid_new_relationships = {p: r for p, r in updated_relationships.items() if p in ALL_POWERS and p != power_name}
                # Update relationships if the dictionary is not empty after validation
                if valid_new_relationships:
                    self.relationships.update(valid_new_relationships)
                    # == Fix: Correct add_journal_entry call signature ==
                    self.add_journal_entry(f"[{game.current_short_phase}] Relationships updated based on {prev_phase}: {valid_new_relationships}")
                elif updated_relationships: # Log if the original dict wasn't empty but validation removed everything
                    logger.warning(f"[{power_name}] LLM provided relationships, but none were valid: {updated_relationships}")
                else: # Log if the original dict was empty
                     logger.warning(f"[{power_name}] LLM provided empty or invalid 'updated_relationships' dict.")
            else:
                 logger.warning(f"[{power_name}] LLM did not provide valid 'updated_relationships' dict in state update.")

        except FileNotFoundError:
            logger.error(f"[{power_name}] state_update_prompt.txt not found. Skipping state update.")
        except json.JSONDecodeError as e:
            logger.error(f"[{power_name}] Failed to parse LLM JSON response for state update: {e}")
            logger.error(f"[{power_name}] Raw response was: {response}")
        except Exception as e:
            # Catch any other unexpected errors during the update process
            logger.error(f"[{power_name}] Error during state analysis/update for phase {game.current_short_phase}: {e}", exc_info=True)

        self.log_state(f"After State Update ({game.current_short_phase})")


    def update_goals(self, new_goals: List[str]):
        """Updates the agent's strategic goals."""
        self.goals = new_goals
        self.add_journal_entry(f"Goals updated: {self.goals}")
        logger.info(f"[{self.power_name}] Goals updated to: {self.goals}")

    def update_relationship(self, other_power: str, status: str):
        """Updates the agent's perceived relationship with another power."""
        if other_power != self.power_name:
             self.relationships[other_power] = status
             self.add_journal_entry(f"Relationship with {other_power} updated to {status}.")
             logger.info(f"[{self.power_name}] Relationship with {other_power} set to {status}.")
        else:
             logger.warning(f"[{self.power_name}] Attempted to set relationship with self.")

    def get_agent_state_summary(self) -> str:
        """Returns a string summary of the agent's current state."""
        summary = f"Agent State for {self.power_name}:\n"
        summary += f"  Goals: {self.goals}\n"
        summary += f"  Relationships: {self.relationships}\n"
        summary += f"  Journal Entries: {len(self.private_journal)}"
        # Optionally include last few journal entries
        # if self.private_journal:
        #    summary += f"\n  Last Journal Entry: {self.private_journal[-1]}"
        return summary

    def generate_plan(self, game: 'Game', board_state: dict, game_history: 'GameHistory') -> str:
        """Generates a strategic plan using the client and logs it."""
        logger.info(f"Agent {self.power_name} generating strategic plan...")
        try:
            plan = self.client.get_plan(game, board_state, self.power_name, game_history)
            self.add_journal_entry(f"Generated plan for phase {game.current_phase}:\n{plan}")
            logger.info(f"Agent {self.power_name} successfully generated plan.")
            return plan
        except Exception as e:
            logger.error(f"Agent {self.power_name} failed to generate plan: {e}")
            self.add_journal_entry(f"Failed to generate plan for phase {game.current_phase} due to error: {e}")
            return "Error: Failed to generate plan."

    # def process_message(self, message, game_phase):
    #     """Processes an incoming message, updates relationships/journal."""
    #     # 1. Analyze message content
    #     # 2. Update self.relationships based on message
    #     # 3. Add journal entry about the message and its impact
    #     pass

    # def generate_message_reply(self, conversation_so_far, game_phase):
    #      """Generates a reply to a conversation using agent state."""
    #      # 1. Consider goals, relationships when crafting reply
    #      # 2. Delegate to self.client.get_conversation_reply(...)
    #      # 3. Add journal entry about the generated message
    #      pass

    def log_state(self, message: str):
        """Logs the current state of the agent."""
        logger.info(f"[{self.power_name}] {message}")
        logger.info(f"  Goals: {self.goals}")
        logger.info(f"  Relationships: {self.relationships}")
