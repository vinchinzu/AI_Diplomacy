import logging
import os
from typing import List, Dict, Optional
# Removed: import re
# Removed: import asyncio
# Removed: import json

import llm # Import the llm library
from diplomacy import Game # Message is removed
from .game_history import GameHistory
from . import llm_utils # Import the new module
from . import prompt_utils # Import for Jinja2 rendering
# Removed: from .utils import log_llm_response
from .prompt_constructor import build_context_prompt # Added import
from .llm_coordinator import LocalLLMCoordinator, LLMCallResult # _local_lock is removed
from .game_config import GameConfig # Added import for GameConfig
# Removed: from .llm_interface import AgentLLMInterface
# Removed: from ai_diplomacy.prompts import SYSTEM_PROMPT_TEMPLATE, POWER_SPECIFIC_PROMPTS, PLANNING_PROMPT_TEMPLATE, NEGOTIATION_DIARY_PROMPT_TEMPLATE, ORDER_SUBMISSION_PROMPT_TEMPLATE, ORDER_DIARY_PROMPT_TEMPLATE

logger = logging.getLogger(__name__) # Module-level logger

# == Best Practice: Define constants at module level ==
ALL_POWERS = frozenset({"AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"})
ALLOWED_RELATIONSHIPS = ["Enemy", "Unfriendly", "Neutral", "Friendly", "Ally"]

# Global LLM Coordinator instance
_global_llm_coordinator = LocalLLMCoordinator()

# _local_llm_lock has been moved to llm_coordinator.py
# _load_prompt_file function has been moved to llm_utils.py

