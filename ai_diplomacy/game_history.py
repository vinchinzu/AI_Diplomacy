from dotenv import load_dotenv
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger("utils")
logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO)
load_dotenv()


@dataclass
class Message:
    sender: str
    recipient: str
    content: str


@dataclass
class Phase:
    name: str  # e.g. "SPRING 1901"
    plans: Dict[str, str] = field(default_factory=dict)
    messages: List[Message] = field(default_factory=list)
    orders_by_power: Dict[str, List[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    results_by_power: Dict[str, List[List[str]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    # NEW: Store phase-end summaries provided by each power
    phase_summaries: Dict[str, str] = field(default_factory=dict)
    # NEW: Store experience/journal updates from each power for this phase
    experience_updates: Dict[str, str] = field(default_factory=dict)

    def add_plan(self, power_name: str, plan: str):
        self.plans[power_name] = plan
    
    def add_message(self, sender: str, recipient: str, content: str):
        self.messages.append(
            Message(sender=sender, recipient=recipient, content=content)
        )

    def add_orders(self, power: str, orders: List[str], results: List[List[str]]):
        self.orders_by_power[power].extend(orders)
        # Make sure results has the same length as orders, if not, pad with empty lists
        if len(results) < len(orders):
            results.extend([[] for _ in range(len(orders) - len(results))])
        self.results_by_power[power].extend(results)

    def get_global_messages(self) -> str:
        result = ""
        for msg in self.messages:
            if msg.recipient == "GLOBAL":
                result += f" {msg.sender}: {msg.content}\n"
        return result

    def get_private_messages(self, power: str) -> Dict[str, str]:
        conversations = defaultdict(str)
        for msg in self.messages:
            if msg.sender == power and msg.recipient != "GLOBAL":
                conversations[msg.recipient] += f"  {power}: {msg.content}\n"
            elif msg.recipient == power:
                conversations[msg.sender] += f"  {msg.sender}: {msg.content}\n"
        return conversations

    def get_all_orders_formatted(self) -> str:
        if not self.orders_by_power:
            return ""

        result = f"\nOrders for {self.name}:\n"
        for power, orders in self.orders_by_power.items():
            result += f"{power}:\n"
            results = self.results_by_power.get(power, [])
            for i, order in enumerate(orders):
                if i < len(results) and results[i]:
                    # Join multiple results with commas
                    result_str = f" ({', '.join(results[i])})"
                else:
                    result_str = " (successful)"
                result += f"  {order}{result_str}\n"
            result += "\n"
        return result


@dataclass
class GameHistory:
    phases: List[Phase] = field(default_factory=list)

    def add_phase(self, phase_name: str):
        # Avoid adding duplicate phases
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

    def add_plan(self, phase_name: str, power_name: str, plan: str):
        phase = self._get_phase(phase_name)
        if phase:
            phase.plans[power_name] = plan
            logger.debug(f"Added plan for {power_name} in {phase_name}")

    def add_message(
        self, phase_name: str, sender: str, recipient: str, message_content: str
    ):
        phase = self._get_phase(phase_name)
        if phase:
            message = Message(
                sender=sender, recipient=recipient, content=message_content
            )
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

    # NEW: Method to add phase summary for a power
    def add_phase_summary(self, phase_name: str, power_name: str, summary: str):
        phase = self._get_phase(phase_name)
        if phase:
            phase.phase_summaries[power_name] = summary
            logger.debug(f"Added phase summary for {power_name} in {phase_name}")

    # NEW: Method to add experience update for a power
    def add_experience_update(self, phase_name: str, power_name: str, update: str):
        phase = self._get_phase(phase_name)
        if phase:
            phase.experience_updates[power_name] = update
            logger.debug(f"Added experience update for {power_name} in {phase_name}")

    def get_strategic_directives(self): 
        # returns for last phase only if exists
        if not self.phases: 
            return {}
        return self.phases[-1].plans

    def get_game_history(
        self, power_name: str, include_plans: bool = True, num_prev_phases: int = 5
    ) -> str:
        if not self.phases:
            return ""

        phases_to_report = self.phases[-num_prev_phases:]
        game_history_str = ""

        # Iterate through phases
        for phase in phases_to_report:
            game_history_str += f"\n{phase.name}:\n"

            # Add GLOBAL section for this phase
            global_msgs = phase.get_global_messages()
            if global_msgs:
                game_history_str += "\nGLOBAL:\n"
                game_history_str += global_msgs

            # Add PRIVATE section for this phase
            private_msgs = phase.get_private_messages(power_name)
            if private_msgs:
                game_history_str += "\nPRIVATE:\n"
                for other_power, messages in private_msgs.items():
                    game_history_str += f" {other_power}:\n\n"
                    game_history_str += messages + "\n"

            # Add ORDERS section for this phase
            if phase.orders_by_power:
                game_history_str += "\nORDERS:\n"
                for power, orders in phase.orders_by_power.items():
                    game_history_str += f"{power}:\n"
                    results = phase.results_by_power.get(power, [])
                    for i, order in enumerate(orders):
                        if (
                            i < len(results)
                            and results[i]
                            and not all(r == "" for r in results[i])
                        ):
                            # Join multiple results with commas
                            result_str = f" ({', '.join(results[i])})"
                        else:
                            result_str = " (successful)"
                        game_history_str += f"  {order}{result_str}\n"
                    game_history_str += "\n"

            game_history_str += "-" * 50 + "\n"  # Add separator between phases
            
        # NOTE: only reports plan for the last phase (otherwise too much clutter)
        if include_plans and phases_to_report and (power_name in phases_to_report[-1].plans):
            game_history_str += f"\n{power_name} STRATEGIC DIRECTIVE:\n"
            game_history_str += "Here is a high-level directive you have planned out previously for this phase.\n"
            game_history_str += phases_to_report[-1].plans[power_name] + "\n"

        return game_history_str
