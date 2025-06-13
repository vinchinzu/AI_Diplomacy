"""
Core domain models for game history.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from ai_diplomacy.domain import Message

logger = logging.getLogger(__name__)

__all__ = ["Message", "Phase", "GameHistory"]


@dataclass
class Message:
    sender: str
    recipient: str
    content: str


@dataclass
class Phase:
    name: str
    plans: Dict[str, str] = field(default_factory=dict)
    messages: List[Message] = field(default_factory=list)
    orders_by_power: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    results_by_power: Dict[str, List[List[str]]] = field(default_factory=lambda: defaultdict(list))
    phase_summaries: Dict[str, str] = field(default_factory=dict)
    experience_updates: Dict[str, str] = field(default_factory=dict)

    def add_plan(self, power_name: str, plan: str):
        self.plans[power_name] = plan

    def add_message(self, sender: str, recipient: str, content: str):
        self.messages.append(Message(sender=sender, recipient=recipient, content=content))

    def add_orders(self, power: str, orders: List[str], results: List[List[str]]):
        self.orders_by_power[power].extend(orders)
        if len(results) < len(orders):
            results.extend([[] for _ in range(len(orders) - len(results))])
        self.results_by_power[power].extend(results)


@dataclass
class GameHistory:
    phases: List[Phase] = field(default_factory=list)

    def add_phase(self, phase_name: str):
        if not self.phases or self.phases[-1].name != phase_name:
            self.phases.append(Phase(name=phase_name))
            logger.debug(f"Added new phase: {phase_name}")
        else:
            logger.warning(f"Phase {phase_name} already exists. Not adding again.")

    def _get_phase(self, phase_name: str) -> Optional[Phase]:
        for phase in reversed(self.phases):
            if phase.name == phase_name:
                return phase
        logger.error(f"Phase {phase_name} not found in history.")
        return None

    def get_phase_by_name(self, phase_name_to_find: str) -> Optional[Phase]:
        """Finds and returns a phase by its exact name."""
        for phase in self.phases:
            if phase.name == phase_name_to_find:
                return phase
        return None

    def add_plan(self, phase_name: str, power_name: str, plan: str):
        phase = self._get_phase(phase_name)
        if phase:
            phase.plans[power_name] = plan
            logger.debug(f"Added plan for {power_name} in {phase_name}")

    def add_message(self, phase_name: str, sender: str, recipient: str, message_content: str):
        phase = self._get_phase(phase_name)
        if phase:
            message = Message(sender=sender, recipient=recipient, content=message_content)
            phase.messages.append(message)
            logger.debug(f"Added message from {sender} to {recipient} in {phase_name}")

    def add_orders(self, phase_name: str, power_name: str, orders: List[str]):
        phase = self._get_phase(phase_name)
        if phase:
            phase.orders_by_power[power_name].extend(orders)
            logger.debug(f"Added orders for {power_name} in {phase_name}: {orders}")

    def add_results(self, phase_name: str, power_name: str, results: List[List[str]]):
        phase = self._get_phase(phase_name)
        if phase:
            phase.results_by_power[power_name].extend(results)
            logger.debug(f"Added results for {power_name} in {phase_name}: {results}")

    def add_phase_summary(self, phase_name: str, power_name: str, summary: str):
        phase = self._get_phase(phase_name)
        if phase:
            phase.phase_summaries[power_name] = summary
            logger.debug(f"Added phase summary for {power_name} in {phase_name}")

    def add_experience_update(self, phase_name: str, power_name: str, update: str):
        phase = self._get_phase(phase_name)
        if phase:
            phase.experience_updates[power_name] = update
            logger.debug(f"Added experience update for {power_name} in {phase_name}")

    def get_strategic_directives(self) -> Dict[str, str]:
        if not self.phases:
            return {}
        return self.phases[-1].plans

    def get_messages_by_phase(self, phase_name: str) -> List[dict]:
        """Return all messages for a given phase as a list of dicts."""
        phase = self.get_phase_by_name(phase_name)
        if not phase:
            logger.error(f"Phase {phase_name} not found in history.")
            return []
        return [{"sender": m.sender, "recipient": m.recipient, "content": m.content} for m in phase.messages]

    def to_dict(self) -> dict:
        """Convert GameHistory to a dictionary for JSON serialization."""
        return {
            "phases": [
                {
                    "name": phase.name,
                    "plans": dict(phase.plans),
                    "messages": [
                        {
                            "sender": msg.sender,
                            "recipient": msg.recipient,
                            "content": msg.content,
                        }
                        for msg in phase.messages
                    ],
                    "orders_by_power": {
                        power: list(orders) for power, orders in phase.orders_by_power.items()
                    },
                    "results_by_power": {
                        power: list(results) for power, results in phase.results_by_power.items()
                    },
                    "phase_summaries": dict(phase.phase_summaries),
                    "experience_updates": dict(phase.experience_updates),
                }
                for phase in self.phases
            ]
        } 