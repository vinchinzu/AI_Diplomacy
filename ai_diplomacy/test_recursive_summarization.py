#!/usr/bin/env python3
"""
Test script to validate the recursive summarization functionality in long_story_short.py
"""

import os
import sys
import logging
import time
from typing import Dict

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("test_summarization")

# Add the parent directory to the path so we can import the module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the module we want to test
from ai_diplomacy.long_story_short import (
    ContextManager, 
    configure_context_manager,
    get_optimized_context
)

def test_phase_summarization():
    """
    Test the recursive phase summarization functionality
    """
    logger.info("Testing phase summarization...")
    
    # Create a context manager with a very low threshold to force summarization
    cm = ContextManager(
        phase_token_threshold=200,  # Very low to trigger summarization
        message_token_threshold=1000,
        summary_model="o3-mini"  # Use a simple model for testing
    )
    
    # Create a mock game object with phase summaries
    mock_game = type('MockGame', (), {})()
    mock_game.phase_summaries = {
        "S1901M": "Spring 1901 Movement: France moved to Burgundy. Germany attacked Paris but was repelled. Russia and Turkey formed an alliance against Austria.",
        "F1901M": "Fall 1901 Movement: England took Norway. Russia captured Sweden. Italy moved into Tyrolia threatening Vienna.",
        "W1901A": "Winter 1901 Adjustments: France built F Brest. England built F London. Russia built A Moscow.",
        "S1902M": "Spring 1902 Movement: Germany attacked Burgundy with support from Munich. Italy took Vienna from Austria. Turkey moved into Armenia threatening Russia."
    }
    
    # Get optimized summaries
    optimized_phases = cm.get_optimized_phase_summaries(mock_game, power_name="FRANCE")
    
    # Print the result
    logger.info(f"Original phases: {len(mock_game.phase_summaries)}")
    logger.info(f"Optimized phases: {len(optimized_phases)}")
    
    # Now add more phases to trigger another round of summarization
    mock_game.phase_summaries.update({
        "F1902M": "Fall 1902 Movement: France retook Burgundy. England invaded St. Petersburg. Austria was eliminated by combined Italian and Turkish forces.",
        "W1902A": "Winter 1902 Adjustments: Russia disbanded A Warsaw. Italy built A Rome and F Naples. Turkey built F Smyrna.",
        "S1903M": "Spring 1903 Movement: Germany and France formed an alliance against England. Russia's position in the north collapsed."
    })
    
    # Get optimized summaries again - should see recursive summarization
    new_optimized_phases = cm.get_optimized_phase_summaries(mock_game, power_name="FRANCE")
    
    logger.info(f"Updated original phases: {len(mock_game.phase_summaries)}")
    logger.info(f"New optimized phases: {len(new_optimized_phases)}")
    
    # Print summary content
    for key, summary in new_optimized_phases.items():
        if key.startswith("SUMMARY_UNTIL_"):
            logger.info(f"=== {key} ===")
            logger.info(summary[:200] + "..." if len(summary) > 200 else summary)
    
    # Add a third batch to trigger recursive summarization of the previous summary
    mock_game.phase_summaries.update({
        "F1903M": "Fall 1903 Movement: Italy captured Tunis. France took Belgium with German support. England lost Edinburgh to a combined Russian and German attack.",
        "W1903A": "Winter 1903 Adjustments: England disbanded F London. France built A Paris. Germany built F Kiel.",
        "S1904M": "Spring 1904 Movement: Turkey attacked Italy in the Ionian Sea. Russia and Germany continued their assault on England. France moved towards Spain."
    })
    
    # Get optimized summaries a third time - should see further recursive summarization
    final_optimized_phases = cm.get_optimized_phase_summaries(mock_game, power_name="FRANCE")
    
    logger.info(f"Final original phases: {len(mock_game.phase_summaries)}")
    logger.info(f"Final optimized phases: {len(final_optimized_phases)}")
    
    # Print final summary content
    for key, summary in final_optimized_phases.items():
        if key.startswith("SUMMARY_UNTIL_"):
            logger.info(f"=== {key} ===")
            logger.info(summary[:200] + "..." if len(summary) > 200 else summary)
    
    return optimized_phases, new_optimized_phases, final_optimized_phases

