#!/usr/bin/env python3
"""
Analyze Key Game Moments: Betrayals, Collaborations, and Playing Both Sides

This script analyzes Diplomacy game data to identify the most interesting strategic moments.
"""

import json
import asyncio
import argparse
import logging
import ast
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import os
from dotenv import load_dotenv

# Import the client from ai_diplomacy module
from ai_diplomacy.clients import load_model_client

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class GameMoment:
    """Represents a key moment in the game"""
    phase: str
    category: str  # BETRAYAL, COLLABORATION, PLAYING_BOTH_SIDES
    powers_involved: List[str]
    promise_agreement: str
    actual_action: str
    impact: str
    interest_score: float
    raw_messages: List[Dict]
    raw_orders: Dict

class GameAnalyzer:
    """Analyzes Diplomacy game data for key strategic moments"""
    
    def __init__(self, game_data_path: str, model_name: str = "openrouter-google/gemini-2.5-flash-preview"):
        self.game_data_path = Path(game_data_path)
        self.model_name = model_name
        self.client = None
        self.game_data = None
        self.moments = []
        
    async def initialize(self):
        """Initialize the analyzer with game data and model client"""
        # Load game data
        with open(self.game_data_path, 'r') as f:
            self.game_data = json.load(f)
        
        # Initialize model client
        self.client = load_model_client(self.model_name)
        logger.info(f"Initialized with model: {self.model_name}")
        
    def extract_turn_data(self, phase_data: Dict) -> Dict:
        """Extract relevant data from a single turn/phase"""
        return {
            "phase": phase_data.get("name", ""),
            "messages": phase_data.get("messages", []),
            "orders": phase_data.get("orders", {}),
            "summary": phase_data.get("summary", ""),
            "statistical_summary": phase_data.get("statistical_summary", {})
        }
    
    def create_analysis_prompt(self, turn_data: Dict) -> str:
        """Create the analysis prompt for a single turn"""
        # Format messages for analysis
        formatted_messages = []
        for msg in turn_data.get("messages", []):
            formatted_messages.append(
                f"{msg.get('sender', 'Unknown')} to {msg.get('recipient', 'Unknown')}: "
                f"{msg.get('message', '')}"
            )
        
        # Format orders for analysis
        formatted_orders = []
        for power, power_orders in turn_data.get("orders", {}).items():
            formatted_orders.append(f"{power}: {power_orders}")
        
        prompt = f"""You are analyzing diplomatic negotiations and subsequent military orders from a Diplomacy game. Your task is to identify key strategic moments in the following categories:

1. BETRAYAL: When a power explicitly promises one action but takes a contradictory action
2. COLLABORATION: When powers successfully coordinate as agreed
3. PLAYING_BOTH_SIDES: When a power makes conflicting promises to different parties

For this turn ({turn_data.get('phase', '')}), analyze:

MESSAGES:
{chr(10).join(formatted_messages) if formatted_messages else 'No messages this turn'}

ORDERS:
{chr(10).join(formatted_orders) if formatted_orders else 'No orders this turn'}

TURN SUMMARY:
{turn_data.get('summary', 'No summary available')}

Identify ALL instances that fit the three categories. For each instance provide:
{{
    "category": "BETRAYAL" or "COLLABORATION" or "PLAYING_BOTH_SIDES",
    "powers_involved": ["POWER1", "POWER2", ...],
    "promise_agreement": "What was promised or agreed",
    "actual_action": "What actually happened",
    "impact": "Strategic impact on the game",
    "interest_score": 8.5  // 1-10 scale, how dramatic/interesting this moment is
}}

Return your response as a JSON array of detected moments. If no relevant moments are found, return an empty array [].

Focus on:
- Explicit promises vs actual orders
- Coordinated attacks or defenses
- DMZ violations
- Support promises kept or broken
- Conflicting negotiations with different powers
"""
        return prompt
    
    async def analyze_turn(self, phase_data: Dict) -> List[Dict]:
        """Analyze a single turn for key moments"""
        turn_data = self.extract_turn_data(phase_data)
        
        # Skip if no meaningful data
        if not turn_data["messages"] and not turn_data["orders"]:
            return []
        
        prompt = self.create_analysis_prompt(turn_data)
        
        try:
            response = await self.client.generate_response(prompt)
            
            # Parse JSON response
            # Handle potential code blocks or direct JSON
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            
            detected_moments = json.loads(response)
            
            # Enrich with raw data
            moments = []
            for moment in detected_moments:
                game_moment = GameMoment(
                    phase=turn_data["phase"],
                    category=moment.get("category", ""),
                    powers_involved=moment.get("powers_involved", []),
                    promise_agreement=moment.get("promise_agreement", ""),
                    actual_action=moment.get("actual_action", ""),
                    impact=moment.get("impact", ""),
                    interest_score=float(moment.get("interest_score", 5)),
                    raw_messages=turn_data["messages"],
                    raw_orders=turn_data["orders"]
                )
                moments.append(game_moment)
                logger.info(f"Detected {game_moment.category} in {game_moment.phase} "
                          f"(score: {game_moment.interest_score})")
            
            return moments
            
        except Exception as e:
            logger.error(f"Error analyzing turn {turn_data.get('phase', '')}: {e}")
            return []
    
    async def analyze_game(self):
        """Analyze the entire game for key moments"""
        phases = self.game_data.get("phases", [])
        
        logger.info(f"Analyzing {len(phases)} phases...")
        
        for i, phase_data in enumerate(phases):
            phase_name = phase_data.get("name", f"Phase {i}")
            logger.info(f"Analyzing phase {phase_name} ({i+1}/{len(phases)})")
            
            moments = await self.analyze_turn(phase_data)
            self.moments.extend(moments)
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.5)
        
        # Sort moments by interest score
        self.moments.sort(key=lambda m: m.interest_score, reverse=True)
        
        logger.info(f"Analysis complete. Found {len(self.moments)} key moments.")
    
    def generate_report(self, output_path: str = "game_moments_report.md"):
        """Generate a markdown report of key moments"""
        report_lines = [
            "# Diplomacy Game Analysis: Key Moments",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Game: {self.game_data_path}",
            "",
            "## Summary",
            f"- Total moments analyzed: {len(self.moments)}",
            f"- Betrayals: {len([m for m in self.moments if m.category == 'BETRAYAL'])}",
            f"- Collaborations: {len([m for m in self.moments if m.category == 'COLLABORATION'])}",
            f"- Playing Both Sides: {len([m for m in self.moments if m.category == 'PLAYING_BOTH_SIDES'])}",
            "",
            "## Top 10 Most Interesting Moments",
            ""
        ]
        
        # Add top moments
        for i, moment in enumerate(self.moments[:10], 1):
            report_lines.extend([
                f"### {i}. {moment.category} - {moment.phase} (Score: {moment.interest_score}/10)",
                f"**Powers Involved:** {', '.join(moment.powers_involved)}",
                "",
                f"**Promise/Agreement:** {moment.promise_agreement}",
                "",
                f"**Actual Action:** {moment.actual_action}",
                "",
                f"**Impact:** {moment.impact}",
                "",
                "---",
                ""
            ])
        
        # Add category breakdowns
        report_lines.extend([
            "## Category Breakdown",
            "",
            "### Betrayals",
            ""
        ])
        
        betrayals = [m for m in self.moments if m.category == "BETRAYAL"]
        for moment in betrayals[:5]:
            report_lines.append(
                f"- **{moment.phase}** ({', '.join(moment.powers_involved)}): "
                f"{moment.promise_agreement[:100]}... Score: {moment.interest_score}"
            )
        
        report_lines.extend(["", "### Collaborations", ""])
        
        collaborations = [m for m in self.moments if m.category == "COLLABORATION"]
        for moment in collaborations[:5]:
            report_lines.append(
                f"- **{moment.phase}** ({', '.join(moment.powers_involved)}): "
                f"{moment.promise_agreement[:100]}... Score: {moment.interest_score}"
            )
        
        report_lines.extend(["", "### Playing Both Sides", ""])
        
        playing_both = [m for m in self.moments if m.category == "PLAYING_BOTH_SIDES"]
        for moment in playing_both[:5]:
            report_lines.append(
                f"- **{moment.phase}** ({', '.join(moment.powers_involved)}): "
                f"{moment.promise_agreement[:100]}... Score: {moment.interest_score}"
            )
        
        # Write report
        with open(output_path, 'w') as f:
            f.write('\n'.join(report_lines))
        
        logger.info(f"Report generated: {output_path}")
    
    def save_json_results(self, output_path: str = "game_moments.json"):
        """Save all moments as JSON for further analysis"""
        moments_data = []
        for moment in self.moments:
            moment_dict = asdict(moment)
            # Remove raw data for cleaner JSON
            moment_dict.pop('raw_messages', None)
            moment_dict.pop('raw_orders', None)
            moments_data.append(moment_dict)
        
        with open(output_path, 'w') as f:
            json.dump(moments_data, f, indent=2)
        
        logger.info(f"JSON results saved: {output_path}")

