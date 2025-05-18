#!/usr/bin/env python3
"""
Quick test of the game analyzer on a specific phase
"""

import asyncio
import json
from analyze_game_moments import GameAnalyzer

async def test_single_phase():
    """Test analysis on a single phase to verify everything works"""
    
    # Path to test game
    game_path = "/Users/alxdfy/Documents/mldev/AI_Diplomacy/results/20250515_005239_francewin_25pro/lmvsgame.json"
    
    # Initialize analyzer
    analyzer = GameAnalyzer(game_path)
    await analyzer.initialize()
    
    # Get a specific phase to test (Spring 1901)
    test_phase = analyzer.game_data["phases"][0]  # First phase
    
    print(f"Testing on phase: {test_phase.get('name', 'Unknown')}")
    print(f"Number of messages: {len(test_phase.get('messages', []))}")
    print(f"Number of powers with orders: {len(test_phase.get('orders', {}))}")
    
    # Run analysis
    moments = await analyzer.analyze_turn(test_phase)
    
    print(f"\nFound {len(moments)} moments")
    for moment in moments:
        print(f"- {moment.category}: {', '.join(moment.powers_involved)} (Score: {moment.interest_score})")
        print(f"  Promise: {moment.promise_agreement[:100]}...")
        print(f"  Reality: {moment.actual_action[:100]}...")
        print()
    
    return moments

if __name__ == "__main__":
    moments = asyncio.run(test_single_phase())
    print("Test complete!")