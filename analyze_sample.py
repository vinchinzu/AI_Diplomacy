#!/usr/bin/env python3
"""
Quick sample analysis of the first 10 phases
"""

import asyncio
import json
from analyze_game_moments import GameAnalyzer

async def main():
    # Path to game file
    game_path = "/Users/alxdfy/Documents/mldev/AI_Diplomacy/results/20250515_005239_francewin_25pro/lmvsgame.json"
    
    # Initialize analyzer
    analyzer = GameAnalyzer(game_path)
    await analyzer.initialize()
    
    # Analyze only first 10 phases
    phases = analyzer.game_data.get("phases", [])[:10]
    
    print(f"Analyzing first {len(phases)} phases...")
    
    for i, phase_data in enumerate(phases):
        phase_name = phase_data.get("name", f"Phase {i}")
        print(f"Analyzing phase {phase_name} ({i+1}/{len(phases)})")
        
        moments = await analyzer.analyze_turn(phase_data)
        analyzer.moments.extend(moments)
        
        # Small delay to avoid rate limiting
        await asyncio.sleep(0.5)
    
    # Sort moments by interest score
    analyzer.moments.sort(key=lambda m: m.interest_score, reverse=True)
    
    print(f"\nFound {len(analyzer.moments)} key moments")
    
    # Generate report
    analyzer.generate_report("sample_report.md")
    analyzer.save_json_results("sample_moments.json")
    
    # Show top 5 moments
    print("\nTop 5 Most Interesting Moments:")
    for i, moment in enumerate(analyzer.moments[:5], 1):
        print(f"{i}. {moment.category} in {moment.phase} (Score: {moment.interest_score})")
        print(f"   Powers: {', '.join(moment.powers_involved)}")
        print(f"   {moment.promise_agreement[:100]}...")
        print()

if __name__ == "__main__":
    asyncio.run(main())