def test_message_summarization():
    """
    Test the power-specific message summarization functionality
    """
    logger.info("Testing message summarization...")
    
    # Create a context manager with a very low threshold to force summarization
    cm = ContextManager(
        phase_token_threshold=1000,
        message_token_threshold=200,  # Very low to trigger summarization
        summary_model="o3-mini"  # Use a simple model for testing
    )
    
    # Test with multiple powers
    powers = ["FRANCE", "GERMANY", "ENGLAND"]
    
    # Create mock message histories for each power
    messages = {
        "FRANCE": "FROM: FRANCE, TO: GERMANY\nI propose we ally against England. I'll support your move to Belgium if you don't move to Burgundy.\n\nFROM: GERMANY, TO: FRANCE\nAgreed. I won't move to Burgundy. Let's coordinate against England.\n\nFROM: ENGLAND, TO: GLOBAL\nI'm looking for allies against France. Any takers?",
        "GERMANY": "FROM: FRANCE, TO: GERMANY\nI propose we ally against England. I'll support your move to Belgium if you don't move to Burgundy.\n\nFROM: GERMANY, TO: FRANCE\nAgreed. I won't move to Burgundy. Let's coordinate against England.\n\nFROM: GERMANY, TO: RUSSIA\nI suggest we avoid conflict in Sweden and focus on other directions.",
        "ENGLAND": "FROM: ENGLAND, TO: GLOBAL\nI'm looking for allies against France. Any takers?\n\nFROM: RUSSIA, TO: ENGLAND\nI could support you against France if you help me with Germany.\n\nFROM: ENGLAND, TO: RUSSIA\nThat works for me. I'll help you take Denmark if you support me into the English Channel."
    }
    
    # Test for each power
    results = {}
    for power in powers:
        logger.info(f"Testing message summarization for {power}...")
        
        # Get optimized message history for this power
        optimized_messages = cm.get_optimized_message_history(messages[power], power)
        
        logger.info(f"Original message length: {len(messages[power])}")
        logger.info(f"Optimized message length: {len(optimized_messages)}")
        
        # Now add more messages to trigger recursive summarization
        additional_messages = f"\n\nFROM: {power}, TO: GLOBAL\nI declare that I am focusing on defense this turn.\n\nFROM: ITALY, TO: {power}\nI propose a mutual non-aggression pact."
        combined_messages = additional_messages * 3  # Multiply to ensure we exceed threshold
        
        # Get optimized messages again with the combined content
        new_optimized_messages = cm.get_optimized_message_history(
            optimized_messages + combined_messages, 
            power
        )
        
        logger.info(f"Updated original + new message length: {len(optimized_messages + combined_messages)}")
        logger.info(f"Recursive optimized message length: {len(new_optimized_messages)}")
        
        # Add a third batch to trigger recursive summarization of the previous summary
        more_messages = f"\n\nFROM: TURKEY, TO: {power}\nI suggest we coordinate our moves in the Mediterranean.\n\nFROM: {power}, TO: TURKEY\nI agree to non-aggression in the Mediterranean. Let's focus on other targets."
        third_combined = more_messages * 4  # Multiply to ensure we exceed threshold again
        
        final_optimized_messages = cm.get_optimized_message_history(
            new_optimized_messages + third_combined,
            power
        )
        
        logger.info(f"Final combined message length: {len(new_optimized_messages + third_combined)}")
        logger.info(f"Final optimized message length: {len(final_optimized_messages)}")
        
        results[power] = (optimized_messages, new_optimized_messages, final_optimized_messages)
    
    return results

