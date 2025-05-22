#!/usr/bin/env python3
"""
Analyze Key Game Moments: Betrayals, Collaborations, and Playing Both Sides

This script analyzes Diplomacy game data to identify the most interesting strategic moments.
Enhanced with:
- More stringent rating criteria
- Integration of power diary entries for better context
- Analysis of well-executed strategies and strategic mistakes
"""

import json
import asyncio
import argparse
import logging
import csv
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
    category: str  # BETRAYAL, COLLABORATION, PLAYING_BOTH_SIDES, BRILLIANT_STRATEGY, STRATEGIC_BLUNDER
    powers_involved: List[str]
    promise_agreement: str
    actual_action: str
    impact: str
    interest_score: float
    raw_messages: List[Dict]
    raw_orders: Dict
    diary_context: Dict[str, str]  # New field for diary entries

class GameAnalyzer:
    """Analyzes Diplomacy game data for key strategic moments"""
    
    def __init__(self, results_folder: str, model_name: str = "openrouter-google/gemini-2.5-flash-preview"):
        self.results_folder = Path(results_folder)
        self.game_data_path = self.results_folder / "lmvsgame.json"
        self.overview_path = self.results_folder / "overview.jsonl"
        self.csv_path = self.results_folder / "llm_responses.csv"
        self.model_name = model_name
        self.client = None
        self.game_data = None
        self.power_to_model = None
        self.moments = []
        self.diary_entries = {}  # phase -> power -> diary content
        self.invalid_moves_by_model = {} # Initialize attribute
        
    async def initialize(self):
        """Initialize the analyzer with game data and model client"""
        # Load game data
        with open(self.game_data_path, 'r') as f:
            self.game_data = json.load(f)
        
        # Load power-to-model mapping from overview.jsonl
        with open(self.overview_path, 'r') as f:
            lines = f.readlines()
            # Second line contains the power-to-model mapping
            if len(lines) >= 2:
                self.power_to_model = json.loads(lines[1])
                logger.info(f"Loaded power-to-model mapping: {self.power_to_model}")
            else:
                logger.warning("Could not find power-to-model mapping in overview.jsonl")
                self.power_to_model = {}
        
        # Load diary entries from CSV
        self.diary_entries = self.parse_llm_responses_csv()
        logger.info(f"Loaded diary entries for {len(self.diary_entries)} phases")
        
        # Load invalid moves data from CSV
        self.invalid_moves_by_model = self.parse_invalid_moves_from_csv()
        logger.info(f"Loaded invalid moves for {len(self.invalid_moves_by_model)} models")
        
        # Initialize model client
        self.client = load_model_client(self.model_name)
        logger.info(f"Initialized with model: {self.model_name}")
    
    def parse_llm_responses_csv(self) -> Dict[str, Dict[str, str]]:
        """Parse the CSV file to extract diary entries by phase and power"""
        diary_entries = {}
        
        try:
            import pandas as pd
            # Use pandas for more robust CSV parsing
            df = pd.read_csv(self.csv_path)
            
            # Filter for negotiation diary entries
            diary_df = df[df['response_type'] == 'negotiation_diary']
            
            for _, row in diary_df.iterrows():
                phase = row['phase']
                power = row['power']
                raw_response = str(row['raw_response']).strip()
                
                if phase not in diary_entries:
                    diary_entries[phase] = {}
                
                try:
                    # Try to parse as JSON first
                    response = json.loads(raw_response)
                    diary_content = f"Negotiation Summary: {response.get('negotiation_summary', 'N/A')}\n"
                    diary_content += f"Intent: {response.get('intent', 'N/A')}\n"
                    relationships = response.get('updated_relationships', {})
                    if isinstance(relationships, dict):
                        diary_content += f"Relationships: {relationships}"
                    else:
                        diary_content += f"Relationships: {relationships}"
                    diary_entries[phase][power] = diary_content
                except (json.JSONDecodeError, TypeError):
                    # If JSON parsing fails, use a simplified version or skip
                    if raw_response and raw_response.lower() not in ['null', 'nan', 'none']:
                        diary_entries[phase][power] = f"Raw diary: {raw_response}"
                    
            logger.info(f"Successfully parsed {len(diary_entries)} phases with diary entries")
            return diary_entries
            
        except ImportError:
            # Fallback to standard CSV if pandas not available
            logger.info("Pandas not available, using standard CSV parsing")
            import csv
            
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        if row.get('response_type') == 'negotiation_diary':
                            phase = row.get('phase', '')
                            power = row.get('power', '')
                            
                            if phase and power:
                                if phase not in diary_entries:
                                    diary_entries[phase] = {}
                                
                                raw_response = row.get('raw_response', '').strip()
                                
                                try:
                                    # Try to parse as JSON
                                    response = json.loads(raw_response)
                                    diary_content = f"Negotiation Summary: {response.get('negotiation_summary', 'N/A')}\n"
                                    diary_content += f"Intent: {response.get('intent', 'N/A')}\n"
                                    diary_content += f"Relationships: {response.get('updated_relationships', 'N/A')}"
                                    diary_entries[phase][power] = diary_content
                                except (json.JSONDecodeError, TypeError):
                                    if raw_response and raw_response != "null":
                                        diary_entries[phase][power] = f"Raw diary: {raw_response}"
                    except Exception as e:
                        continue  # Skip problematic rows
                        
            return diary_entries
            
        except Exception as e:
            logger.error(f"Error parsing CSV file: {e}")
            return {}
    
    def parse_invalid_moves_from_csv(self) -> Dict[str, int]:
        """Parse the CSV file to count invalid moves by model"""
        invalid_moves_by_model = {}
        
        try:
            import pandas as pd
            # Use pandas for more robust CSV parsing
            df = pd.read_csv(self.csv_path)
            
            # Look for failures in the success column
            failure_df = df[df['success'].str.contains('Failure: Invalid LLM Moves', na=False)]
            
            for _, row in failure_df.iterrows():
                model = row['model']
                success_text = str(row['success'])
                
                # Extract the number from "Failure: Invalid LLM Moves (N):"
                import re
                match = re.search(r'Invalid LLM Moves \((\d+)\)', success_text)
                if match:
                    invalid_count = int(match.group(1))
                    if model not in invalid_moves_by_model:
                        invalid_moves_by_model[model] = 0
                    invalid_moves_by_model[model] += invalid_count
            
            logger.info(f"Successfully parsed invalid moves for {len(invalid_moves_by_model)} models")
            return invalid_moves_by_model
            
        except ImportError:
            # Fallback to standard CSV if pandas not available
            logger.info("Pandas not available, using standard CSV parsing for invalid moves")
            import csv
            import re
            
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        success_text = row.get('success', '')
                        if 'Failure: Invalid LLM Moves' in success_text:
                            model = row.get('model', '')
                            match = re.search(r'Invalid LLM Moves \((\d+)\)', success_text)
                            if match and model:
                                invalid_count = int(match.group(1))
                                if model not in invalid_moves_by_model:
                                    invalid_moves_by_model[model] = 0
                                invalid_moves_by_model[model] += invalid_count
                    except Exception as e:
                        continue  # Skip problematic rows
                        
            return invalid_moves_by_model
            
        except Exception as e:
            logger.error(f"Error parsing invalid moves from CSV file: {e}")
            return {}
    
    def extract_turn_data(self, phase_data: Dict) -> Dict:
        """Extract relevant data from a single turn/phase"""
        phase_name = phase_data.get("name", "")
        
        # Get diary entries for this phase
        phase_diaries = self.diary_entries.get(phase_name, {})
        
        return {
            "phase": phase_name,
            "messages": phase_data.get("messages", []),
            "orders": phase_data.get("orders", {}),
            "summary": phase_data.get("summary", ""),
            "statistical_summary": phase_data.get("statistical_summary", {}),
            "diaries": phase_diaries
        }
    
    def create_analysis_prompt(self, turn_data: Dict) -> str:
        """Create the analysis prompt for a single turn"""
        # Format messages for analysis
        formatted_messages = []
        for msg in turn_data.get("messages", []):
            sender = msg.get('sender', 'Unknown')
            sender_model = self.power_to_model.get(sender, '')
            sender_str = f"{sender} ({sender_model})" if sender_model else sender
            
            recipient = msg.get('recipient', 'Unknown')
            recipient_model = self.power_to_model.get(recipient, '')
            recipient_str = f"{recipient} ({recipient_model})" if recipient_model else recipient
            
            formatted_messages.append(
                f"{sender_str} to {recipient_str}: {msg.get('message', '')}"
            )
        
        # Format orders for analysis
        formatted_orders = []
        for power, power_orders in turn_data.get("orders", {}).items():
            power_model = self.power_to_model.get(power, '')
            power_str = f"{power} ({power_model})" if power_model else power
            formatted_orders.append(f"{power_str}: {power_orders}")
        
        # Format diary entries
        formatted_diaries = []
        for power, diary in turn_data.get("diaries", {}).items():
            power_model = self.power_to_model.get(power, '')
            power_str = f"{power} ({power_model})" if power_model else power
            formatted_diaries.append(f"{power_str} DIARY:\n{diary}")
        
        prompt = f"""You are analyzing diplomatic negotiations and subsequent military orders from a Diplomacy game. Your task is to identify key strategic moments in the following categories:

1. BETRAYAL: When a power explicitly promises one action but takes a contradictory action
2. COLLABORATION: When powers successfully coordinate as agreed
3. PLAYING_BOTH_SIDES: When a power makes conflicting promises to different parties
4. BRILLIANT_STRATEGY: Exceptionally well-executed strategic maneuvers that gain significant advantage
5. STRATEGIC_BLUNDER: Major strategic mistakes that significantly weaken a power's position

IMPORTANT SCORING GUIDELINES:
- Scores 1-3: Minor or routine diplomatic events
- Scores 4-6: Significant but expected diplomatic maneuvers
- Scores 7-8: Notable strategic moments with clear impact
- Scores 9-10: EXCEPTIONAL moments that are truly dramatic or game-changing

Reserve high scores (8+) for:
- Major betrayals that fundamentally shift alliances
- Successful coordinated attacks on major powers
- Clever deceptions that fool multiple powers
- Brilliant strategic maneuvers that dramatically improve position
- Catastrophic strategic errors with lasting consequences
- Actions that dramatically alter the game's balance

For this turn ({turn_data.get('phase', '')}), analyze:

PRIVATE DIARY ENTRIES (Powers' internal thoughts):
{chr(10).join(formatted_diaries) if formatted_diaries else 'No diary entries available'}

MESSAGES:
{chr(10).join(formatted_messages) if formatted_messages else 'No messages this turn'}

ORDERS:
{chr(10).join(formatted_orders) if formatted_orders else 'No orders this turn'}

TURN SUMMARY:
{turn_data.get('summary', 'No summary available')}

Identify ALL instances that fit the five categories. For each instance provide:
{{
    "category": "BETRAYAL" or "COLLABORATION" or "PLAYING_BOTH_SIDES" or "BRILLIANT_STRATEGY" or "STRATEGIC_BLUNDER",
    "powers_involved": ["POWER1", "POWER2", ...],
    "promise_agreement": "What was promised/agreed/intended (or strategy attempted)",
    "actual_action": "What actually happened",
    "impact": "Strategic impact on the game",
    "interest_score": 6.5  // 1-10 scale, be STRICT with high scores
}}

Use the diary entries to verify:
- Whether actions align with stated intentions
- Hidden motivations behind diplomatic moves
- Contradictions between public promises and private plans
- Strategic planning and its execution

Return your response as a JSON array of detected moments. If no relevant moments are found, return an empty array [].

Focus on:
- Comparing diary intentions vs actual orders
- Explicit promises vs actual orders
- Coordinated attacks or defenses
- DMZ violations
- Support promises kept or broken
- Conflicting negotiations with different powers
- Clever strategic positioning
- Missed strategic opportunities
- Tactical errors that cost supply centers
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
                    raw_orders=turn_data["orders"],
                    diary_context=turn_data["diaries"]
                )
                moments.append(game_moment)
                logger.info(f"Detected {game_moment.category} in {game_moment.phase} "
                          f"(score: {game_moment.interest_score})")
            
            return moments
            
        except Exception as e:
            logger.error(f"Error analyzing turn {turn_data.get('phase', '')}: {e}")
            return []
    
    async def analyze_game(self, max_phases: Optional[int] = None, max_concurrent: int = 5):
        """Analyze the entire game for key moments with concurrent processing
        
        Args:
            max_phases: Maximum number of phases to analyze (None = all)
            max_concurrent: Maximum number of concurrent phase analyses
        """
        phases = self.game_data.get("phases", [])
        
        if max_phases is not None:
            phases = phases[:max_phases]
            logger.info(f"Analyzing first {len(phases)} phases (out of {len(self.game_data.get('phases', []))} total)...")
        else:
            logger.info(f"Analyzing {len(phases)} phases...")
        
        # Process phases in batches to avoid overwhelming the API
        all_moments = []
        
        for i in range(0, len(phases), max_concurrent):
            batch = phases[i:i + max_concurrent]
            batch_start = i + 1
            batch_end = min(i + max_concurrent, len(phases))
            
            logger.info(f"Processing batch {batch_start}-{batch_end} of {len(phases)} phases...")
            
            # Create tasks for concurrent processing
            tasks = []
            for j, phase_data in enumerate(batch):
                phase_name = phase_data.get("name", f"Phase {i+j}")
                logger.info(f"Starting analysis of phase {phase_name}")
                task = self.analyze_turn(phase_data)
                tasks.append(task)
            
            # Wait for all tasks in this batch to complete
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results and handle any exceptions
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    phase_name = batch[j].get("name", f"Phase {i+j}")
                    logger.error(f"Error analyzing phase {phase_name}: {result}")
                else:
                    all_moments.extend(result)
            
            # Small delay between batches to be respectful to the API
            if i + max_concurrent < len(phases):
                logger.info(f"Batch complete. Waiting 2 seconds before next batch...")
                await asyncio.sleep(2)
        
        self.moments = all_moments
        
        # Sort moments by interest score
        self.moments.sort(key=lambda m: m.interest_score, reverse=True)
        
        logger.info(f"Analysis complete. Found {len(self.moments)} key moments.")
    
    def format_power_with_model(self, power: str) -> str:
        """Format power name with model in parentheses"""
        model = self.power_to_model.get(power, '')
        return f"{power} ({model})" if model else power
    
    def phase_sort_key(self, phase_name):
        """Create a sortable key for diplomacy phases like 'S1901M', 'F1901M', etc."""
        # Extract season, year, and type
        if not phase_name or len(phase_name) < 6:
            return (0, 0, "")
            
        try:
            season = phase_name[0]  # S, F, W
            year = int(phase_name[1:5]) if phase_name[1:5].isdigit() else 0  # 1901, 1902, etc.
            phase_type = phase_name[5:]  # M, A, R
            
            # Order: Spring (S) < Fall (F) < Winter (W)
            season_order = {"S": 1, "F": 2, "W": 3}.get(season, 0)
            
            return (year, season_order, phase_type)
        except Exception:
            return (0, 0, "")
    
    async def generate_narrative(self) -> str:
        """Generate a narrative story of the game using phase summaries and top moments"""
        # Collect all phase summaries
        phase_summaries = []
        phases_with_summaries = []
        
        for phase in self.game_data.get("phases", []):
            if phase.get("summary"):
                phase_name = phase.get("name", "")
                summary = phase.get("summary", "")
                phases_with_summaries.append((phase_name, summary))
        
        # Sort phases chronologically
        phases_with_summaries.sort(key=lambda p: self.phase_sort_key(p[0]))
        
        # Create summary strings
        for phase_name, summary in phases_with_summaries:
            phase_summaries.append(f"{phase_name}: {summary}")
        
        # Create the narrative prompt
        narrative_prompt = f"""You are a master war historian writing a dramatic chronicle of a Diplomacy game. Transform the comprehensive game record below into a single, gripping narrative of betrayal, alliance, and conquest.

