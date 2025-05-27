"""
Usage tracking and analytics service.
Provides utilities for token usage analysis and Datasette integration.
"""

import sqlite3
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

DATABASE_PATH = "ai_diplomacy_usage.db"


@dataclass
class UsageStats:
    """Container for usage statistics."""

    agent: str
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    models_used: List[str]
    cost_estimate: Optional[float] = None


@dataclass
class GameSummary:
    """Summary statistics for a complete game."""

    game_id: str
    total_agents: int
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    duration_hours: Optional[float] = None
    cost_estimate: Optional[float] = None


class UsageTracker:
    """Service for analyzing LLM usage patterns and costs."""

    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path

    def get_agent_stats(self, game_id: str, agent: str) -> Optional[UsageStats]:
        """Get usage statistics for a specific agent in a game."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT 
                        COUNT(*) as calls,
                        SUM(input) as input_tokens,
                        SUM(output) as output_tokens,
                        GROUP_CONCAT(DISTINCT model) as models
                    FROM usage 
                    WHERE game_id = ? AND agent = ?
                """,
                    (game_id, agent),
                )

                row = cursor.fetchone()
                if row and row[0] > 0:
                    models = row[3].split(",") if row[3] else []
                    return UsageStats(
                        agent=agent,
                        total_calls=row[0],
                        total_input_tokens=row[1] or 0,
                        total_output_tokens=row[2] or 0,
                        models_used=models,
                    )
                return None
        except sqlite3.Error as e:
            logger.error(f"Error getting agent stats: {e}")
            return None

    def get_game_summary(self, game_id: str) -> Optional[GameSummary]:
        """Get overall statistics for a game."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get basic stats
                cursor = conn.execute(
                    """
                    SELECT 
                        COUNT(DISTINCT agent) as agents,
                        COUNT(*) as calls,
                        SUM(input) as input_tokens,
                        SUM(output) as output_tokens,
                        MIN(ts) as start_time,
                        MAX(ts) as end_time
                    FROM usage 
                    WHERE game_id = ?
                """,
                    (game_id,),
                )

                row = cursor.fetchone()
                if row and row[1] > 0:
                    # Calculate duration if we have timestamps
                    duration = None
                    if row[4] and row[5]:
                        try:
                            start = datetime.fromisoformat(row[4])
                            end = datetime.fromisoformat(row[5])
                            duration = (end - start).total_seconds() / 3600  # hours
                        except ValueError:
                            pass

                    return GameSummary(
                        game_id=game_id,
                        total_agents=row[0],
                        total_calls=row[1],
                        total_input_tokens=row[2] or 0,
                        total_output_tokens=row[3] or 0,
                        duration_hours=duration,
                    )
                return None
        except sqlite3.Error as e:
            logger.error(f"Error getting game summary: {e}")
            return None

    def get_all_games(self) -> List[str]:
        """Get list of all game IDs in the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT DISTINCT game_id FROM usage ORDER BY game_id"
                )
                return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Error getting game list: {e}")
            return []

    def get_phase_breakdown(self, game_id: str) -> Dict[str, UsageStats]:
        """Get usage breakdown by phase for a game."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT 
                        phase,
                        COUNT(*) as calls,
                        SUM(input) as input_tokens,
                        SUM(output) as output_tokens
                    FROM usage 
                    WHERE game_id = ?
                    GROUP BY phase
                    ORDER BY phase
                """,
                    (game_id,),
                )

                results = {}
                for row in cursor.fetchall():
                    results[row[0]] = UsageStats(
                        agent=f"Phase {row[0]}",
                        total_calls=row[1],
                        total_input_tokens=row[2] or 0,
                        total_output_tokens=row[3] or 0,
                        models_used=[],
                    )
                return results
        except sqlite3.Error as e:
            logger.error(f"Error getting phase breakdown: {e}")
            return {}

    def export_for_datasette(self, output_path: Optional[str] = None) -> str:
        """
        Export data in a format optimized for Datasette viewing.
        Returns the path to the exported database.
        """
        if output_path is None:
            output_path = self.db_path.replace(".db", "_datasette.db")

        try:
            with sqlite3.connect(self.db_path) as source:
                with sqlite3.connect(output_path) as dest:
                    # Copy the usage table
                    source.backup(dest)

                    # Add computed views for better Datasette experience
                    dest.execute(
                        """
                        CREATE VIEW IF NOT EXISTS game_summary AS
                        SELECT 
                            game_id,
                            COUNT(DISTINCT agent) as agents,
                            COUNT(*) as total_calls,
                            SUM(input) as total_input_tokens,
                            SUM(output) as total_output_tokens,
                            ROUND(AVG(input), 2) as avg_input_per_call,
                            ROUND(AVG(output), 2) as avg_output_per_call,
                            MIN(ts) as start_time,
                            MAX(ts) as end_time
                        FROM usage 
                        GROUP BY game_id
                    """
                    )

                    dest.execute(
                        """
                        CREATE VIEW IF NOT EXISTS agent_performance AS
                        SELECT 
                            game_id,
                            agent,
                            COUNT(*) as calls,
                            SUM(input) as input_tokens,
                            SUM(output) as output_tokens,
                            ROUND(SUM(input + output) / COUNT(*), 2) as avg_tokens_per_call,
                            GROUP_CONCAT(DISTINCT model) as models_used
                        FROM usage 
                        GROUP BY game_id, agent
                    """
                    )

                    dest.execute(
                        """
                        CREATE VIEW IF NOT EXISTS phase_analysis AS
                        SELECT 
                            game_id,
                            phase,
                            COUNT(*) as calls,
                            COUNT(DISTINCT agent) as active_agents,
                            SUM(input) as input_tokens,
                            SUM(output) as output_tokens
                        FROM usage 
                        GROUP BY game_id, phase
                    """
                    )

                    dest.commit()

            logger.info(f"Exported Datasette-optimized database to {output_path}")
            return output_path

        except sqlite3.Error as e:
            logger.error(f"Error exporting for Datasette: {e}")
            raise

    def generate_cost_estimate(self, stats: UsageStats, model_id: str) -> float:
        """
        Generate rough cost estimate based on token usage.
        These are approximations based on common pricing as of 2024.
        """
        # Rough pricing per 1K tokens (input/output) for common models
        pricing = {
            "gpt-4o": (0.005, 0.015),
            "gpt-4o-mini": (0.00015, 0.0006),
            "gpt-4-turbo": (0.01, 0.03),
            "gpt-3.5-turbo": (0.001, 0.002),
            "claude-3-5-sonnet": (0.003, 0.015),
            "claude-3-opus": (0.015, 0.075),
            "claude-3-sonnet": (0.003, 0.015),
            "claude-3-haiku": (0.00025, 0.00125),
        }

        # Default pricing for unknown models (use GPT-4o-mini as baseline)
        input_price, output_price = pricing.get(model_id, (0.00015, 0.0006))

        input_cost = (stats.total_input_tokens / 1000) * input_price
        output_cost = (stats.total_output_tokens / 1000) * output_price

        return input_cost + output_cost


