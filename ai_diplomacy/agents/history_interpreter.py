"""
Functions to interpret and format game history for consumption by AI agents.
"""

from __future__ in annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from ai_diplomacy.domain.history import GameHistory, Message, Phase

logger = logging.getLogger(__name__)


def get_messages_this_round(
    history: GameHistory, power_name: str, current_phase_name: str
) -> str:
    current_phase: Optional[Phase] = None
    for phase_obj in history.phases:
        if phase_obj.name == current_phase_name:
            current_phase = phase_obj
            break

    if not current_phase:
        return f"\n(No messages found for current phase: {current_phase_name})\n"

    messages_str = ""

    # Helper to get global messages from a phase
    global_msgs_content = ""
    for msg in current_phase.messages:
        if msg.recipient == "GLOBAL":
            global_msgs_content += f" {msg.sender}: {msg.content}\n"

    if global_msgs_content:
        messages_str += "**GLOBAL MESSAGES THIS ROUND:**\n"
        messages_str += global_msgs_content
    else:
        messages_str += "**GLOBAL MESSAGES THIS ROUND:**\n (No global messages this round)\n"

    # Helper to get private messages from a phase
    conversations = defaultdict(str)
    for msg in current_phase.messages:
        if msg.sender == power_name and msg.recipient != "GLOBAL":
            conversations[msg.recipient] += f"  {power_name}: {msg.content}\n"
        elif msg.recipient == power_name:
            conversations[msg.sender] += f"  {msg.sender}: {msg.content}\n"

    if conversations:
        messages_str += "\n**PRIVATE MESSAGES TO/FROM YOU THIS ROUND:**\n"
        for other_power, conversation_content in conversations.items():
            messages_str += f" Conversation with {other_power}:\n"
            messages_str += conversation_content
            messages_str += "\n"
    else:
        messages_str += (
            "\n**PRIVATE MESSAGES TO/FROM YOU THIS ROUND:**\n (No private messages this round)\n"
        )

    if not global_msgs_content and not conversations:
        return f"\n(No messages recorded for current phase: {current_phase_name})\n"

    return messages_str.strip()


def get_recent_messages_to_power(history: GameHistory, power_name: str, limit: int = 3) -> List[Dict[str, str]]:
    """
    Gets the most recent messages sent TO this power, useful for tracking messages that need replies.
    Returns a list of dictionaries with 'sender', 'content', and 'phase' keys.
    """
    if not history.phases:
        return []

    recent_phases = history.phases[-2:] if len(history.phases) >= 2 else history.phases[-1:]

    messages_to_power = []
    for phase in recent_phases:
        for msg in phase.messages:
            if msg.recipient == power_name or (msg.recipient == "GLOBAL" and msg.sender != power_name):
                if msg.sender != power_name:
                    messages_to_power.append(
                        {
                            "sender": msg.sender,
                            "content": msg.content,
                            "phase": phase.name,
                        }
                    )

    logger.debug(
        f"Found {len(messages_to_power)} messages to {power_name} across {len(recent_phases)} phases"
    )
    if not messages_to_power:
        logger.debug(f"No messages found for {power_name} to respond to")

    return messages_to_power[-limit:] if messages_to_power else []


def get_ignored_messages_by_power(
    history: GameHistory, sender_name: str, num_phases: int = 3
) -> Dict[str, List[Dict[str, str]]]:
    """
    Identifies which powers are not responding to messages from sender_name.
    Returns a dict mapping power names to their ignored messages.

    A message is considered ignored if:
    1. It was sent from sender_name to another power (private)
    2. No response from that power was received in the same or next phase
    """
    ignored_by_power = {}

    recent_phases = history.phases[-num_phases:] if history.phases else []
    if not recent_phases:
        return ignored_by_power

    for i, phase in enumerate(recent_phases):
        sender_messages = []
        for msg in phase.messages:
            if isinstance(msg, Message):
                if msg.sender == sender_name and msg.recipient not in [
                    "GLOBAL",
                    "ALL",
                ]:
                    sender_messages.append(msg)
            else:
                if msg["sender"] == sender_name and msg["recipient"] not in [
                    "GLOBAL",
                    "ALL",
                ]:
                    sender_messages.append(msg)

        for msg in sender_messages:
            if isinstance(msg, Message):
                recipient = msg.recipient
                msg_content = msg.content
            else:
                recipient = msg["recipient"]
                msg_content = msg["content"]

            found_response = False

            for check_phase in recent_phases[i : min(i + 2, len(recent_phases))]:
                response_msgs = []
                for m in check_phase.messages:
                    if isinstance(m, Message):
                        if m.sender == recipient and (
                            m.recipient == sender_name
                            or (m.recipient in ["GLOBAL", "ALL"] and sender_name in m.content)
                        ):
                            response_msgs.append(m)
                    else:
                        if m["sender"] == recipient and (
                            m["recipient"] == sender_name
                            or (
                                m["recipient"] in ["GLOBAL", "ALL"]
                                and sender_name in m.get("content", "")
                            )
                        ):
                            response_msgs.append(m)

                if response_msgs:
                    found_response = True
                    break

            if not found_response:
                if recipient not in ignored_by_power:
                    ignored_by_power[recipient] = []
                ignored_by_power[recipient].append({"phase": phase.name, "content": msg_content})

    return ignored_by_power