THE COMPETING POWERS (always refer to them as "Power (Model)"):
{chr(10).join([f"- {power} ({model})" for power, model in sorted(self.power_to_model.items())])}

COMPLETE GAME RECORD (synthesize all of this into your narrative):
{chr(10).join(phase_summaries)}

IMPORTANT POWER DIARIES (internal thoughts of each power):
"""
        # Sort diary phases chronologically
        diary_phases = list(self.diary_entries.keys())
        diary_phases.sort(key=self.phase_sort_key)
        
        # Include power diaries for context (early phases)
        for phase in diary_phases[:3]:  # First few phases for early intentions
            narrative_prompt += f"Phase {phase}:\n"
            for power, diary in sorted(self.diary_entries[phase].items()):
                power_with_model = self.format_power_with_model(power)
                diary_excerpt = diary  # Display full diary content
                narrative_prompt += f"- {power_with_model}: {diary_excerpt}\n"
            narrative_prompt += "\n"
            
        # Also include some late-game diaries
        if len(diary_phases) > 3:
            for phase in diary_phases[-2:]:  # Last two phases for endgame context
                narrative_prompt += f"Phase {phase}:\n"
                for power, diary in sorted(self.diary_entries[phase].items()):
                    power_with_model = self.format_power_with_model(power)
                    diary_excerpt = diary  # Display full diary content
                    narrative_prompt += f"- {power_with_model}: {diary_excerpt}\n"
                narrative_prompt += "\n"
            
        narrative_prompt += """