async def main():
    parser = argparse.ArgumentParser(description="Analyze Diplomacy game for key strategic moments")
    parser.add_argument("game_file", help="Path to lmvsgame.json file")
    parser.add_argument("--model", default="openrouter-google/gemini-2.5-flash-preview",
                        help="Model to use for analysis")
    parser.add_argument("--report", default="game_moments_report.md",
                        help="Output path for markdown report")
    parser.add_argument("--json", default="game_moments.json",
                        help="Output path for JSON results")
    
    args = parser.parse_args()
    
    analyzer = GameAnalyzer(args.game_file, args.model)
    
    try:
        await analyzer.initialize()
        await analyzer.analyze_game()
        analyzer.generate_report(args.report)
        analyzer.save_json_results(args.json)
        
        # Print summary
        print(f"\nAnalysis Complete!")
        print(f"Found {len(analyzer.moments)} key moments")
        print(f"Report saved to: {args.report}")
        print(f"JSON data saved to: {args.json}")
        
        # Show top 3 moments
        print("\nTop 3 Most Interesting Moments:")
        for i, moment in enumerate(analyzer.moments[:3], 1):
            print(f"{i}. {moment.category} in {moment.phase} (Score: {moment.interest_score})")
            print(f"   Powers: {', '.join(moment.powers_involved)}")
            print(f"   Impact: {moment.impact[:100]}...")
            print()
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())