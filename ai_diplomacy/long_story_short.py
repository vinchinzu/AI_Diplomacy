import logging
import re
import os
import time
from typing import Dict, List, Optional, Tuple, Any

# Establish logger
logger = logging.getLogger(__name__)

# Import model client for summarization
from ai_diplomacy.model_loader import load_model_client

# Token counting approximation
def count_tokens(text: str) -> int:
    """
    Approximates token count for text. This is a rough estimate.
    OpenAI tokens are ~4 chars per token on average.
    """
    return len(text) // 4  # Simple approximation


class ContextManager:
    """
    Manages context size for Diplomacy game history and messages.
    Provides power-specific recursive summarization functionality 
    when context exceeds thresholds.
    """
    def __init__(
        self, 
        phase_token_threshold: int = 5000,
        message_token_threshold: int = 5000,
        summary_model: str = "o3-mini"
    ):
        self.phase_token_threshold = phase_token_threshold
        self.message_token_threshold = message_token_threshold
        self.summary_model = summary_model
        
        # Per-power tracking of summary states
        self.power_summary_states = {}  # Indexed by power_name
        
        # Shared phase summary state (phases are globally visible)
        self.phase_summary_state = {
            'last_summary': None,      # The most recent summary of older phases
            'summarized_phases': [],   # List of phase names that have been summarized
            'last_summary_time': 0,    # When we last summarized
        }
        
        # Cooldown period (seconds) - don't summarize more frequently than this
        self.summary_cooldown = 300  # 5 minutes
        
        logger.debug(f"CONTEXT | Initialized manager with thresholds: phase={phase_token_threshold}, message={message_token_threshold}")
    
    def get_power_state(self, power_name):
        """
        Gets or initializes the summary state for a specific power.
        """
        if power_name not in self.power_summary_states:
            self.power_summary_states[power_name] = {
                'last_message_summary': None,  # The most recent message summary
                'summarized_messages': set(),  # Set of message IDs that have been summarized
                'last_summary_time': 0,        # When we last summarized messages for this power
            }
        return self.power_summary_states[power_name]
    
    def load_summarization_prompts(self) -> Tuple[str, str, str]:
        """
        Load prompts for phase, message, and recursive summarization.
        Returns tuple of (phase_prompt, message_prompt, recursive_prompt)
        """
        try:
            # Try to load from files
            with open("./ai_diplomacy/prompts/phase_summary_prompt.txt", "r") as f:
                phase_prompt = f.read().strip()
            
            with open("./ai_diplomacy/prompts/message_summary_prompt.txt", "r") as f:
                message_prompt = f.read().strip()
                
            with open("./ai_diplomacy/prompts/recursive_summary_prompt.txt", "r") as f:
                recursive_prompt = f.read().strip()
                
            logger.debug("CONTEXT | Loaded summarization prompts from files")
            return phase_prompt, message_prompt, recursive_prompt
        except FileNotFoundError:
            # Return default prompts if files not found
            logger.warning("CONTEXT | Summarization prompt files not found, using default templates")
            
            phase_prompt = """You are summarizing the history of a Diplomacy game. 
Create a concise summary that preserves all strategically relevant information about:
1. Supply center changes
2. Unit movements and their results 
3. Key battles and their outcomes
4. Territory control shifts

Focus on what actually happened, not explanations or justifications.
Maintain the chronological structure but condense verbose descriptions.
Use clear, factual language with specific location names.

ORIGINAL PHASE HISTORY:
{phase_history}

SUMMARY:"""

            message_prompt = """You are summarizing diplomatic messages in a Diplomacy game.
Create a concise summary of the conversations between powers that preserves:
1. Agreements and alliances formed
2. Betrayals and broken promises
3. Strategic intentions revealed 
4. Explicit threats or support offered
5. Key relationships between each power

Organize by relationships (e.g., FRANCE-GERMANY, ENGLAND-RUSSIA), prioritizing the most 
significant interactions. Include specific territory names mentioned.

The summary must reflect the actual diplomatic landscape accurately so players can make informed decisions.

ORIGINAL MESSAGE HISTORY:
{message_history}

SUMMARY:"""

            recursive_prompt = """You are creating a recursive summary of a Diplomacy game's history.
You have a previous summary of earlier events/messages and new content to incorporate.

Your task is to create a unified, seamless summary that:
1. Preserves key strategic information from both sources
2. Maintains chronological flow and logical structure
3. Presents the most relevant information for decision-making
4. Emphasizes developments in alliances, betrayals, and territorial control

PREVIOUS SUMMARY:
{previous_summary}

NEW CONTENT:
{new_content}

Create a unified summary that reads as a single coherent narrative while preserving critical strategic information:"""
            
            return phase_prompt, message_prompt, recursive_prompt
    
    def generate_recursive_summary(self, previous_summary, new_content, prompt_type="recursive", power_name=None):
        """
        Generates a recursive summary by combining previous summary with new content.
        
        Args:
            previous_summary: Previous summary text
            new_content: New content to be incorporated
            prompt_type: Type of prompt to use (recursive, phase, or message)
            power_name: Name of the power for context
            
        Returns:
            A new summary incorporating both previous and new content
        """
        # Load appropriate prompt
        phase_prompt, message_prompt, recursive_prompt = self.load_summarization_prompts()
        
        if prompt_type == "phase" and not previous_summary:
            # Initial phase summary
            prompt = phase_prompt.replace("{phase_history}", new_content)
            logger.debug(f"CONTEXT | SUMMARY | Creating initial phase summary with {len(new_content)} characters")
        elif prompt_type == "message" and not previous_summary:
            # Initial message summary
            prompt = message_prompt.replace("{message_history}", new_content)
            logger.debug(f"CONTEXT | SUMMARY | Creating initial message summary for {power_name} with {len(new_content)} characters")
        else:
            # Recursive summary (or phase/message with previous summary)
            prompt = recursive_prompt
            prompt = prompt.replace("{previous_summary}", previous_summary or "(No previous summary)")
            prompt = prompt.replace("{new_content}", new_content)
            logger.debug(f"CONTEXT | SUMMARY | Creating recursive {prompt_type} summary for {power_name or 'game'}")
            logger.debug(f"CONTEXT | SUMMARY | Previous summary: {len(previous_summary or '')} chars, New content: {len(new_content)} chars")
        
        # Get the summary using the LLM
        summarization_client = load_model_client(self.summary_model, power_name=power_name, emptysystem=True)
        summary = summarization_client.generate_response(prompt)
        
        logger.debug(f"CONTEXT | Generated {prompt_type} recursive summary ({len(summary)} chars)")
        return summary
    
    def should_summarize_phases(self, phase_summaries: Dict[str, str]) -> bool:
        """
        Determine if phase summaries need to be condensed based on token count,
        cooldown period, and new content since last summarization.
        """
        # Check if we're in cooldown period
        current_time = time.time()
        if current_time - self.phase_summary_state['last_summary_time'] < self.summary_cooldown:
            logger.debug("CONTEXT | Phase summarization skipped (in cooldown period)")
            return False
            
        # Get unsummarized phase content
        unsummarized_phase_names = [p for p in phase_summaries.keys() 
                                  if p not in self.phase_summary_state['summarized_phases']
                                  and not p.startswith("SUMMARY_UNTIL_")]
        
        # If we have a previous summary, count its tokens
        base_token_count = 0
        if self.phase_summary_state['last_summary']:
            base_token_count = count_tokens(self.phase_summary_state['last_summary'])
        
        # Count tokens in unsummarized phases
        unsummarized_text = "\n\n".join([phase_summaries[phase] for phase in unsummarized_phase_names])
        unsummarized_token_count = count_tokens(unsummarized_text)
        
        # Check if total exceeds threshold
        total_token_count = base_token_count + unsummarized_token_count
        should_summarize = total_token_count > self.phase_token_threshold
        
        if should_summarize:
            logger.debug(f"CONTEXT | Phase token count ({total_token_count}) exceeds threshold ({self.phase_token_threshold}), will summarize")
            logger.debug(f"CONTEXT | Phase breakdown: {base_token_count} tokens from previous summary + {unsummarized_token_count} tokens from {len(unsummarized_phase_names)} new phases")
        
        return should_summarize
    
    def should_summarize_messages(self, message_history: str, power_name: str) -> bool:
        """
        Determine if message history for a specific power needs to be condensed
        based on token count and cooldown period.
        """
        # Get power-specific state
        power_state = self.get_power_state(power_name)
        
        # Check if we're in cooldown period
        current_time = time.time()
        if current_time - power_state['last_summary_time'] < self.summary_cooldown:
            logger.debug(f"CONTEXT | Message summarization for {power_name} skipped (in cooldown period)")
            return False
            
        # If we have a previous summary, count its tokens
        base_token_count = 0
        if power_state['last_message_summary']:
            base_token_count = count_tokens(power_state['last_message_summary'])
        
        # Count tokens in the new content
        new_token_count = count_tokens(message_history)
        
        # Check if total exceeds threshold
        total_token_count = base_token_count + new_token_count
        should_summarize = total_token_count > self.message_token_threshold
        
        if should_summarize:
            logger.debug(f"CONTEXT | Message token count for {power_name} ({total_token_count}) exceeds threshold ({self.message_token_threshold}), will summarize")
            logger.debug(f"CONTEXT | Message breakdown for {power_name}: {base_token_count} tokens from previous summary + {new_token_count} tokens from new messages")
            
        return should_summarize
    
    def summarize_phase_history(self, phase_summaries: Dict[str, str], power_name: Optional[str] = None) -> Dict[str, str]:
        """
        Create a recursively updated summary of phase history.
        Keeps recent phases intact and summarizes older ones.
        
        Returns a new dictionary with condensed history.
        """
        if not self.should_summarize_phases(phase_summaries):
            return phase_summaries
            
        # Mark summarization time
        self.phase_summary_state['last_summary_time'] = time.time()
        
        # Sort phases chronologically 
        sorted_phases = sorted(phase_summaries.keys())
        
        # Get unsummarized phase names
        unsummarized_phase_names = [p for p in sorted_phases 
                                  if p not in self.phase_summary_state['summarized_phases']
                                  and not p.startswith("SUMMARY_UNTIL_")]
        
        # Keep the 3 most recent phases intact
        recent_phases = unsummarized_phase_names[-3:] if len(unsummarized_phase_names) > 3 else unsummarized_phase_names
        phases_to_summarize = [p for p in unsummarized_phase_names if p not in recent_phases]
        
        if not phases_to_summarize:
            logger.debug("CONTEXT | No new phases to summarize")
            return phase_summaries  # Nothing to summarize
        
        # Text to summarize: previous summary + new phases to summarize
        previous_summary = self.phase_summary_state['last_summary'] or ""
        
        new_content = ""
        for phase in phases_to_summarize:
            new_content += f"PHASE {phase}:\n{phase_summaries[phase]}\n\n"
        
        # Log before summarization
        logger.info(f"CONTEXT | PHASE SUMMARIZATION | Starting recursive summarization for {len(phases_to_summarize)} phases")
        logger.info(f"CONTEXT | PHASE SUMMARIZATION | Phases being summarized: {', '.join(phases_to_summarize)}")
        
        # Generate recursive summary
        if previous_summary:
            # We have a previous summary, do recursive summarization
            logger.debug(f"CONTEXT | PHASE SUMMARIZATION | Performing recursive summarization with previous summary ({len(previous_summary)} chars)")
            summary = self.generate_recursive_summary(
                previous_summary, 
                new_content,
                prompt_type="recursive", 
                power_name=power_name
            )
        else:
            # No previous summary, do initial summarization
            logger.debug(f"CONTEXT | PHASE SUMMARIZATION | Performing initial phase summarization ({len(new_content)} chars)")
            summary = self.generate_recursive_summary(
                None,
                new_content,
                prompt_type="phase",
                power_name=power_name
            )
        
        # Update phase summary state
        self.phase_summary_state['last_summary'] = summary
        self.phase_summary_state['summarized_phases'].extend(phases_to_summarize)
        
        # Create new dictionary with summarized older phases and intact recent phases
        result = {}
        
        # Add the summary as a special entry
        if phases_to_summarize:
            last_summarized = max(phases_to_summarize)
            summary_key = f"SUMMARY_UNTIL_{last_summarized}"
            result[summary_key] = summary
            logger.info(f"CONTEXT | PHASE SUMMARIZATION | Created summary key '{summary_key}' ({len(summary)} chars)")
        
        # Add the recent phases as-is
        for phase in recent_phases:
            result[phase] = phase_summaries[phase]
        
        logger.info(f"CONTEXT | PHASE SUMMARIZATION | Recursively condensed {len(phase_summaries)} phase entries to {len(result)}")
        logger.debug(f"CONTEXT | PHASE SUMMARIZATION | Result contains summary + {len(recent_phases)} intact recent phases")
        return result
    
    def summarize_message_history(
        self, 
        message_history: str, 
        power_name: str,
        organized_by_relationship: bool = True
    ) -> str:
        """
        Create a recursively updated summary of message history for a specific power.
        
        Args:
            message_history: Current unsummarized message history
            power_name: The power whose history is being summarized
            organized_by_relationship: If True, assumes messages are organized by relationship
            
        Returns:
            Updated message history with recursive summarization applied
        """
        if not self.should_summarize_messages(message_history, power_name):
            return message_history
            
        # Get power-specific state
        power_state = self.get_power_state(power_name)
        
        # Mark summarization time
        power_state['last_summary_time'] = time.time()
        
        # Log before summarization
        logger.info(f"CONTEXT | MESSAGE SUMMARIZATION | Starting message summarization for {power_name}")
        logger.info(f"CONTEXT | MESSAGE SUMMARIZATION | Current message history size: {len(message_history)} chars")
        
        # Generate recursive summary
        previous_summary = power_state['last_message_summary']
        
        if previous_summary:
            # We have a previous summary, do recursive summarization
            logger.debug(f"CONTEXT | MESSAGE SUMMARIZATION | Performing recursive message summarization for {power_name}")
            logger.debug(f"CONTEXT | MESSAGE SUMMARIZATION | Previous summary: {len(previous_summary)} chars, New messages: {len(message_history)} chars")
            
            summary = self.generate_recursive_summary(
                previous_summary,
                message_history,
                prompt_type="recursive",
                power_name=power_name
            )
        else:
            # No previous summary, do initial summarization
            logger.debug(f"CONTEXT | MESSAGE SUMMARIZATION | Performing initial message summarization for {power_name} ({len(message_history)} chars)")
            
            summary = self.generate_recursive_summary(
                None,
                message_history,
                prompt_type="message",
                power_name=power_name
            )
        
        # Update power state
        power_state['last_message_summary'] = summary
        
        # Track metrics for logging
        message_tokens = count_tokens(message_history)
        summary_tokens = count_tokens(summary)
        reduction = 100 - (summary_tokens * 100 / message_tokens) if message_tokens > 0 else 0
        
        logger.info(f"CONTEXT | MESSAGE SUMMARIZATION | Completed for {power_name}: {message_tokens} → {summary_tokens} tokens ({reduction:.1f}% reduction)")
        logger.debug(f"CONTEXT | MESSAGE SUMMARIZATION | Original size: {len(message_history)} chars, Summary size: {len(summary)} chars")
        
        return summary
    
    def get_optimized_phase_summaries(
        self, 
        game, 
        power_name: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Main access point for getting optimized phase summaries.
        If summaries are below threshold, returns original.
        Otherwise, returns recursively condensed version.
        """
        if not hasattr(game, "phase_summaries") or not game.phase_summaries:
            logger.debug("CONTEXT | No phase summaries available")
            return {}
            
        logger.debug(f"CONTEXT | Checking phase optimization for {power_name or 'game'} with {len(game.phase_summaries)} phases")
        
        if self.should_summarize_phases(game.phase_summaries):
            # Create condensed version using recursive summarization
            logger.debug(f"CONTEXT | Creating optimized phase summaries for {power_name or 'game'}")
            result = self.summarize_phase_history(game.phase_summaries, power_name)
            
            # Add a log showing which phases are included in the optimized version
            phase_keys = list(result.keys())
            summary_keys = [k for k in phase_keys if k.startswith("SUMMARY_UNTIL_")]
            regular_phases = [k for k in phase_keys if not k.startswith("SUMMARY_UNTIL_")]
            
            logger.info(f"CONTEXT | PHASE OPTIMIZATION | Returning {len(summary_keys)} summary entries and {len(regular_phases)} regular phases")
            if summary_keys:
                logger.debug(f"CONTEXT | PHASE OPTIMIZATION | Summary entries: {', '.join(summary_keys)}")
            if regular_phases:
                logger.debug(f"CONTEXT | PHASE OPTIMIZATION | Regular phases: {', '.join(regular_phases)}")
                
            return result
        else:
            # Return original
            logger.debug("CONTEXT | Using original phase summaries (below threshold)")
            return game.phase_summaries
    
    def get_optimized_message_history(
        self, 
        game_history, 
        power_name: Optional[str] = None,
        organized_history: Optional[str] = None
    ) -> str:
        """
        Main access point for getting optimized message history.
        
        Args:
            game_history: The GameHistory object
            power_name: The power requesting the history
            organized_history: Optional pre-organized history text
            
        Returns:
            Optimized message history as string
        """
        if not power_name:
            logger.warning("CONTEXT | No power_name provided for message history optimization, using raw history")
            return organized_history or (game_history.get_game_history() if hasattr(game_history, "get_game_history") else str(game_history))
        
        # Get the raw message history for this power
        if organized_history is not None:
            message_history = organized_history
        elif hasattr(game_history, "get_game_history"):
            message_history = game_history.get_game_history(power_name) or "(No history yet)"
        else:
            message_history = str(game_history) if game_history else "(No history yet)"
        
        if message_history == "(No history yet)":
            return message_history
        
        logger.debug(f"CONTEXT | Checking message optimization for {power_name} with {len(message_history)} chars")
        
        # Check if we need to create a recursive summary
        if self.should_summarize_messages(message_history, power_name):
            # Create recursively condensed version
            logger.debug(f"CONTEXT | Creating optimized message history for {power_name}")
            result = self.summarize_message_history(message_history, power_name)
            
            # Log the optimization stats
            power_state = self.get_power_state(power_name)
            has_previous_summary = power_state['last_message_summary'] is not None
            
            logger.info(f"CONTEXT | MESSAGE OPTIMIZATION | {power_name} | Original size: {len(message_history)} chars, Optimized size: {len(result)} chars")
            logger.info(f"CONTEXT | MESSAGE OPTIMIZATION | {power_name} | Using {'recursive' if has_previous_summary else 'initial'} message summary")
            
            return result
        else:
            # Return original
            logger.debug(f"CONTEXT | Using original message history for {power_name} (below threshold)")
            return message_history


# Global context manager instance
# This can be configured at startup
context_manager = ContextManager()

def configure_context_manager(
    phase_threshold: int = 5000,
    message_threshold: int = 5000,
    summary_model: str = "o3-mini"
) -> None:
    """
    Configure the global context manager.
    Should be called early in the application lifecycle.
    """
    global context_manager
    logger.info(f"CONTEXT | Configuring manager with thresholds: phase={phase_threshold}, message={message_threshold}, model={summary_model}")
    context_manager = ContextManager(
        phase_token_threshold=phase_threshold,
        message_token_threshold=message_threshold,
        summary_model=summary_model
    )

def get_optimized_context(
    game,
    game_history,
    power_name: Optional[str] = None,
    organized_history: Optional[str] = None
) -> Tuple[Dict[str, str], str]:
    """
    Convenience function to get both optimized phase summaries and message history.
    
    Returns:
        Tuple of (optimized_phase_summaries, optimized_message_history)
    """
    logger.debug(f"CONTEXT | Getting optimized context for {power_name or 'game'}")
    
    optimized_phases = context_manager.get_optimized_phase_summaries(game, power_name)
    optimized_messages = context_manager.get_optimized_message_history(
        game_history, power_name, organized_history
    )
    
    # Add a log entry showing what we're returning for tracking
    phase_count = len(optimized_phases) if optimized_phases else 0
    message_length = len(optimized_messages) if optimized_messages else 0
    summary_count = len([k for k in optimized_phases.keys() if k.startswith("SUMMARY_UNTIL_")]) if optimized_phases else 0
    
    logger.info(f"CONTEXT | OPTIMIZATION RESULT | {power_name or 'game'} | Returning {phase_count} phases ({summary_count} summaries) and {message_length} chars of messages")
    
    return optimized_phases, optimized_messages