KEY DRAMATIC MOMENTS (reference these highlights appropriately):
"""
        # Extract top moments from each category for narrative context
        key_moments = []
        for category in ["BETRAYAL", "COLLABORATION", "PLAYING_BOTH_SIDES", "BRILLIANT_STRATEGY", "STRATEGIC_BLUNDER"]:
            category_moments = [m for m in self.moments if m.category == category]
            category_moments.sort(key=lambda m: m.interest_score, reverse=True)
            key_moments.extend(category_moments[:5])  # Top 5 from each category
        
        # Sort by phase chronologically
        key_moments.sort(key=lambda m: self.phase_sort_key(m.phase))
        
        # Format dramatic moments with power names and models (simpler format)
        for moment in key_moments:
            powers_with_models = [f"{p} ({self.power_to_model.get(p, 'Unknown')})" for p in moment.powers_involved]
            narrative_prompt += f"{moment.phase} - {moment.category} (Score: {moment.interest_score}/10): {', '.join(powers_with_models)}\n"

        narrative_prompt += """
CRITICAL INSTRUCTIONS:
- Write EXACTLY 1-2 paragraphs that tell the COMPLETE story of the ENTIRE game
- This is NOT a summary of each phase - it's ONE flowing narrative of the whole game
- Always refer to powers as "PowerName (ModelName)" - e.g., "Germany (o3)", "France (o4-mini)"
- Start with how the game began and the initial alliances
- Cover the major turning points and dramatic moments
- End with how the game concluded and who won
- Use dramatic, evocative language but be concise
- Focus on the overall arc of the game, not individual phase details

