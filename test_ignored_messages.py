#!/usr/bin/env python3
"""Test script to verify ignored message tracking functionality."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from ai_diplomacy.game_history import GameHistory, Phase

def test_ignored_messages_tracking():
    """Test the ignored messages tracking functionality."""
    print("Testing ignored message tracking...")
    
    # Create a game history instance
    game_history = GameHistory()
    
    # Add some test phases with messages
    phase1 = Phase("S1901M")
    # Convert Message objects to dicts as used in the system
    phase1.messages = [
        {"sender": "ENGLAND", "recipient": "FRANCE", "content": "Want to work together on Belgium?"},
        {"sender": "ENGLAND", "recipient": "RUSSIA", "content": "Let's discuss the Baltic."},
        {"sender": "FRANCE", "recipient": "GLOBAL", "content": "Peace for all!"},  # No response to England
        {"sender": "ENGLAND", "recipient": "GERMANY", "content": "Interested in Denmark cooperation?"},
    ]
    game_history.phases.append(phase1)
    
    phase2 = Phase("F1901M")
    phase2.messages = [
        {"sender": "ENGLAND", "recipient": "FRANCE", "content": "You didn't reply about Belgium?"},
        {"sender": "RUSSIA", "recipient": "ENGLAND", "content": "Baltic cooperation sounds good."},  # Response to England
        {"sender": "GERMANY", "recipient": "ENGLAND", "content": "Yes, Denmark interests me too."},  # Germany responds
    ]
    game_history.phases.append(phase2)
    
    phase3 = Phase("S1902M")
    phase3.messages = [
        {"sender": "FRANCE", "recipient": "ITALY", "content": "Focus on Austria?"},  # Still no response to England
    ]
    game_history.phases.append(phase3)
    
    # Test ignored messages for ENGLAND
    ignored = game_history.get_ignored_messages_by_power("ENGLAND", num_phases=3)
    
    print(f"\nIgnored messages for ENGLAND: {ignored}")
    
    # Verify results
    assert "FRANCE" in ignored, "FRANCE should be in ignored powers"
    assert "RUSSIA" not in ignored, "RUSSIA should NOT be in ignored powers (they responded)"
    assert "GERMANY" not in ignored, "GERMANY should NOT be in ignored powers (they responded)"
    assert len(ignored["FRANCE"]) == 2, "Should have 2 ignored messages from ENGLAND to FRANCE"
    
    print("✅ Ignored message tracking test passed!")
    return True

if __name__ == "__main__":
    print("Ignored Messages Tracking Test")
    print("============================\n")
    
    success = test_ignored_messages_tracking()
    
    print("\n============================")
    if success:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")
    
    sys.exit(0 if success else 1)