def get_previous_phases_history(
    history: GameHistory,
    power_name: str,
    current_phase_name: str,
    include_plans: bool = True,
    num_prev_phases: int = 5,
) -> str:
    if not history.phases:
        return "\n(No game history available)\n"

    relevant_phases = [p for p in history.phases if p.name != current_phase_name]

    if not relevant_phases:
        return "\n(No previous game history before this round)\n"

    phases_to_report = relevant_phases[-num_prev_phases:]

    if not phases_to_report:
        return "\n(No previous game history available within the lookback window)\n"

    game_history_str = ""

    for phase_idx, phase in enumerate(phases_to_report):
        phase_content_str = f"\nPHASE: {phase.name}\n"
        current_phase_has_content = False

        # Helper to get global messages
        global_msgs = ""
        for msg in phase.messages:
            if msg.recipient == "GLOBAL":
                global_msgs += f" {msg.sender}: {msg.content}\n"

        if global_msgs:
            phase_content_str += "\n  GLOBAL MESSAGES:\n"
            phase_content_str += "".join([f"    {line}\n" for line in global_msgs.strip().split("\n")])
            current_phase_has_content = True

        # Helper to get private messages
        private_msgs = defaultdict(str)
        for msg in phase.messages:
            if msg.sender == power_name and msg.recipient != "GLOBAL":
                private_msgs[msg.recipient] += f"  {power_name}: {msg.content}\n"
            elif msg.recipient == power_name:
                private_msgs[msg.sender] += f"  {msg.sender}: {msg.content}\n"

        if private_msgs:
            phase_content_str += "\n  PRIVATE MESSAGES:\n"
            for other_power, messages in private_msgs.items():
                phase_content_str += f"    Conversation with {other_power}:\n"
                phase_content_str += "".join([f"      {line}\n" for line in messages.strip().split("\n")])
            current_phase_has_content = True

        if phase.orders_by_power:
            phase_content_str += "\n  ORDERS:\n"
            for power, orders in phase.orders_by_power.items():
                indicator = " (your power)" if power == power_name else ""
                phase_content_str += f"    {power}{indicator}:\n"
                results = phase.results_by_power.get(power, [])
                for i, order in enumerate(orders):
                    result_str = " (successful)"
                    if i < len(results) and results[i] and not all(r == "" for r in results[i]):
                        result_str = f" ({', '.join(results[i])})"
                    phase_content_str += f"      {order}{result_str}\n"
                phase_content_str += "\n"
            current_phase_has_content = True

        if current_phase_has_content:
            if not game_history_str:
                game_history_str = (
                    "**PREVIOUS GAME HISTORY (Messages, Orders, & Plans from older rounds & phases)**\n"
                )
            game_history_str += phase_content_str
            if phase_idx < len(phases_to_report) - 1:
                game_history_str += "  " + "-" * 48 + "\n"

    if include_plans and phases_to_report:
        last_reported_previous_phase = phases_to_report[-1]
        if last_reported_previous_phase.plans:
            if not game_history_str:
                game_history_str = (
                    "**PREVIOUS GAME HISTORY (Messages, Orders, & Plans from older rounds & phases)**\n"
                )
            game_history_str += f"\n  PLANS SUBMITTED FOR PHASE {last_reported_previous_phase.name}:\n"
            if power_name in last_reported_previous_phase.plans:
                game_history_str += f"    Your Plan: {last_reported_previous_phase.plans[power_name]}\n"
            for p_other, plan_other in last_reported_previous_phase.plans.items():
                if p_other != power_name:
                    game_history_str += f"    {p_other}'s Plan: {plan_other}\n"
            game_history_str += "\n"

    if not game_history_str.replace(
        "**PREVIOUS GAME HISTORY (Messages, Orders, & Plans from older rounds & phases)**\n",
        "",
    ).strip():
        return "\n(No relevant previous game history to display)\n"

    return game_history_str.strip() 