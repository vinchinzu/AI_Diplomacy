"""
Game configuration parsing and management.
"""

import argparse
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import toml
import os
from datetime import datetime


DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_GAME_ID_PREFIX = "aidiplomacy"
DEFAULT_NUM_PLAYERS = 7
DEFAULT_NUM_NEGOTIATION_ROUNDS = 3
DEFAULT_NEGOTIATION_STYLE = "simultaneous"


@dataclass
class GameConfig:
    """Typed configuration class for a game instance."""

    args: argparse.Namespace
    game_id: str
    log_dir: str
    models: Dict[str, Any] = field(default_factory=dict)
    powers: Dict[str, Any] = field(default_factory=dict)
    agents: Dict[str, Any] = field(default_factory=dict)
    power_to_agent_id_map: Dict[str, str] = field(default_factory=dict)

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.game_id = self._determine_game_id()
        self.log_dir = self._setup_log_dir()
        self._load_models_config()
        self._prepare_power_agent_mapping()

    def _determine_game_id(self) -> str:
        if self.args.game_id:
            return self.args.game_id
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{self.args.game_id_prefix}_{timestamp}"

    def _setup_log_dir(self) -> str:
        base_log_dir = self.args.log_dir or "logs"
        game_log_dir = os.path.join(base_log_dir, self.game_id)
        if self.args.log_to_file:
            os.makedirs(game_log_dir, exist_ok=True)
        return game_log_dir

    def _load_models_config(self):
        if self.args.models_config_file and os.path.exists(self.args.models_config_file):
            with open(self.args.models_config_file, "r") as f:
                self.models = toml.load(f).get("models", {})

    def _prepare_power_agent_mapping(self):
        # This is a simplified placeholder. The actual logic might be more complex,
        # involving fixed_models, randomization, etc.
        all_powers = ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"]
        for power in all_powers:
            self.power_to_agent_id_map[power] = power 