class DiplomacyAgent:
    """
    Represents a stateful AI agent playing as a specific power in Diplomacy.
    It holds the agent's goals, relationships, and private journal,
    and uses a BaseModelClient instance to interact with the LLM.
    """
    def __init__(
        self, 
        power_name: str, 
        model_id: str, # Changed from client: BaseModelClient
        game_config: 'GameConfig', # Added game_config parameter
        game_id: str = "unknown_game",  # Add game_id parameter
        initial_goals: Optional[List[str]] = None,
        initial_relationships: Optional[Dict[str, str]] = None,
    ):
        """
        Initializes the DiplomacyAgent.

        Args:
            power_name: The name of the power this agent represents (e.g., 'FRANCE').
            model_id: The llm-compatible model ID string for LLM interaction.
            game_config: The game configuration object.
            game_id: The ID of the game this agent is playing in.
            initial_goals: An optional list of initial strategic goals.
            initial_relationships: An optional dictionary mapping other power names to 
                                     relationship statuses (e.g., 'ALLY', 'ENEMY', 'NEUTRAL').
        """
        if power_name not in ALL_POWERS:
            raise ValueError(f"Invalid power name: {power_name}. Must be one of {ALL_POWERS}")

        self.power_name: str = power_name
        self.model_id: str = model_id
        self.game_config = game_config # Store game_config
        self.game_id: str = game_id
        
        # Validate the model_id at initialization
        try:
            # Validate the model_id by trying to get the model instance
            # The Ollama plugin for the 'llm' library typically relies on
            # environment variables like OLLAMA_HOST or OLLAMA_BASE_URL.
            # Passing 'options' here was causing the TypeError.
            logger.debug(f"[{self.power_name} __init__] Checking Ollama ENV VARS before llm.get_model for validation:")
            logger.debug(f"[{self.power_name} __init__] OLLAMA_HOST: {os.environ.get('OLLAMA_HOST')}")
            logger.debug(f"[{self.power_name} __init__] OLLAMA_BASE_URL: {os.environ.get('OLLAMA_BASE_URL')}")
            logger.debug(f"[{self.power_name} __init__] OLLAMA_PORT: {os.environ.get('OLLAMA_PORT')}")

            # Corrected call: removed the 'options' argument.
            _ = llm.get_model(self.model_id)
            
            logger.info(f"Successfully validated model_id '{self.model_id}' for agent {self.power_name}.")
            self._model_instance = None # Initialize but don't keep it loaded yet. Lazy load in methods.
        except llm.UnknownModelError as ume:
            logger.error(f"CRITICAL: Unknown model_id '{self.model_id}' for agent {self.power_name}. This agent will not function. Error: {ume}")
            raise # Re-raise the error to halt initialization if the model is unknown
        except Exception as e: # General exception handling for other errors
            logger.error(f"CRITICAL: Unexpected error validating model_id '{self.model_id}' for agent {self.power_name}: {e}")
            raise # Re-raise any other critical error during model validation
        
        self.goals: List[str] = initial_goals if initial_goals is not None else [] 
        
        # Initialize relationships to Neutral if not provided
        if initial_relationships is None:
            self.relationships: Dict[str, str] = {p: "Neutral" for p in ALL_POWERS if p != self.power_name}
        else:
            self.relationships: Dict[str, str] = initial_relationships
        
        # Initialize private tracking lists
        self.private_journal: List[str] = []
        self.private_diary: List[str] = []

        # --- Load and store the system prompt ---
        # Note: llm_utils.load_prompt_file defaults to looking in 'ai_diplomacy/prompts/'
        power_prompt_filename_only = f"{power_name.lower()}_system_prompt.txt"
        default_prompt_filename_only = "system_prompt.txt"

        system_prompt_content = llm_utils.load_prompt_file(power_prompt_filename_only)

        if not system_prompt_content:
            logger.warning(f"Power-specific prompt '{power_prompt_filename_only}' not found or empty. Loading default system prompt.")
            system_prompt_content = llm_utils.load_prompt_file(default_prompt_filename_only)
        else:
            logger.info(f"Loaded power-specific system prompt for {power_name}.")
        
        self.system_prompt: Optional[str] = system_prompt_content
        if not self.system_prompt:
            logger.error(f"Could not load default system prompt either! Agent {power_name} may not function correctly.")
        
        # Removed: Initialize the LLM interface for this agent
        # self.llm_interface = AgentLLMInterface(
        #     model_id=self.model_id,
        #     system_prompt=self.system_prompt,
        #     coordinator=_global_llm_coordinator,
        #     power_name=self.power_name
        # )
        
        logger.info(f"Initialized DiplomacyAgent for {self.power_name} with model_id {self.model_id} and goals: {self.goals}")
        self.add_journal_entry(f"Agent initialized with model {self.model_id}. Initial Goals: {self.goals}")

    # _extract_json_from_text and _clean_json_text have been moved to llm_utils.py

    def add_journal_entry(self, entry: str):
        """Adds a formatted entry string to the agent's private journal."""
        if not isinstance(entry, str):
            entry = str(entry)
        self.private_journal.append(entry)
        logger.debug(f"[{self.power_name} Journal]: {entry}")

    def add_diary_entry(self, entry: str, phase: str):
        """Adds a formatted entry string to the agent's private diary."""
        if not isinstance(entry, str):
            entry = str(entry)
        formatted_entry = f"[{phase}] {entry}"
        self.private_diary.append(formatted_entry)
        logger.info(f"[{self.power_name}] DIARY ENTRY ADDED for {phase}. Total entries: {len(self.private_diary)}. New entry: {entry[:100]}...")

    def format_private_diary_for_prompt(self, initial_max_entries_fallback=40) -> str:
        """
        Formats private diary entries for inclusion in a prompt, respecting a token budget.
        The diary (self.private_diary) may be trimmed if its estimated token count exceeds the budget.
        """
        logger.info(f"[{self.power_name}] Formatting diary. Max entries hint: {initial_max_entries_fallback}, Token budget: {self.game_config.max_diary_tokens}")

        if not self.private_diary:
            logger.warning(f"[{self.power_name}] No diary entries found.")
            return "(No diary entries yet)"

        # Start with a slice of the diary based on initial_max_entries_fallback
        # Ensure we don't go out of bounds if diary is shorter than initial_max_entries_fallback
        start_index = max(0, len(self.private_diary) - initial_max_entries_fallback)
        # Make a copy to work with, to decide what to keep from the original self.private_diary
        working_diary_entries = list(self.private_diary[start_index:]) 
        
        final_formatted_diary = ""
        final_kept_entries_for_prompt: List[str] = []


        while True:
            if not working_diary_entries:
                logger.warning(f"[{self.power_name}] Diary (working copy) became empty while trying to meet token budget {self.game_config.max_diary_tokens}.")
                final_formatted_diary = "(Diary empty after trimming for token budget)"
                final_kept_entries_for_prompt = []
                break

            current_formatted_diary = "\n".join(working_diary_entries)
            # Token estimation: characters / 3 (approximate)
            estimated_tokens = len(current_formatted_diary) / 3 

            if estimated_tokens <= self.game_config.max_diary_tokens:
                logger.info(f"[{self.power_name}] Diary token count ({estimated_tokens:.0f}) for {len(working_diary_entries)} entries is within budget ({self.game_config.max_diary_tokens}).")
                final_formatted_diary = current_formatted_diary
                final_kept_entries_for_prompt = list(working_diary_entries) # Store the version that fits
                break
            
            # If over budget, remove the oldest entry from our working list
            removed_entry = working_diary_entries.pop(0) # Remove from the front (oldest)
            logger.info(f"[{self.power_name}] Trimming diary for token budget. Approx tokens: {estimated_tokens:.0f}. Budget: {self.game_config.max_diary_tokens}. Removed oldest of {len(working_diary_entries)+1} entries: {removed_entry[:70]}...")
            
            if not working_diary_entries: # Check again if empty after pop
                 logger.warning(f"[{self.power_name}] Diary (working copy) became empty after last trim for token budget {self.game_config.max_diary_tokens}.")
                 final_formatted_diary = "(Diary empty after trimming for token budget)"
                 final_kept_entries_for_prompt = []
                 break
        
        # Update self.private_diary to reflect the entries that were actually used for the prompt AFTER trimming.
        # This means self.private_diary will now only contain final_kept_entries_for_prompt.
        original_diary_len = len(self.private_diary)
        
        # If final_kept_entries_for_prompt is shorter than the original self.private_diary, update it.
        # This effectively trims self.private_diary to only what was selected and token-budgeted.
        if len(final_kept_entries_for_prompt) < original_diary_len:
            self.private_diary = final_kept_entries_for_prompt
            logger.info(f"[{self.power_name}] Updated self.private_diary due to token budget trimming. Was {original_diary_len} entries, now {len(self.private_diary)}.")
        elif len(final_kept_entries_for_prompt) == original_diary_len and start_index > 0:
            # This means the initial slice based on initial_max_entries_fallback was used without further token trimming,
            # but this slice was shorter than the full diary. So, effectively, the diary was trimmed by initial_max_entries_fallback.
            self.private_diary = final_kept_entries_for_prompt # working_diary_entries was already a slice
            logger.info(f"[{self.power_name}] Updated self.private_diary based on initial_max_entries_fallback. Was {original_diary_len} entries, now {len(self.private_diary)}.")
        # If len(final_kept_entries_for_prompt) == original_diary_len and start_index == 0, no trimming happened.
        
        num_entries_in_prompt = len(final_kept_entries_for_prompt)
        logger.info(f"[{self.power_name}] Formatted {num_entries_in_prompt} diary entries for prompt. Preview: {final_formatted_diary[:200]}...")
        return final_formatted_diary
    
    async def consolidate_year_diary_entries(self, year: str, game: 'Game', log_file_path: str):
        """
        Consolidates all diary entries from a specific year into a concise summary.
        This is called when we're 2+ years past a given year to prevent context bloat.
        
        Args:
            year: The year to consolidate (e.g., "1901")
            game: The game object for context
            log_file_path: Path for logging LLM responses
        """
        logger.debug(f"[{self.power_name}] CONSOLIDATION CALLED for year {year}")
        logger.debug(f"[{self.power_name}] Current diary has {len(self.private_diary)} total entries")
        if self.private_diary:
            logger.debug(f"[{self.power_name}] Sample diary entries:")
            for i, entry in enumerate(self.private_diary[:3]):
                logger.debug(f"[{self.power_name}]   Entry {i}: {entry[:100]}...")
        
        # Find all diary entries from the specified year
        year_entries = []
        # Update pattern to match phase format: [S1901M], [F1901M], [W1901A] etc.
        # We need to check for [S1901, [F1901, [W1901
        patterns_to_check = [f"[S{year}", f"[F{year}", f"[W{year}"]
        logger.debug(f"[{self.power_name}] Looking for entries matching patterns: {patterns_to_check}")
        
        for i, entry in enumerate(self.private_diary):
            # Check if entry matches any of our patterns
            for pattern in patterns_to_check:
                if pattern in entry:
                    year_entries.append(entry)
                    logger.debug(f"[{self.power_name}] Found matching entry {i} with pattern '{pattern}': {entry[:50]}...")
                    break  # Don't add the same entry multiple times
        
        if not year_entries:
            logger.debug(f"[{self.power_name}] No diary entries found for year {year} using patterns: {patterns_to_check}")
            return
        
        logger.debug(f"[{self.power_name}] Found {len(year_entries)} entries to consolidate for year {year}")
        
        year_diary_text_for_prompt = "\n\n".join(year_entries)
        current_game_phase = game.current_short_phase if game else f"Consolidate-{year}"
        consolidated_entry = f"(Error: LLM call for diary consolidation failed for year {year})" # Default fallback

        try:
            prompt_text = prompt_utils.render_prompt(
                'diary_consolidation_prompt.j2', # Using .j2 extension now
                power_name=self.power_name,
                year=year,
                year_diary_entries=year_diary_text_for_prompt
            )
            logger.info(f"[{self.power_name}] Successfully rendered diary_consolidation_prompt.j2 template using Jinja2.")
        except FileNotFoundError as e:
            logger.error(f"[{self.power_name}] diary_consolidation_prompt.j2 template file not found: {e}.")
            consolidated_entry = f"(Error: Prompt template 'diary_consolidation_prompt.j2' not found for year {year})"
        except Exception as e: # Catch other Jinja2 rendering errors
            logger.error(f"[{self.power_name}] Error rendering diary_consolidation_prompt.j2 with Jinja2: {e}.")
            consolidated_entry = f"(Error: Could not render prompt for diary_consolidation for year {year}: {e})"
        else:
            # Proceed with LLM call only if prompt rendering was successful
            result: LLMCallResult = await _global_llm_coordinator.call_llm_with_json_parsing(
                model_id=self.model_id,
                prompt=prompt_text,
                system_prompt=self.system_prompt,
                request_identifier=f"{self.power_name}-diary_consolidation",
                expected_json_fields=None,  # Expecting raw text
                game_id=self.game_id,
                agent_name=self.power_name,
                phase_str=current_game_phase,
                log_to_file_path=log_file_path,
                response_type="diary_consolidation"
            )

            if result.success:
                consolidated_entry = result.raw_response.strip() if result.raw_response else ""
                if not consolidated_entry: # If LLM returned empty string
                    logger.warning(f"[{self.power_name}] Diary consolidation for {year} returned empty response.")
                    consolidated_entry = f"(LLM returned empty summary for {year} consolidation)"
            else:
                logger.error(f"[{self.power_name}] LLM call for diary consolidation for {year} failed: {result.error_message}")
                consolidated_entry = f"(Error: LLM call failed during diary consolidation for {year}: {result.error_message})"

        # Process the consolidated_entry (whether it's a success or an error/fallback message)
        if consolidated_entry and not consolidated_entry.startswith("(Error:") and not consolidated_entry.startswith("(LLM returned empty summary"):
            try:
                # Separate entries logic
                existing_consolidated = []
                entries_to_keep = []
                for existing_entry_item in self.private_diary: # Renamed to avoid conflict
                    if existing_entry_item.startswith("[CONSOLIDATED"):
                        existing_consolidated.append(existing_entry_item)
                    else:
                        is_from_consolidated_year = False
                        for pattern_to_check in patterns_to_check:
                            if pattern_to_check in existing_entry_item:
                                is_from_consolidated_year = True
                                break
                        if not is_from_consolidated_year:
                            entries_to_keep.append(existing_entry_item)
                
                new_consolidated_summary = f"[CONSOLIDATED {year}] {consolidated_entry.strip()}" # consolidated_entry is already stripped if successful
                existing_consolidated.append(new_consolidated_summary)
                # Sort consolidated entries by year (ascending) to keep historical order
                existing_consolidated.sort(key=lambda x: x[14:18], reverse=False) # Assuming format [CONSOLIDATED YYYY]
                
                self.private_diary = existing_consolidated + entries_to_keep
                logger.info(f"[{self.power_name}] Successfully processed diary consolidation for {year}. Consolidated {len(year_entries)} entries.")
            except Exception as e:
                 logger.error(f"[{self.power_name}] Error processing successfully generated consolidated diary entry for {year}: {e}", exc_info=True)
                 self.add_diary_entry(f"Raw successful consolidation for {year} (processing error): {consolidated_entry.strip()}", current_game_phase)
        else: # This 'else' now covers cases where consolidated_entry starts with "(Error:" or "(LLM returned empty summary"
            logger.warning(f"[{self.power_name}] Diary consolidation for {year} resulted in: {consolidated_entry}")
            self.add_diary_entry(f"Consolidation attempt for {year}: {consolidated_entry}", current_game_phase)


    async def generate_negotiation_diary_entry(self, game: 'Game', game_history: 'GameHistory', log_file_path: str):
        """
        Generates a diary entry summarizing negotiations and updates relationships.
        """
        logger.info(f"[{self.power_name}] Generating negotiation diary entry for {game.current_short_phase}..." )
        
        # Load the template
        prompt_template = llm_utils.load_prompt_file('negotiation_diary_prompt.txt')
        if not prompt_template:
            logger.error(f"[{self.power_name}] Could not load negotiation_diary_prompt.txt. Skipping diary entry.")
            return
        
        # Prepare context for the prompt (this logic remains largely the same)
        try:
            board_state_dict = game.get_state()
            board_state_str = f"Units: {board_state_dict.get('units', {})}, Centers: {board_state_dict.get('centers', {})}"
            
            messages_this_round = game_history.get_messages_this_round(
                power_name=self.power_name,
                current_phase_name=game.current_short_phase
            )
            if not messages_this_round.strip() or messages_this_round.startswith("\n(No messages"):
                messages_this_round = "(No messages involving your power this round that require deep reflection for diary. Focus on overall situation.)"
            
            current_relationships_str = str(self.relationships)
            current_goals_str = str(self.goals)
            formatted_diary = self.format_private_diary_for_prompt()
            
            ignored_messages = game_history.get_ignored_messages_by_power(self.power_name)
            ignored_context_parts = []
            if ignored_messages:
                ignored_context_parts.append("\n\nPOWERS NOT RESPONDING TO YOUR MESSAGES:")
                for power, msgs in ignored_messages.items():
                    ignored_context_parts.append(f"{power}:")
                    for msg_data in msgs[-2:]:
                        ignored_context_parts.append(f"  - Phase {msg_data['phase']}: {msg_data['content'][:100]}...")
            else:
                ignored_context_parts.append("\n\nAll powers have been responsive to your messages.")
            ignored_context = "\n".join(ignored_context_parts)

            # Create the prompt using the template
            prompt = prompt_template.format(
                power_name=self.power_name,
                current_phase=game.current_short_phase,
                board_state_str=board_state_str,
                messages_this_round=messages_this_round,
                agent_relationships=current_relationships_str,
                agent_goals=current_goals_str,
                allowed_relationships_str=", ".join(ALLOWED_RELATIONSHIPS),
                private_diary_summary=formatted_diary,
                ignored_messages_context=ignored_context
            )
            
            logger.debug(f"[{self.power_name}] Negotiation diary prompt:\n{prompt[:500]}...")

            # Use the new centralized LLM call approach
            result = await _global_llm_coordinator.call_llm_with_json_parsing(
                model_id=self.model_id,
                prompt=prompt,
                system_prompt=self.system_prompt,
                request_identifier=f"{self.power_name}-negotiation_diary",
                expected_json_fields=["negotiation_summary"],  # Main field we expect
                game_id=self.game_id,
                agent_name=self.power_name,
                phase_str=game.current_short_phase,
                log_to_file_path=log_file_path,
                response_type="negotiation_diary"
            )

            diary_entry_text = "(LLM diary entry generation or parsing failed.)" # Fallback
            relationships_updated = False

            if result.success and result.parsed_json:
                parsed_data = result.parsed_json
                
                # Fix 1: Be more robust about extracting the negotiation_summary field
                diary_text_candidate = None
                for key in ['negotiation_summary', 'summary', 'diary_entry']:
                    if key in parsed_data and isinstance(parsed_data[key], str) and parsed_data[key].strip():
                        diary_text_candidate = parsed_data[key].strip()
                        logger.info(f"[{self.power_name}] Successfully extracted '{key}' for diary.")
                        break
                        
                if diary_text_candidate:
                    diary_entry_text = diary_text_candidate
                else:
                    logger.warning(f"[{self.power_name}] Could not find valid summary field in diary response. Using fallback.")
                
                # Fix 2: Be more robust about extracting relationship updates
                new_relationships = llm_utils.extract_relationships(parsed_data)
                        
                if new_relationships is not None:
                    valid_new_rels = {}
                    for p, r in new_relationships.items():
                        p_upper = str(p).upper()
                        r_title = str(r).title()
                        if p_upper in ALL_POWERS and p_upper != self.power_name and r_title in ALLOWED_RELATIONSHIPS:
                            valid_new_rels[p_upper] = r_title
                        elif p_upper != self.power_name: # Log invalid relationship for a valid power
                            logger.warning(f"[{self.power_name}] Invalid relationship '{r}' for power '{p}' in diary update. Keeping old.")
                    
                    if valid_new_rels:
                        # Log changes before applying
                        for p_changed, new_r_val in valid_new_rels.items():
                            old_r_val = self.relationships.get(p_changed, "Unknown")
                            if old_r_val != new_r_val:
                                logger.info(f"[{self.power_name}] Relationship with {p_changed} changing from {old_r_val} to {new_r_val} based on diary.")
                        self.relationships.update(valid_new_rels)
                        relationships_updated = True
                    else:
                        logger.info(f"[{self.power_name}] No valid relationship updates found in diary response.")
                else:
                    logger.info(f"[{self.power_name}] No relationship updates found in diary response.")
            else:
                logger.warning(f"[{self.power_name}] Failed to generate negotiation diary: {result.error_message}")

            # Add the generated (or fallback) diary entry
            self.add_diary_entry(diary_entry_text, game.current_short_phase)
            if relationships_updated:
                self.add_journal_entry(f"[{game.current_short_phase}] Relationships updated after negotiation diary: {self.relationships}")

        except Exception as e:
            # Log the full exception details for better debugging
            logger.error(f"[{self.power_name}] Caught unexpected error in generate_negotiation_diary_entry: {type(e).__name__}: {e}", exc_info=True)
            # Add a fallback diary entry in case of general error
            self.add_diary_entry(f"(Error generating diary entry: {type(e).__name__})", game.current_short_phase)

    async def generate_order_diary_entry(self, game: 'Game', orders: List[str], log_file_path: str):
        """
        Generates a diary entry reflecting on the decided orders.
        """
        logger.info(f"[{self.power_name}] Generating order diary entry for {game.current_short_phase}...")
        
        board_state_dict = game.get_state()
        board_state_str = f"Units: {board_state_dict.get('units', {})}, Centers: {board_state_dict.get('centers', {})}"
        
        orders_list_str = "\n".join([f"- {o}" for o in orders]) if orders else "No orders submitted."
        
        goals_str = "\n".join([f"- {g}" for g in self.goals]) if self.goals else "None"
        relationships_str = "\n".join([f"- {p}: {s}" for p, s in self.relationships.items()]) if self.relationships else "None"
        
        try:
            prompt = prompt_utils.render_prompt(
                'order_diary_prompt.j2',  # Use the new .j2 extension
                power_name=self.power_name,
                current_phase=game.current_short_phase,
                orders_list_str=orders_list_str,
                board_state_str=board_state_str,
                agent_goals=goals_str,
                agent_relationships=relationships_str
            )
            logger.info(f"[{self.power_name}] Successfully rendered order diary prompt template using Jinja2.")
        except FileNotFoundError as e:
            logger.error(f"[{self.power_name}] Order diary prompt template file not found: {e}. Skipping diary entry.")
            fallback_diary_on_file_not_found = f"Submitted orders for {game.current_short_phase}: {', '.join(orders)}. (Internal error: Prompt template file not found)"
            self.add_diary_entry(fallback_diary_on_file_not_found, game.current_short_phase)
            return
        except Exception as e: # Catch other Jinja2 rendering errors
            logger.error(f"[{self.power_name}] Error rendering order diary template with Jinja2: {e}. Skipping diary entry.")
            # Add a fallback diary entry in case of prompt rendering error
            fallback_diary_on_render_error = f"Submitted orders for {game.current_short_phase}: {', '.join(orders)}. (Internal error: Could not render prompt: {e})"
            self.add_diary_entry(fallback_diary_on_render_error, game.current_short_phase)
            logger.warning(f"[{self.power_name}] Added fallback diary due to prompt rendering error.")
            return
        
        logger.debug(f"[{self.power_name}] Order diary prompt (first 300 chars):\n{prompt[:300]}...")

        # Use the new centralized LLM call wrapper
        result: LLMCallResult = await _global_llm_coordinator.call_llm_with_json_parsing(
            model_id=self.model_id,
            prompt=prompt,
            system_prompt=self.system_prompt,
            request_identifier=f"{self.power_name}-order_diary",
            expected_json_fields=["order_summary"],
            game_id=self.game_id,
            agent_name=self.power_name,
            phase_str=game.current_short_phase,
            log_to_file_path=log_file_path,
            response_type="order_diary"
        )

        if result.success:
            diary_text = result.get_field("order_summary")
            if diary_text and isinstance(diary_text, str) and diary_text.strip():
                self.add_diary_entry(diary_text, game.current_short_phase)
                logger.info(f"[{self.power_name}] Order diary entry generated and added.")
            else:
                # Success was true, but the field was missing or empty
                missing_field_msg = "LLM response successful but 'order_summary' field missing or empty."
                logger.warning(f"[{self.power_name}] {missing_field_msg}")
                fallback_diary = f"Submitted orders for {game.current_short_phase}: {', '.join(orders)}. ({missing_field_msg})"
                self.add_diary_entry(fallback_diary, game.current_short_phase)
        else:
            # Fallback if LLM call failed or returned invalid data
            error_message_for_log = result.error_message if result.error_message else "Unknown error during LLM call."
            fallback_diary = f"Submitted orders for {game.current_short_phase}: {', '.join(orders)}. (LLM failed to generate specific diary entry: {error_message_for_log})"
            self.add_diary_entry(fallback_diary, game.current_short_phase)
            logger.warning(f"[{self.power_name}] Failed to generate specific order diary entry. Added fallback. Error: {error_message_for_log}")

    async def generate_phase_result_diary_entry(
        self, 
        game: 'Game', 
        game_history: 'GameHistory',
        phase_summary: str,
        all_orders: Dict[str, List[str]],
        log_file_path: str
    ):
        """
        Generates a diary entry analyzing the actual phase results,
        comparing them to negotiations and identifying betrayals/collaborations.
        """
        logger.info(f"[{self.power_name}] Generating phase result diary entry for {game.current_short_phase}...")
        
        # Load the template
        prompt_template = llm_utils.load_prompt_file('phase_result_diary_prompt.txt')
        if not prompt_template:
            logger.error(f"[{self.power_name}] Could not load phase_result_diary_prompt.txt. Skipping diary entry.")
            return
        
        # Format all orders for the prompt
        all_orders_formatted = ""
        for power, orders in all_orders.items():
            orders_str = ", ".join(orders) if orders else "No orders"
            all_orders_formatted += f"{power}: {orders_str}\n"
        
        # Get your own orders
        your_orders = all_orders.get(self.power_name, [])
        your_orders_str = ", ".join(your_orders) if your_orders else "No orders"
        
        # Get recent negotiations for this phase
        messages_this_phase = game_history.get_messages_by_phase(game.current_short_phase)
        your_negotiations = ""
        for msg in messages_this_phase:
            if msg.sender == self.power_name:
                your_negotiations += f"To {msg.recipient}: {msg.content}\n"
            elif msg.recipient == self.power_name:
                your_negotiations += f"From {msg.sender}: {msg.content}\n"
        
        if not your_negotiations:
            your_negotiations = "No negotiations this phase"
        
        # Format relationships
        relationships_str = "\n".join([f"{p}: {r}" for p, r in self.relationships.items()])
        
        # Format goals
        goals_str = "\n".join([f"- {g}" for g in self.goals]) if self.goals else "None"
        
        # Create the prompt
        prompt = prompt_template.format(
            power_name=self.power_name,
            current_phase=game.current_short_phase,
            phase_summary=phase_summary,
            all_orders_formatted=all_orders_formatted,
            your_negotiations=your_negotiations,
            pre_phase_relationships=relationships_str,
            agent_goals=goals_str,
            your_actual_orders=your_orders_str
        )
        
        logger.debug(f"[{self.power_name}] Phase result diary prompt:\n{prompt[:500]}...")
        
        # Use the new centralized LLM call approach
        result = await _global_llm_coordinator.call_llm_with_json_parsing(
            model_id=self.model_id,
            prompt=prompt,
            system_prompt=self.system_prompt,
            request_identifier=f"{self.power_name}-phase_result_diary",
            expected_json_fields=None,  # This might return plain text or JSON
            game_id=self.game_id,
            agent_name=self.power_name,
            phase_str=game.current_short_phase,
            log_to_file_path=log_file_path,
            response_type="phase_result_diary"
        )

        if result.success and result.raw_response.strip():
            diary_entry = result.raw_response.strip()
            self.add_diary_entry(diary_entry, game.current_short_phase)
            logger.info(f"[{self.power_name}] Phase result diary entry generated and added.")
        else:
            fallback_diary = f"Phase {game.current_short_phase} completed. Orders executed as: {your_orders_str}. (Failed to generate detailed analysis: {result.error_message})"
            self.add_diary_entry(fallback_diary, game.current_short_phase)
            logger.warning(f"[{self.power_name}] Failed to generate phase result diary. Added fallback. Error: {result.error_message}")

    def log_state(self, prefix=""):
        logger.debug(f"[{self.power_name}] {prefix} State: Goals={self.goals}, Relationships={self.relationships}")

    # Make this method async
    async def analyze_phase_and_update_state(self, game: 'Game', board_state: dict, phase_summary: str, game_history: 'GameHistory', log_file_path: str):
        """Analyzes the outcome of the last phase and updates goals/relationships using the LLM."""
        power_name = self.power_name 
        current_phase = game.get_current_phase()
        logger.info(f"[{power_name}] Analyzing phase {current_phase} outcome to update state...")
        self.log_state(f"Before State Update ({current_phase})")

        try:
            # 1. Construct the prompt using the dedicated state update prompt file
            prompt_template = llm_utils.load_prompt_file('state_update_prompt.txt')
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
            
            # Get formatted diary for context
            formatted_diary = self.format_private_diary_for_prompt()

            # The variable 'context' was assigned but not used. build_context_prompt is called for its side effects or future use.
            # If it has no side effects relevant here and its return is truly unused, the call itself could be removed,
            # but for now, just removing the assignment to an unused variable is safer.
            # For this pass, we assume build_context_prompt might have logging or other side effects,
            # so we keep the call but not the assignment if 'context' is not used.
            # Upon review, build_context_prompt appears to be a pure function constructing text.
            # If `context` is not used, the call to `build_context_prompt` is also dead code here.
            # However, the instruction is "Remove such unused variables", not "remove calls that assign to unused variables".
            # So, if `context` is not used, I will remove its assignment.
            # Let me re-verify if `context` is used. It is not used.
            # The instructions also say "Prioritize obvious cases. If unsure, it's safer to leave it."
            # Removing the call to `build_context_prompt` might be too aggressive if its output was intended
            # to be part of `prompt` later, but was missed.
            # For now, I will remove the assignment `context =`, but leave the call if it was `_ = build_context_prompt(...)`
            # or if the function call itself might have side effects (though unlikely for a prompt builder).
            # The original code was `context = build_context_prompt(...)`.
            # The variable `context` is not used in the rest of the function.
            # I will remove the assignment and the call, as it's a prompt builder and its result is unused.
            # build_context_prompt(  # Call removed as its result 'context' is unused
            #     game=game,
            #     board_state=board_state,
            #     power_name=power_name,
            #     possible_orders=possible_orders,
            #     game_history=game_history,
            #     agent_goals=self.goals,
            #     agent_relationships=self.relationships,
            #     agent_private_diary=formatted_diary,
            # )

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
                other_powers=str(other_powers),
                current_goals="\n".join([f"- {g}" for g in self.goals]) if self.goals else "None",
                current_relationships=str(self.relationships) if self.relationships else "None"
            )
            logger.debug(f"[{power_name}] State update prompt:\n{prompt}")

            # Use the new centralized LLM call approach
            result = await _global_llm_coordinator.call_llm_with_json_parsing(
                model_id=self.model_id,
                prompt=prompt,
                system_prompt=self.system_prompt,
                request_identifier=f"{power_name}-state_update",
                expected_json_fields=["reasoning", "relationships", "goals"],
                game_id=self.game_id,
                agent_name=power_name,
                phase_str=current_phase,
                log_to_file_path=log_file_path,
                response_type="state_update"
            )

            if result.success and result.parsed_json:
                update_data = result.parsed_json
                
                # Use the helper functions to extract goals and relationships
                extracted_goals = llm_utils.extract_goals(update_data)
                extracted_relationships = llm_utils.extract_relationships(update_data)
                
                if extracted_goals is not None:
                    self.goals = extracted_goals
                    self.add_journal_entry(f"[{game.current_short_phase}] Goals updated based on {last_phase_name}: {self.goals}")
                else:
                    logger.warning(f"[{power_name}] LLM did not provide valid goals in state update. Current goals remain: {self.goals}")

                if extracted_relationships is not None:
                    valid_new_relationships = {}
                    invalid_count = 0
                    for p, r_status in extracted_relationships.items():
                        p_upper = str(p).upper()
                        if p_upper in ALL_POWERS and p_upper != power_name:
                            r_title = str(r_status).title() if isinstance(r_status, str) else r_status
                            if r_title in ALLOWED_RELATIONSHIPS:
                                valid_new_relationships[p_upper] = r_title
                            else:
                                invalid_count += 1
                                if invalid_count <= 2: logger.warning(f"[{power_name}] Received invalid relationship label '{r_status}' for '{p}'. Ignoring.")
                        elif p_upper != self.power_name: # Avoid logging self as invalid
                            invalid_count += 1
                            if invalid_count <= 2: logger.warning(f"[{power_name}] Received relationship for invalid/own power '{p}'. Ignoring.")
                    if invalid_count > 2: logger.warning(f"[{power_name}] {invalid_count} total invalid relationships were ignored.")
                    
                    if valid_new_relationships:
                        self.relationships.update(valid_new_relationships)
                        self.add_journal_entry(f"[{game.current_short_phase}] Relationships updated based on {last_phase_name}: {valid_new_relationships}")
                    elif extracted_relationships: 
                        logger.warning(f"[{power_name}] Found relationships in LLM response but none were valid after normalization. Current relationships remain: {self.relationships}")
                else:
                    logger.warning(f"[{power_name}] LLM did not provide valid relationships in state update. Current relationships remain: {self.relationships}")
            else:
                logger.warning(f"[{power_name}] State update failed: {result.error_message}")

        except FileNotFoundError:
            logger.error(f"[{power_name}] state_update_prompt.txt not found. Skipping state update.")
        except Exception as e:
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
        summary = f"Agent State for {self.power_name} (Model: {self.model_id}):\n" # Added model_id
        summary += f"  Goals: {self.goals}\n"
        summary += f"  Relationships: {self.relationships}\n"
        summary += f"  Journal Entries: {len(self.private_journal)}"
        return summary

    async def generate_plan(self, game: 'Game', game_history: 'GameHistory', log_file_path: str) -> str:
        """Generates a strategic plan using the llm library and logs it."""
        logger.info(f"Agent {self.power_name} (model: {self.model_id}) generating strategic plan for phase {game.current_short_phase}...")
        
        prompt_template = llm_utils.load_prompt_file('planning_prompt.txt') # Assuming a generic planning prompt
        if not prompt_template:
            logger.error(f"[{self.power_name}] Could not load planning_prompt.txt. Cannot generate plan.")
            return "Error: Planning prompt file not found."

        board_state = game.get_state()
        possible_orders_for_context = {} # For planning, detailed orders might not be needed for context

        # Re-use build_context_prompt if it's suitable for planning context
        context_prompt_text = build_context_prompt(
            game,
            board_state,
            self.power_name,
            possible_orders_for_context, 
            game_history,
            agent_goals=self.goals,
            agent_relationships=self.relationships,
            agent_private_diary=self.format_private_diary_for_prompt(),
        )
        
        full_prompt = f"{context_prompt_text}\n\n{prompt_template}"

        # Use the new centralized LLM call wrapper (no JSON parsing expected for plans)
        result = await _global_llm_coordinator.call_llm_with_json_parsing(
            model_id=self.model_id,
            prompt=full_prompt,
            system_prompt=self.system_prompt,
            request_identifier=f"{self.power_name}-plan_generation",
            expected_json_fields=None,  # No JSON expected for planning
            game_id=self.game_id,
            agent_name=self.power_name,
            phase_str=game.current_short_phase,
            log_to_file_path=log_file_path,
            response_type="plan_generation"
        )

        if result.success and result.raw_response.strip():
            plan_text = result.raw_response.strip()
            self.add_journal_entry(f"Generated plan for phase {game.current_short_phase}:\n{plan_text[:200]}...") # Log a preview
            return plan_text
        else:
            error_msg = f"Error: Failed to generate plan for {self.power_name} - {result.error_message}"
            self.add_journal_entry(f"Failed to generate plan for phase {game.current_short_phase}: {result.error_message}")
            return error_msg

    async def generate_messages(
        self,
        game: 'Game',
        board_state: dict,
        possible_orders: Dict[str, List[str]], # For context, might not be directly used in prompt
        game_history: 'GameHistory',
        current_phase: str,
        log_file_path: str,
        active_powers: List[str],
        # agent_goals, agent_relationships, agent_private_diary_str are available via self
    ) -> List[Dict[str, str]]:
        """
        Generates messages to send to other powers during negotiations.
        """
        logger.info(f"[{self.power_name}] Generating messages for phase {current_phase}...")

        prompt_template_conversation = llm_utils.load_prompt_file('conversation_instructions.txt')
        if not prompt_template_conversation:
            logger.error(f"[{self.power_name}] Could not load conversation_instructions.txt. Cannot generate messages.")
            return []

        # Prepare context for the main prompt
        context_prompt_text = build_context_prompt(
            game=game,
            board_state=board_state,
            power_name=self.power_name,
            possible_orders=possible_orders,
            game_history=game_history,
            agent_goals=self.goals,
            agent_relationships=self.relationships,
            agent_private_diary=self.format_private_diary_for_prompt(),
        )

        # Create the full prompt
        active_powers_str = ", ".join([p for p in active_powers if p != self.power_name])
        
        negotiation_context_enhancement = (
            f"\n\n--- Negotiation Context ---\n"
            f"You are {self.power_name}.\n"
            f"Other active powers you can negotiate with: {active_powers_str}.\n"
            f"Previous messages and game state are provided above.\n"
            f"Your current goals: {self.goals}\n"
            f"Your current relationships: {self.relationships}\n"
            f"Review your private diary for reflections and plans.\n"
            f"--- End Negotiation Context ---\n\n"
        )

        full_prompt = (
            context_prompt_text +
            negotiation_context_enhancement +
            prompt_template_conversation
        )

        # Use the new centralized LLM call approach
        result = await _global_llm_coordinator.call_llm_with_json_parsing(
            model_id=self.model_id,
            prompt=full_prompt,
            system_prompt=self.system_prompt,
            request_identifier=f"{self.power_name}-message_generation",
            expected_json_fields=None,  # Messages can have various formats
            game_id=self.game_id,
            agent_name=self.power_name,
            phase_str=current_phase,
            log_to_file_path=log_file_path,
            response_type="message_generation"
        )

        extracted_messages: List[Dict[str, str]] = []

        if result.success and result.raw_response.strip():
            # Try to extract messages from the response
            parsed_data = result.parsed_json if result.parsed_json else {}
            
            if isinstance(parsed_data, dict) and "messages" in parsed_data and isinstance(parsed_data["messages"], list):
                extracted_messages = parsed_data["messages"]
            elif isinstance(parsed_data, list):
                # If LLM directly returns a list of messages
                extracted_messages = parsed_data
            else:
                logger.warning(f"[{self.power_name}] Unexpected message format in LLM response")
                
            # Validate message structure
            valid_messages = []
            for msg in extracted_messages:
                if isinstance(msg, dict) and "message_type" in msg and "content" in msg:
                    # For private messages, ensure recipient is specified
                    if msg.get("message_type") == "private" and "recipient" in msg:
                        valid_messages.append(msg)
                    elif msg.get("message_type") == "global":
                        valid_messages.append(msg)
                    else:
                        logger.warning(f"[{self.power_name}] Invalid message structure: {msg}")
                else:
                    logger.warning(f"[{self.power_name}] Invalid message format: {msg}")
            
            extracted_messages = valid_messages
            logger.info(f"[{self.power_name}] Extracted {len(extracted_messages)} valid messages.")
        else:
            logger.warning(f"[{self.power_name}] Failed to generate messages: {result.error_message}")
        
        return extracted_messages