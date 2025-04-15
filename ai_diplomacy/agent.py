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
ALLOWED_RELATIONSHIPS = ["Enemy", "Unfriendly", "Neutral", "Friendly", "Ally"]

# == New: Helper function to load prompt files reliably ==
def _load_prompt_file(filename: str) -> Optional[str]:
    """Loads a prompt template from the prompts directory."""
    try:
        # Construct path relative to this file's location
        current_dir = os.path.dirname(os.path.abspath(__file__))
        prompts_dir = os.path.join(current_dir, 'prompts')
        filepath = os.path.join(prompts_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {filepath}")
        return None
    except Exception as e:
        logger.error(f"Error loading prompt file {filepath}: {e}")
        return None

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

    def _extract_json_from_text(self, text: str) -> dict:
        """Extract and parse JSON from text, handling common LLM response formats."""
        # Try different patterns to extract JSON
        # 1. Try to find JSON wrapped in markdown code blocks
        patterns = [
            r"```json\n(.*?)\n```",  # Markdown JSON block
            r"```\n(.*?)\n```",      # Generic markdown block
            r"`(.*?)`",              # Inline code block
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            if matches:
                # Try each match until one parses successfully
                for match in matches:
                    try:
                        return json.loads(match)
                    except json.JSONDecodeError:
                        continue
        
        # 2. Try to find JSON between braces
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
        
        # 3. Aggressively clean the string and try again
        # Remove common non-JSON text that LLMs might add
        cleaned_text = re.sub(r'[^{}[\]"\',:.\d\w\s_-]', '', text)
        try:
            start = cleaned_text.find('{')
            end = cleaned_text.rfind('}') + 1
            if start != -1 and end > start:
                return json.loads(cleaned_text[start:end])
        except json.JSONDecodeError:
            pass
        
        # 4. Repair common JSON issues and try again
        try:
            # Replace single quotes with double quotes (common LLM error)
            text_fixed = re.sub(r"'([^']*)':", r'"\1":', text)
            text_fixed = re.sub(r': *\'([^\']*)\'', r': "\1"', text_fixed)
            
            start = text_fixed.find('{')
            end = text_fixed.rfind('}') + 1
            if start != -1 and end > start:
                return json.loads(text_fixed[start:end])
        except json.JSONDecodeError:
            pass
        
        # If all attempts fail, raise error
        raise json.JSONDecodeError("Could not extract valid JSON from LLM response", text, 0)

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
            allowed_labels_str = ", ".join(ALLOWED_RELATIONSHIPS)
            initial_prompt = f"You are the agent for {self.power_name} in a game of Diplomacy at the very start (Spring 1901). " \
                             f"Analyze the initial board position and suggest 2-3 strategic high-level goals for the early game. " \
                             f"Consider your power's strengths, weaknesses, and neighbors. " \
                             f"Also, provide an initial assessment of relationships with other powers. " \
                             f"IMPORTANT: For each relationship, you MUST use exactly one of the following labels: {allowed_labels_str}. " \
                             f"Format your response as a JSON object with two keys: 'initial_goals' (a list of strings) and 'initial_relationships' (a dictionary mapping power names to one of the allowed relationship strings)."

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

            # Try to extract JSON from the response
            try:
                update_data = self._extract_json_from_text(response)
                logger.debug(f"[{self.power_name}] Successfully parsed JSON: {update_data}")
            except json.JSONDecodeError as e:
                logger.error(f"[{self.power_name}] All JSON extraction attempts failed: {e}")
                # Create default data rather than failing
                update_data = {
                    "initial_goals": ["Survive and expand", "Form beneficial alliances", "Secure key territories"],
                    "initial_relationships": {p: "Neutral" for p in ALL_POWERS if p != self.power_name},
                    "goals": ["Survive and expand", "Form beneficial alliances", "Secure key territories"],
                    "relationships": {p: "Neutral" for p in ALL_POWERS if p != self.power_name}
                }
                logger.warning(f"[{self.power_name}] Using default goals and relationships: {update_data}")

            # Check for both possible key names
            initial_goals = update_data.get('initial_goals')
            if initial_goals is None:
                initial_goals = update_data.get('goals')
                if initial_goals is not None:
                    logger.debug(f"[{self.power_name}] Using 'goals' key instead of 'initial_goals'")
            
            initial_relationships = update_data.get('initial_relationships')
            if initial_relationships is None:
                initial_relationships = update_data.get('relationships')
                if initial_relationships is not None:
                    logger.debug(f"[{self.power_name}] Using 'relationships' key instead of 'initial_relationships'")

            if isinstance(initial_goals, list):
                self.goals = initial_goals
                # == Fix: Correct add_journal_entry call signature ==
                self.add_journal_entry(f"[{game.current_short_phase}] Initial Goals Set: {self.goals}")
            else:
                logger.warning(f"[{self.power_name}] LLM did not provide valid 'initial_goals' list.")
                # Set default goals
                self.goals = ["Survive and expand", "Form beneficial alliances", "Secure key territories"]
                self.add_journal_entry(f"[{game.current_short_phase}] Set default initial goals: {self.goals}")

            if isinstance(initial_relationships, dict):
                # Validate relationship keys and values
                valid_relationships = {}
                invalid_count = 0
                
                for p, r in initial_relationships.items():
                    # Convert power name to uppercase for case-insensitive matching
                    p_upper = p.upper()
                    if p_upper in ALL_POWERS and p_upper != self.power_name:
                        # Check against allowed labels (case-insensitive)
                        r_title = r.title() if isinstance(r, str) else r  # Convert "enemy" to "Enemy" etc.
                        if r_title in ALLOWED_RELATIONSHIPS:
                            valid_relationships[p_upper] = r_title
                        else:
                            invalid_count += 1
                            if invalid_count <= 2:  # Only log first few to reduce noise
                                logger.warning(f"[{self.power_name}] Received invalid relationship label '{r}' for '{p}'. Setting to Neutral.")
                                valid_relationships[p_upper] = "Neutral"
                    else:
                        invalid_count += 1
                        if invalid_count <= 2 and not p_upper.startswith(self.power_name):  # Only log first few to reduce noise
                            logger.warning(f"[{self.power_name}] Received relationship for invalid/own power '{p}'. Ignoring.")
                
                # Summarize if there were many invalid entries
                if invalid_count > 2:
                    logger.warning(f"[{self.power_name}] {invalid_count} total invalid relationships were processed.")
                
                # If we have any valid relationships, use them
                if valid_relationships:
                    self.relationships = valid_relationships
                    self.add_journal_entry(f"[{game.current_short_phase}] Initial Relationships Set: {self.relationships}")
                else:
                    # Set default relationships
                    logger.warning(f"[{self.power_name}] No valid relationships found, using defaults.")
                    self.relationships = {p: "Neutral" for p in ALL_POWERS if p != self.power_name}
                    self.add_journal_entry(f"[{game.current_short_phase}] Set default neutral relationships.")
            else:
                 logger.warning(f"[{self.power_name}] LLM did not provide valid 'initial_relationships' dict.")
                 # Set default relationships
                 self.relationships = {p: "Neutral" for p in ALL_POWERS if p != self.power_name}
                 self.add_journal_entry(f"[{game.current_short_phase}] Set default neutral relationships.")

        except Exception as e:
            logger.error(f"[{self.power_name}] Error during initial state generation: {e}", exc_info=True)
            # Set conservative defaults even if everything fails
            if not self.goals:
                self.goals = ["Survive and expand", "Form beneficial alliances", "Secure key territories"]
            if not self.relationships:
                self.relationships = {p: "Neutral" for p in ALL_POWERS if p != self.power_name}
            logger.info(f"[{self.power_name}] Set fallback goals and relationships after error.")

    def analyze_phase_and_update_state(self, game: 'Game', board_state: dict, phase_summary: str, game_history: 'GameHistory'):
        """Analyzes the outcome of the last phase and updates goals/relationships using the LLM."""
        # Use self.power_name internally
        power_name = self.power_name 
        logger.info(f"[{power_name}] Analyzing phase {game.current_short_phase} outcome to update state...")
        self.log_state(f"Before State Update ({game.current_short_phase})")

        try:
            # 1. Construct the prompt using the dedicated state update prompt file
            prompt_template = _load_prompt_file('state_update_prompt.txt')
            if not prompt_template:
                 logger.error(f"[{power_name}] Could not load state_update_prompt.txt. Skipping state update.")
                 return
 
            # Get previous phase safely from history
            if not game_history or not game_history.phases:
                logger.warning(f"[{power_name}] No game history available to analyze for {game.current_short_phase}. Skipping state update.")
                return

            last_phase = game_history.phases[-1]
            last_phase_name = last_phase.name # Assuming phase object has a 'name' attribute
            
            # Use the provided phase_summary parameter instead of retrieving it
            last_phase_summary = phase_summary
            if not last_phase_summary:
                logger.warning(f"[{power_name}] No summary available for previous phase {last_phase_name}. Skipping state update.")
                return
 
            # == Fix: Use board_state parameter ==
            possible_orders = game.get_all_possible_orders()

            context = self.client.build_context_prompt(
                game=game,
                board_state=board_state, # Use provided board_state parameter
                power_name=power_name,
                possible_orders=possible_orders, # Pass possible_orders
                game_history=game_history, # Pass game_history
                agent_goals=self.goals,
                agent_relationships=self.relationships
            )

            # Add previous phase summary to the information provided to the LLM
            other_powers = [p for p in game.powers if p != power_name]
            
            # Create a readable board state string from the board_state dict
            board_state_str = f"Board State:\n"
            for p_name, power_data in board_state.get('powers', {}).items():
                # Get units and centers from the board state
                units = power_data.get('units', [])
                centers = power_data.get('centers', [])
                board_state_str += f"  {p_name}: Units={units}, Centers={centers}\n"
            
            # Extract year from the phase name (e.g., "S1901M" -> "1901")
            current_year = last_phase_name[1:5] if len(last_phase_name) >= 5 else "unknown"
            
            prompt = prompt_template.format(
                power_name=power_name,
                current_year=current_year,
                current_phase=last_phase_name, # Analyze the phase that just ended
                board_state_str=board_state_str,
                phase_summary=last_phase_summary, # Use provided phase_summary
                other_powers=str(other_powers), # Pass as string representation
                current_goals="\n".join([f"- {g}" for g in self.goals]) if self.goals else "None",
                current_relationships=str(self.relationships) if self.relationships else "None"
            )
            logger.debug(f"[{power_name}] State update prompt:\n{prompt}")

            # Use the client's raw generation capability
            response = self.client.generate_response(prompt)
            logger.debug(f"[{power_name}] Raw LLM response for state update: {response}")

            # Use our robust JSON extraction helper
            try:
                update_data = self._extract_json_from_text(response)
                logger.debug(f"[{power_name}] Successfully parsed JSON: {update_data}")
            except json.JSONDecodeError as e:
                logger.error(f"[{power_name}] Failed to parse JSON response for state update: {e}")
                logger.error(f"[{power_name}] Raw response was: {response}")
                # Create fallback data to avoid full failure
                update_data = {
                    "updated_goals": self.goals, # Maintain current goals
                    "updated_relationships": self.relationships, # Maintain current relationships
                    "goals": self.goals, # Alternative key
                    "relationships": self.relationships # Alternative key
                }
                logger.warning(f"[{power_name}] Using existing goals and relationships as fallback: {update_data}")

            # Check for both possible key names (prompt uses "goals"/"relationships", 
            # but code was expecting "updated_goals"/"updated_relationships")
            updated_goals = update_data.get('updated_goals')
            if updated_goals is None:
                updated_goals = update_data.get('goals')
                if updated_goals is not None:
                    logger.debug(f"[{power_name}] Using 'goals' key instead of 'updated_goals'")
            
            updated_relationships = update_data.get('updated_relationships')
            if updated_relationships is None:
                updated_relationships = update_data.get('relationships')
                if updated_relationships is not None:
                    logger.debug(f"[{power_name}] Using 'relationships' key instead of 'updated_relationships'")

            if isinstance(updated_goals, list):
                # Simple overwrite for now, could be more sophisticated (e.g., merging)
                self.goals = updated_goals
                self.add_journal_entry(f"[{game.current_short_phase}] Goals updated based on {last_phase_name}: {self.goals}")
            else:
                logger.warning(f"[{power_name}] LLM did not provide valid 'updated_goals' list in state update.")
                # Keep current goals, no update needed

            if isinstance(updated_relationships, dict):
                # Validate and update relationships
                valid_new_relationships = {}
                invalid_count = 0
                
                for p, r in updated_relationships.items():
                    # Convert power name to uppercase for case-insensitive matching
                    p_upper = p.upper()
                    if p_upper in ALL_POWERS and p_upper != power_name:
                        # Check against allowed labels (case-insensitive)
                        r_title = r.title() if isinstance(r, str) else r  # Convert "enemy" to "Enemy" etc.
                        if r_title in ALLOWED_RELATIONSHIPS:
                            valid_new_relationships[p_upper] = r_title
                        else:
                            invalid_count += 1
                            if invalid_count <= 2:  # Only log first few to reduce noise
                                logger.warning(f"[{power_name}] Received invalid relationship label '{r}' for '{p}'. Ignoring.")
                    else:
                        invalid_count += 1
                        if invalid_count <= 2 and not p_upper.startswith(power_name):  # Only log first few to reduce noise
                            logger.warning(f"[{power_name}] Received relationship for invalid/own power '{p}' (normalized: {p_upper}). Ignoring.")
                
                # Summarize if there were many invalid entries
                if invalid_count > 2:
                    logger.warning(f"[{power_name}] {invalid_count} total invalid relationships were ignored.")
                    
                # Update relationships if the dictionary is not empty after validation
                if valid_new_relationships:
                    self.relationships.update(valid_new_relationships)
                    self.add_journal_entry(f"[{game.current_short_phase}] Relationships updated based on {last_phase_name}: {valid_new_relationships}")
                elif updated_relationships: # Log if the original dict wasn't empty but validation removed everything
                    logger.warning(f"[{power_name}] Found relationships in LLM response but none were valid after normalization. Using defaults.")
                else: # Log if the original dict was empty
                     logger.warning(f"[{power_name}] LLM did not provide valid 'updated_relationships' dict in state update.")
                     # Keep current relationships, no update needed
            else:
                 logger.warning(f"[{power_name}] LLM did not provide valid 'updated_relationships' dict in state update.")
                 # Keep current relationships, no update needed

        except FileNotFoundError:
            logger.error(f"[{power_name}] state_update_prompt.txt not found. Skipping state update.")
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