def create_datasette_config(db_path: str) -> Dict[str, Any]:
    """
    Create a Datasette configuration for the usage database.
    Returns a config dict that can be saved as metadata.json.
    """
    return {
        "title": "AI Diplomacy Usage Analytics",
        "description": "Token usage and performance analytics for AI Diplomacy games",
        "databases": {
            "usage": {
                "title": "LLM Usage Database",
                "description": "Detailed token usage logs for AI agents",
                "tables": {
                    "usage": {
                        "title": "Raw Usage Data",
                        "description": "Individual LLM API calls with token counts",
                        "sort_desc": "ts",
                    },
                    "game_summary": {
                        "title": "Game Summaries",
                        "description": "Aggregated statistics per game",
                    },
                    "agent_performance": {
                        "title": "Agent Performance",
                        "description": "Per-agent statistics across games",
                    },
                    "phase_analysis": {
                        "title": "Phase Analysis",
                        "description": "Token usage patterns by game phase",
                    },
                },
            }
        },
        "plugins": {"datasette-vega": {"default_width": 800, "default_height": 400}},
    }


# Compatibility functions for legacy code
def get_usage_stats_by_country(game_id: str) -> Dict[str, Dict[str, int]]:
    """
    Get API usage statistics by country for a specific game.
    Compatibility function for legacy code.
    """
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.execute(
                """
                SELECT agent, 
                       COUNT(*) as api_calls,
                       SUM(input) as total_input_tokens,
                       SUM(output) as total_output_tokens,
                       model
                FROM usage 
                WHERE game_id = ? 
                GROUP BY agent, model
                ORDER BY agent
            """,
                (game_id,),
            )

            results = {}
            for row in cursor.fetchall():
                agent, api_calls, input_tokens, output_tokens, model = row
                if agent not in results:
                    results[agent] = {
                        "api_calls": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "models": [],
                    }
                results[agent]["api_calls"] += api_calls
                results[agent]["input_tokens"] += input_tokens or 0
                results[agent]["output_tokens"] += output_tokens or 0
                if model not in results[agent]["models"]:
                    results[agent]["models"].append(model)

            return results
    except sqlite3.Error as e:
        logger.error(f"Error getting usage stats: {e}", exc_info=True)
        return {}


def get_total_usage_stats(game_id: str) -> Dict[str, int]:
    """
    Get total API usage statistics for a specific game.
    Compatibility function for legacy code.
    """
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.execute(
                """
                SELECT COUNT(*) as total_api_calls,
                       SUM(input) as total_input_tokens,
                       SUM(output) as total_output_tokens
                FROM usage 
                WHERE game_id = ?
            """,
                (game_id,),
            )

            row = cursor.fetchone()
            if row:
                return {
                    "total_api_calls": row[0],
                    "total_input_tokens": row[1] or 0,
                    "total_output_tokens": row[2] or 0,
                }
            return {
                "total_api_calls": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
            }
    except sqlite3.Error as e:
        logger.error(f"Error getting total usage stats: {e}", exc_info=True)
        return {"total_api_calls": 0, "total_input_tokens": 0, "total_output_tokens": 0}

