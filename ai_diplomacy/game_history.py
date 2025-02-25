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
    messages: List[Message] = field(default_factory=list)
    orders_by_power: Dict[str, List[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    results_by_power: Dict[str, List[List[str]]] = field(
        default_factory=lambda: defaultdict(list)
    )

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

    def add_phase(self, phase_name: str) -> Phase:
        # Check if phase already exists
        for phase in self.phases:
            if phase.name == phase_name:
                return phase

        # Create new phase
        new_phase = Phase(name=phase_name)
        self.phases.append(new_phase)
        return new_phase

    def add_message(self, phase_name: str, sender: str, recipient: str, content: str):
        phase = self.add_phase(phase_name)
        phase.add_message(sender, recipient, content)

    def add_orders(
        self, phase_name: str, power: str, orders: List[str], results: List[List[str]]
    ):
        phase = self.add_phase(phase_name)
        phase.add_orders(power, orders, results)

    def get_game_history(self, power_name: str, num_prev_phases: int = 5) -> str:
        if not self.phases:
            logger.debug(f"HISTORY | {power_name} | No phases recorded yet")
            return "COMMUNICATION HISTORY:\n\n(No game phases recorded yet)"

        phases_to_report = self.phases[-num_prev_phases:]
        game_history_str = "COMMUNICATION HISTORY:\n"

        # Count messages for this power across all available phases, not just recent
        # This helps ensure we're not misreporting "no communication" when there is historical context
        all_phases_message_count = 0
        for phase in self.phases:
            global_msgs = phase.get_global_messages()
            private_msgs = phase.get_private_messages(power_name)
            if global_msgs or private_msgs:
                all_phases_message_count += 1
                
        # Count messages just in recent phases for display decisions
        recent_phases_message_count = 0
        for phase in phases_to_report:
            global_msgs = phase.get_global_messages()
            private_msgs = phase.get_private_messages(power_name)
            if global_msgs or private_msgs:
                recent_phases_message_count += 1
        
        logger.debug(f"HISTORY | {power_name} | Found {all_phases_message_count} phases with messages (total), {recent_phases_message_count} in recent phases")

        # If there are no messages at all in any phase, provide a clear indicator
        if all_phases_message_count == 0:
            game_history_str += f"\n{power_name} has not engaged in any diplomatic exchanges yet.\n"
            logger.debug(f"HISTORY | {power_name} | No diplomatic exchanges found in any phase")
            return game_history_str
        
        # If there are messages in history but none in recent phases, note this
        if all_phases_message_count > 0 and recent_phases_message_count == 0:
            game_history_str += f"\n{power_name} has messages in earlier phases, but none in the last {len(phases_to_report)} phases.\n"
            logger.debug(f"HISTORY | {power_name} | Has historical messages but none in recent phases")
        
        # Track if we have content for debugging
        has_content = False

        # Iterate through phases
        for phase in phases_to_report:
            phase_has_content = False
            phase_str = f"\n{phase.name}:\n"

            # Add GLOBAL section for this phase
            global_msgs = phase.get_global_messages()
            if global_msgs:
                phase_str += "\nGLOBAL:\n"
                phase_str += global_msgs
                phase_has_content = True
                has_content = True

            # Add PRIVATE section for this phase
            private_msgs = phase.get_private_messages(power_name)
            if private_msgs:
                phase_str += "\nPRIVATE:\n"
                for other_power, messages in private_msgs.items():
                    phase_str += f" {other_power}:\n\n"
                    phase_str += messages + "\n"
                phase_has_content = True
                has_content = True
            
            # Only add ORDERS section if we have any content in this phase
            # or if it's the most recent phase (always include latest orders)
            is_latest_phase = phase == phases_to_report[-1]
            
            if phase_has_content or is_latest_phase:
                # Add ORDERS section for this phase
                if phase.orders_by_power:
                    phase_str += "\nORDERS:\n"
                    for power, orders in phase.orders_by_power.items():
                        phase_str += f"{power}:\n"
                        if not orders:
                            phase_str += "  (No orders)\n\n"
                            continue
                        
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
                            phase_str += f"  {order}{result_str}\n"
                        phase_str += "\n"
                
                # Only add this phase to the history if it has content or is the latest phase
                game_history_str += phase_str
                game_history_str += "-" * 50 + "\n"  # Add separator between phases

        # If we have no content at all, provide a meaningful message
        if not has_content:
            logger.warning(f"HISTORY | {power_name} | No message content found for display, providing fallback message")
            # Don't overwrite previous content - append this explanation
            game_history_str += f"\nNote: No diplomatic communications to display for {power_name} in recent phases.\n"
        else:
            logger.debug(f"HISTORY | {power_name} | Generated history with content from {recent_phases_message_count} phases")
        
        return game_history_str
