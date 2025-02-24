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
    Provides summarization functionality when context exceeds thresholds.
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
        
        # Cache for summaries - prevents regenerating summaries unnecessarily
        self.phase_summary_cache = {}
        self.message_summary_cache = {}
        
        # Track when we last generated summaries
        self.last_phase_summary_time = 0
        self.last_message_summary_time = 0
        
        # Cooldown period (seconds) - don't summarize more frequently than this
        self.summary_cooldown = 300  # 5 minutes
    
    def load_summarization_prompts(self) -> Tuple[str, str]:
        """
        Load prompts for phase and message summarization.
        Returns tuple of (phase_prompt, message_prompt)
        """
        try:
            # Try to load from files
            with open("./ai_diplomacy/prompts/phase_summary_prompt.txt", "r") as f:
                phase_prompt = f.read().strip()
            
            with open("./ai_diplomacy/prompts/message_summary_prompt.txt", "r") as f:
                message_prompt = f.read().strip()
                
            return phase_prompt, message_prompt
        except FileNotFoundError:
            # Return default prompts if files not found
            logger.warning("Summarization prompt files not found. Using defaults.")
            
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
            
            return phase_prompt, message_prompt
    
    def should_summarize_phases(self, phase_summaries: Dict[str, str]) -> bool:
        """
        Determine if phase summaries need to be condensed based on token count
        and cooldown period.
        """
        # Check if we're in cooldown period
        current_time = time.time()
        if current_time - self.last_phase_summary_time < self.summary_cooldown:
            return False
            
        # Join all summaries to count total tokens
        all_text = "\n\n".join(phase_summaries.values())
        token_count = count_tokens(all_text)
        
        return token_count > self.phase_token_threshold
    
    def should_summarize_messages(self, message_history: str) -> bool:
        """
        Determine if message history needs to be condensed based on token count
        and cooldown period.
        """
        # Check if we're in cooldown period
        current_time = time.time()
        if current_time - self.last_message_summary_time < self.summary_cooldown:
            return False
            
        token_count = count_tokens(message_history)
        return token_count > self.message_token_threshold
    
    def summarize_phase_history(self, phase_summaries: Dict[str, str], power_name: Optional[str] = None) -> Dict[str, str]:
        """
        Create a condensed version of phase summaries.
        Keeps the most recent phases intact and summarizes older ones.
        
        Returns a new dictionary with condensed history.
        """
        if not self.should_summarize_phases(phase_summaries):
            return phase_summaries
            
        # Mark summarization time
        self.last_phase_summary_time = time.time()
        
        # Sort phases chronologically
        sorted_phases = sorted(phase_summaries.keys())
        
        # Keep the 3 most recent phases intact
        recent_phases = sorted_phases[-3:] if len(sorted_phases) > 3 else sorted_phases
        older_phases = sorted_phases[:-3] if len(sorted_phases) > 3 else []
        
        if not older_phases:
            return phase_summaries  # Nothing to summarize
        
        # Get summarization prompt
        phase_prompt, _ = self.load_summarization_prompts()
        
        # Generate a summary of the older phases
        older_text = ""
        for phase in older_phases:
            older_text += f"PHASE {phase}:\n{phase_summaries[phase]}\n\n"
        
        # Check if we already have a cached summary for this exact text
        if older_text in self.phase_summary_cache:
            summary = self.phase_summary_cache[older_text]
        else:
            # Generate new summary
            summarization_client = load_model_client(self.summary_model, power_name=power_name, emptysystem=True)
            formatted_prompt = phase_prompt.replace("{phase_history}", older_text)
            summary = summarization_client.generate_response(formatted_prompt)
            
            # Cache the result
            self.phase_summary_cache[older_text] = summary
        
        # Create new dictionary with summarized older phases and intact recent phases
        result = {}
        
        # Add the summary as a special entry
        summary_key = f"SUMMARY_UNTIL_{older_phases[-1]}"
        result[summary_key] = summary
        
        # Add the recent phases as-is
        for phase in recent_phases:
            result[phase] = phase_summaries[phase]
            
        return result
    
    def summarize_message_history(
        self, 
        message_history: str, 
        power_name: Optional[str] = None,
        organized_by_relationship: bool = True
    ) -> str:
        """
        Create a condensed version of message history.
        If organized_by_relationship is True, assumes the history is already 
        organized by power relationships.
        
        Returns a condensed message history.
        """
        if not self.should_summarize_messages(message_history):
            return message_history
            
        # Mark summarization time
        self.last_message_summary_time = time.time()
        
        # Get summarization prompt
        _, message_prompt = self.load_summarization_prompts()
        
        # Check if we already have a cached summary for this exact text
        if message_history in self.message_summary_cache:
            return self.message_summary_cache[message_history]
            
        # Generate new summary
        summarization_client = load_model_client(self.summary_model, power_name=power_name, emptysystem=True)
        formatted_prompt = message_prompt.replace("{message_history}", message_history)
        summary = summarization_client.generate_response(formatted_prompt)
        
        # Cache the result
        self.message_summary_cache[message_history] = summary
        
        return summary
    
    def get_optimized_phase_summaries(
        self, 
        game, 
        power_name: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Main access point for getting optimized phase summaries.
        If summaries are below threshold, returns original.
        Otherwise, returns condensed version.
        """
        if not hasattr(game, "phase_summaries") or not game.phase_summaries:
            return {}
            
        if self.should_summarize_phases(game.phase_summaries):
            # Create condensed version
            return self.summarize_phase_history(game.phase_summaries, power_name)
        else:
            # Return original
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
        # Get the raw message history
        if organized_history is not None:
            message_history = organized_history
        elif hasattr(game_history, "get_game_history"):
            message_history = game_history.get_game_history(power_name) or "(No history yet)"
        else:
            message_history = str(game_history) if game_history else "(No history yet)"
        
        if self.should_summarize_messages(message_history):
            # Create condensed version
            return self.summarize_message_history(message_history, power_name)
        else:
            # Return original
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
    optimized_phases = context_manager.get_optimized_phase_summaries(game, power_name)
    optimized_messages = context_manager.get_optimized_message_history(
        game_history, power_name, organized_history
    )
    
    return optimized_phases, optimized_messages