def test_with_game_integration():
    """
    Test using the get_optimized_context function which is what the game actually uses
    """
    logger.info("Testing integration with game context...")
    
    # Configure the global context manager with very low thresholds
    configure_context_manager(
        phase_threshold=200,  
        message_threshold=200,
        summary_model="o3-mini"
    )
    
    # Create a mock game object with phase summaries
    mock_game = type('MockGame', (), {})()
    mock_game.phase_summaries = {
        "S1901M": "Spring 1901 Movement: France moved to Burgundy. Germany attacked Paris but was repelled.",
        "F1901M": "Fall 1901 Movement: England took Norway. Russia captured Sweden.",
        "W1901A": "Winter 1901 Adjustments: France built F Brest. England built F London.",
        "S1902M": "Spring 1902 Movement: Germany attacked Burgundy with support from Munich."
    }
    
    # Create mock message histories 
    mock_messages = {
        "FRANCE": "FROM: FRANCE, TO: GERMANY\nI propose we ally against England.\n\nFROM: GERMANY, TO: FRANCE\nAgreed. Let's coordinate against England.",
        "GERMANY": "FROM: FRANCE, TO: GERMANY\nI propose we ally against England.\n\nFROM: GERMANY, TO: FRANCE\nAgreed. Let's coordinate against England.",
    }
    
    # Create a mock game history object
    class MockGameHistory:
        def get_game_history(self, power_name=None):
            if power_name:
                return mock_messages.get(power_name, "")
            return ""
    
    mock_history = MockGameHistory()
    
    # Test for multiple powers
    for power in ["FRANCE", "GERMANY"]:
        logger.info(f"Testing integration for {power}...")
        
        # First call - should be under threshold
        optimized_phases, optimized_messages = get_optimized_context(
            mock_game, mock_history, power_name=power
        )
        
        logger.info(f"{power} initial optimized_phases count: {len(optimized_phases)}")
        logger.info(f"{power} initial optimized_messages length: {len(optimized_messages)}")
        
        # Add more content to exceed thresholds
        mock_game.phase_summaries.update({
            "F1902M": "Fall 1902 Movement: France retook Burgundy. England invaded St. Petersburg.",
            "W1902A": "Winter 1902 Adjustments: Russia disbanded A Warsaw. Italy built A Rome.",
            "S1903M": "Spring 1903 Movement: Germany and France formed an alliance against England."
        })
        
        # Update message history
        additional_msg = f"\n\nFROM: {power}, TO: GLOBAL\nI declare that I am focusing on defense this turn." * 3
        mock_messages[power] += additional_msg
        
        # Second call - should trigger summarization
        optimized_phases2, optimized_messages2 = get_optimized_context(
            mock_game, mock_history, power_name=power
        )
        
        logger.info(f"{power} second optimized_phases count: {len(optimized_phases2)}")
        if len(optimized_phases2) < len(mock_game.phase_summaries):
            logger.info(f"✅ {power} phase summarization successful!")
        else:
            logger.warning(f"❌ {power} phase summarization did not occur as expected")
            
        logger.info(f"{power} second optimized_messages length: {len(optimized_messages2)}")
        if len(optimized_messages2) < len(mock_messages[power]):
            logger.info(f"✅ {power} message summarization successful!")
        else:
            logger.warning(f"❌ {power} message summarization did not occur as expected")
    
    return True

def main():
    """
    Main test function
    """
    logger.info("Starting recursive summarization tests...")
    
    # Test phase summarization
    phase_test_results = test_phase_summarization()
    
    # Test message summarization
    message_test_results = test_message_summarization()
    
    # Test integration with game context
    integration_result = test_with_game_integration()
    
    logger.info("All tests completed!")
    
    # Final validation checks
    # Check if we're getting different summaries for different powers (should be!)
    message_summaries = {power: result[1] for power, result in message_test_results.items()}
    unique_summaries = set(message_summaries.values())
    
    logger.info(f"Number of powers tested: {len(message_summaries)}")
    logger.info(f"Number of unique message summaries: {len(unique_summaries)}")
    
    if len(unique_summaries) == len(message_summaries):
        logger.info("✅ SUCCESS: Each power has a unique message summary!")
    else:
        logger.warning("❌ FAILURE: Some powers have identical message summaries!")

if __name__ == "__main__":
    main() 