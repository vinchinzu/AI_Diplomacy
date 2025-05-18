# Improve Negotiation Awareness - Experiment

## Analysis Date: May 18, 2025

## Issue Identified
Powers don't modify their messaging strategies when other powers aren't responding to them. The system already tracks messages to powers, but doesn't explicitly note when outgoing messages are being ignored.

## Solution Plan
1. Add a method to track which powers are not responding to messages
2. Include this information in the negotiation diary prompt
3. Add examples showing how to adapt strategies when ignored

## Implementation Strategy
- Minimal changes to avoid breaking working system
- Add unanswered message tracking to negotiation diary generation
- Update prompts to include awareness of non-responsive powers

## Files to Modify
1. `ai_diplomacy/game_history.py` - Add method to track ignored messages
2. `ai_diplomacy/prompts/negotiation_diary_prompt.txt` - Add awareness of non-responsive powers
3. `ai_diplomacy/agent.py` - Include ignored messages in diary context

## Changes to Implement

### Step 1: Add tracking method to game_history.py ✓ COMPLETE
Added `get_ignored_messages_by_power()` method that:
- Tracks which powers don't respond to private messages
- Looks for responses in current and next phase
- Returns a dict mapping power names to their ignored messages

### Step 2: Update negotiation diary prompt ✓ COMPLETE
- Added ignored messages context to the prompt
- Added task item to note non-responsive powers
- Added strategic guidance for handling silence
- Added example scenario showing adaptation to ignored messages

### Step 3: Update agent.py ✓ COMPLETE
- Added ignored messages tracking in `generate_negotiation_diary_entry()`
- Included ignored context in template variables
- Added preprocessing for the new template variable

### Step 4: Update conversation instructions ✓ COMPLETE
- Added consideration for powers ignoring messages
- Added strategic guidance for dealing with non-responsive powers

## Summary of Changes
1. Added `get_ignored_messages_by_power()` method to `game_history.py`
2. Updated `negotiation_diary_prompt.txt` with ignored messages context and example
3. Modified `agent.py` to track and include ignored messages in diary generation
4. Enhanced `conversation_instructions.txt` with guidance for non-responsive powers

## Technical Implementation
The system now:
- Tracks when private messages go unanswered
- Provides context about which powers are ignoring messages
- Gives strategic guidance on adapting diplomatic approaches
- Includes examples of adjusting strategy based on silence
- Handles both Message objects and dictionary representations

All changes were minimal and surgical to avoid breaking the working system.

## Bug Fix
Fixed TypeError where the method was trying to subscript Message objects as dictionaries. The method now handles both Message objects (used in actual game) and dictionaries (used in tests).