Create a single, cohesive narrative that captures the essence of the entire game from start to finish. Think of it as the opening passage of a history book chapter about this conflict.
"""

        try:
            response = await self.client.generate_response(narrative_prompt)
            return response
        except Exception as e:
            logger.error(f"Error generating narrative: {e}")
            return "Unable to generate narrative due to an error."
    
    async def generate_report(self, output_path: Optional[str] = None):
        """Generate a markdown report of key moments"""
        # Generate unique filename with datetime if no path specified
        if output_path is None:
            # Create in the game_moments directory
            game_moments_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_moments")
            os.makedirs(game_moments_dir, exist_ok=True)
            
            # Use results folder name in the file name
            results_name = os.path.basename(os.path.normpath(str(self.results_folder)))
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(game_moments_dir, f"{results_name}_report_{timestamp}.md")
        
        # Generate the narrative first
        narrative = await self.generate_narrative()
        
        report_lines = [
            "# Diplomacy Game Analysis: Key Moments",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Game: {self.game_data_path}",
            "",
            "## Game Narrative",
            "",
            narrative,
            "",
            "---",
            "",
            "## Summary",
            f"- Total moments analyzed: {len(self.moments)}",
            f"- Betrayals: {len([m for m in self.moments if m.category == 'BETRAYAL'])}",
            f"- Collaborations: {len([m for m in self.moments if m.category == 'COLLABORATION'])}",
            f"- Playing Both Sides: {len([m for m in self.moments if m.category == 'PLAYING_BOTH_SIDES'])}",
            f"- Brilliant Strategies: {len([m for m in self.moments if m.category == 'BRILLIANT_STRATEGY'])}",
            f"- Strategic Blunders: {len([m for m in self.moments if m.category == 'STRATEGIC_BLUNDER'])}",
            "",
            "## Score Distribution",
            f"- Scores 9-10: {len([m for m in self.moments if m.interest_score >= 9])}",
            f"- Scores 7-8: {len([m for m in self.moments if 7 <= m.interest_score < 9])}",
            f"- Scores 4-6: {len([m for m in self.moments if 4 <= m.interest_score < 7])}",
            f"- Scores 1-3: {len([m for m in self.moments if m.interest_score < 4])}",
            "",
            "## Power Models",
            ""
        ]
        
        # Add power-model mapping
        for power, model in sorted(self.power_to_model.items()):
            report_lines.append(f"- **{power}**: {model}")
        
        # Add category breakdowns with detailed information
        report_lines.extend([
            "## Key Strategic Moments by Category",
            ""
        ])
        
        # BETRAYALS SECTION
        report_lines.extend([
            "### Betrayals",
            "_When powers explicitly promised one action but took a contradictory action_",
            ""
        ])
        
        betrayals = [m for m in self.moments if m.category == "BETRAYAL"]
        betrayals.sort(key=lambda m: m.interest_score, reverse=True)
        
        for i, moment in enumerate(betrayals[:5], 1):
            powers_str = ', '.join([self.format_power_with_model(p) for p in moment.powers_involved])
            report_lines.extend([
                f"#### {i}. {moment.phase} (Score: {moment.interest_score}/10)",
                f"**Powers Involved:** {powers_str}",
                "",
                f"**Promise:** {moment.promise_agreement if moment.promise_agreement else 'N/A'}",
                "",
                f"**Actual Action:** {moment.actual_action if moment.actual_action else 'N/A'}",
                "",
                f"**Impact:** {moment.impact if moment.impact else 'N/A'}",
                "",
                "**Diary Context:**",
                ""
            ])
            
            # Add relevant diary entries
            for power in moment.powers_involved:
                if power in moment.diary_context:
                    power_with_model = self.format_power_with_model(power)
                    report_lines.append(f"_{power_with_model} Diary:_ {moment.diary_context[power]}")
                    report_lines.append("")
                    
            report_lines.append("")
        
        # COLLABORATIONS SECTION
        report_lines.extend([
            "### Collaborations",
            "_When powers successfully coordinated as agreed_",
            ""
        ])
        
        collaborations = [m for m in self.moments if m.category == "COLLABORATION"]
        collaborations.sort(key=lambda m: m.interest_score, reverse=True)
        
        for i, moment in enumerate(collaborations[:5], 1):
            powers_str = ', '.join([self.format_power_with_model(p) for p in moment.powers_involved])
            report_lines.extend([
                f"#### {i}. {moment.phase} (Score: {moment.interest_score}/10)",
                f"**Powers Involved:** {powers_str}",
                "",
                f"**Agreement:** {moment.promise_agreement if moment.promise_agreement else 'N/A'}",
                "",
                f"**Action Taken:** {moment.actual_action if moment.actual_action else 'N/A'}",
                "",
                f"**Impact:** {moment.impact if moment.impact else 'N/A'}",
                "",
                "**Diary Context:**",
                ""
            ])
            
            # Add relevant diary entries
            for power in moment.powers_involved:
                if power in moment.diary_context:
                    power_with_model = self.format_power_with_model(power)
                    report_lines.append(f"_{power_with_model} Diary:_ {moment.diary_context[power]}")
                    report_lines.append("")
                    
            report_lines.append("")
        
        # PLAYING BOTH SIDES SECTION
        report_lines.extend([
            "### Playing Both Sides",
            "_When a power made conflicting promises to different parties_",
            ""
        ])
        
        playing_both = [m for m in self.moments if m.category == "PLAYING_BOTH_SIDES"]
        playing_both.sort(key=lambda m: m.interest_score, reverse=True)
        
        for i, moment in enumerate(playing_both[:5], 1):
            powers_str = ', '.join([self.format_power_with_model(p) for p in moment.powers_involved])
            report_lines.extend([
                f"#### {i}. {moment.phase} (Score: {moment.interest_score}/10)",
                f"**Powers Involved:** {powers_str}",
                "",
                f"**Conflicting Promises:** {moment.promise_agreement if moment.promise_agreement else 'N/A'}",
                "",
                f"**Actual Action:** {moment.actual_action if moment.actual_action else 'N/A'}",
                "",
                f"**Impact:** {moment.impact if moment.impact else 'N/A'}",
                "",
                "**Diary Context:**",
                ""
            ])
            
            # Add relevant diary entries
            for power in moment.powers_involved:
                if power in moment.diary_context:
                    power_with_model = self.format_power_with_model(power)
                    report_lines.append(f"_{power_with_model} Diary:_ {moment.diary_context[power]}")
                    report_lines.append("")
                    
            report_lines.append("")
        
        # BRILLIANT STRATEGIES SECTION
        report_lines.extend([
            "### Brilliant Strategies",
            "_Exceptionally well-executed strategic maneuvers that gained significant advantage_",
            ""
        ])
        
        brilliant = [m for m in self.moments if m.category == "BRILLIANT_STRATEGY"]
        brilliant.sort(key=lambda m: m.interest_score, reverse=True)
        
        for i, moment in enumerate(brilliant[:5], 1):
            powers_str = ', '.join([self.format_power_with_model(p) for p in moment.powers_involved])
            report_lines.extend([
                f"#### {i}. {moment.phase} (Score: {moment.interest_score}/10)",
                f"**Powers Involved:** {powers_str}",
                "",
                f"**Strategy:** {moment.promise_agreement if moment.promise_agreement else 'N/A'}",
                "",
                f"**Execution:** {moment.actual_action if moment.actual_action else 'N/A'}",
                "",
                f"**Impact:** {moment.impact if moment.impact else 'N/A'}",
                "",
                "**Diary Context:**",
                ""
            ])
            
            # Add relevant diary entries
            for power in moment.powers_involved:
                if power in moment.diary_context:
                    power_with_model = self.format_power_with_model(power)
                    report_lines.append(f"_{power_with_model} Diary:_ {moment.diary_context[power]}")
                    report_lines.append("")
                    
            report_lines.append("")
        
        # STRATEGIC BLUNDERS SECTION
        report_lines.extend([
            "### Strategic Blunders",
            "_Major strategic mistakes that significantly weakened a power's position_",
            ""
        ])
        
        blunders = [m for m in self.moments if m.category == "STRATEGIC_BLUNDER"]
        blunders.sort(key=lambda m: m.interest_score, reverse=True)
        
        for i, moment in enumerate(blunders[:5], 1):
            powers_str = ', '.join([self.format_power_with_model(p) for p in moment.powers_involved])
            report_lines.extend([
                f"#### {i}. {moment.phase} (Score: {moment.interest_score}/10)",
                f"**Powers Involved:** {powers_str}",
                "",
                f"**Mistaken Strategy:** {moment.promise_agreement if moment.promise_agreement else 'N/A'}",
                "",
                f"**What Happened:** {moment.actual_action if moment.actual_action else 'N/A'}",
                "",
                f"**Impact:** {moment.impact if moment.impact else 'N/A'}",
                "",
                "**Diary Context:**",
                ""
            ])
            
            # Add relevant diary entries
            for power in moment.powers_involved:
                if power in moment.diary_context:
                    power_with_model = self.format_power_with_model(power)
                    report_lines.append(f"_{power_with_model} Diary:_ {moment.diary_context[power]}")
                    report_lines.append("")
                    
            report_lines.append("")
        
        # Write report
        with open(output_path, 'w') as f:
            f.write('\n'.join(report_lines))
        
        logger.info(f"Report generated: {output_path}")
        return output_path
    
    def save_json_results(self, output_path: Optional[str] = None):
        """Save all moments as JSON for further analysis"""
        # Generate unique filename with datetime if no path specified
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if output_path is None:
            # Create in the game_moments directory
            game_moments_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_moments")
            os.makedirs(game_moments_dir, exist_ok=True)
            
            # Use results folder name in the file name
            results_name = os.path.basename(os.path.normpath(str(self.results_folder)))
            output_path = os.path.join(game_moments_dir, f"{results_name}_data_{timestamp}.json")
        
        # Prepare the moments data
        moments_data = []
        for moment in self.moments:
            moment_dict = asdict(moment)
            # Remove raw data for cleaner JSON
            moment_dict.pop('raw_messages', None)
            moment_dict.pop('raw_orders', None)
            # Keep diary context but limit size
            if 'diary_context' in moment_dict:
                for power, diary in moment_dict['diary_context'].items():
                    moment_dict['diary_context'][power] = diary  # Include full diary content
            moments_data.append(moment_dict)
        
        # Create the final data structure with metadata
        full_data = {
            "metadata": {
                "timestamp": timestamp,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source_folder": str(self.results_folder),
                "analysis_model": self.model_name,
                "total_moments": len(self.moments),
                "moment_categories": {
                    "betrayals": len([m for m in self.moments if m.category == "BETRAYAL"]),
                    "collaborations": len([m for m in self.moments if m.category == "COLLABORATION"]),
                    "playing_both_sides": len([m for m in self.moments if m.category == "PLAYING_BOTH_SIDES"]),
                    "brilliant_strategies": len([m for m in self.moments if m.category == "BRILLIANT_STRATEGY"]),
                    "strategic_blunders": len([m for m in self.moments if m.category == "STRATEGIC_BLUNDER"])
                },
                "score_distribution": {
                    "scores_9_10": len([m for m in self.moments if m.interest_score >= 9]),
                    "scores_7_8": len([m for m in self.moments if 7 <= m.interest_score < 9]),
                    "scores_4_6": len([m for m in self.moments if 4 <= m.interest_score < 7]),
                    "scores_1_3": len([m for m in self.moments if m.interest_score < 4])
                }
            },
            "power_models": self.power_to_model,
            "invalid_moves_by_model": self.invalid_moves_by_model,
            "moments": moments_data
        }
        
        # Write to file
        with open(output_path, 'w') as f:
            json.dump(full_data, f, indent=2)
        
        logger.info(f"JSON results saved: {output_path}")
        return output_path

async def main():
    parser = argparse.ArgumentParser(description="Analyze Diplomacy game for key strategic moments")
    parser.add_argument("results_folder", help="Path to the results folder containing lmvsgame.json and overview.jsonl")
    parser.add_argument("--model", default="openrouter-google/gemini-2.5-flash-preview",
                        help="Model to use for analysis")
    parser.add_argument("--report", default=None,
                        help="Output path for markdown report (auto-generates timestamped name if not specified)")
    parser.add_argument("--json", default=None,
                        help="Output path for JSON results (auto-generates timestamped name if not specified)")
    parser.add_argument("--max-phases", type=int, default=None,
                        help="Maximum number of phases to analyze (useful for testing)")
    parser.add_argument("--max-concurrent", type=int, default=5,
                        help="Maximum number of concurrent phase analyses (default: 5)")
    
    args = parser.parse_args()
    
    # Ensure the game_moments directory exists
    game_moments_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_moments")
    os.makedirs(game_moments_dir, exist_ok=True)
    
    # Extract game name from the results folder
    results_folder_name = os.path.basename(os.path.normpath(args.results_folder))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create default report and JSON paths in the game_moments directory
    if args.report is None:
        args.report = os.path.join(game_moments_dir, f"{results_folder_name}_report_{timestamp}.md")
    
    if args.json is None:
        args.json = os.path.join(game_moments_dir, f"{results_folder_name}_data_{timestamp}.json")
    
    analyzer = GameAnalyzer(args.results_folder, args.model)
    
    try:
        await analyzer.initialize()
        await analyzer.analyze_game(max_phases=args.max_phases, max_concurrent=args.max_concurrent)
        report_path = await analyzer.generate_report(args.report)
        json_path = analyzer.save_json_results(args.json)
        
        # Print summary
        print(f"\nAnalysis Complete!")
        print(f"Found {len(analyzer.moments)} key moments")
        print(f"Report saved to: {report_path}")
        print(f"JSON data saved to: {json_path}")
        
        # Show score distribution
        print("\nScore Distribution:")
        print(f"  Scores 9-10: {len([m for m in analyzer.moments if m.interest_score >= 9])}")
        print(f"  Scores 7-8: {len([m for m in analyzer.moments if 7 <= m.interest_score < 9])}")
        print(f"  Scores 4-6: {len([m for m in analyzer.moments if 4 <= m.interest_score < 7])}")
        print(f"  Scores 1-3: {len([m for m in analyzer.moments if m.interest_score < 4])}")
        
        # Show top 3 moments
        print("\nTop 3 Most Interesting Moments:")
        for i, moment in enumerate(analyzer.moments[:3], 1):
            powers_str = ', '.join([analyzer.format_power_with_model(p) for p in moment.powers_involved])
            print(f"{i}. {moment.category} in {moment.phase} (Score: {moment.interest_score})")
            print(f"   Powers: {powers_str}")
            print(f"   Impact: {moment.impact[:100]}...")
            print()
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())