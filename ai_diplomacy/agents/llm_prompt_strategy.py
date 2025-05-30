"""
Defines strategies for constructing various prompts for LLM-based agents.

This module provides the LLMPromptStrategy class, which contains methods
for building specific prompts required by LLM agents during different
phases of a Diplomacy game (e.g., order generation, negotiation, diary entry).
"""
from typing import List, Dict, Any

__all__ = ["LLMPromptStrategy"]

class LLMPromptStrategy:
    # Class docstring already exists and is good.

    def __init__(self) -> None:
        """
        Initializes the prompt strategy.
        (No specific initialization needed for now).
        """
        pass

    def build_order_prompt(
        self,
        country: str,
        goals: List[str],
        relationships: Dict[str, str],
        formatted_diary: str,
        context_text: str,
        tools_available: bool,
    ) -> str:
        """
        Constructs the prompt for order generation.
        """
        goals_str = "\n".join(f"- {goal}" for goal in goals) if goals else "No specific goals set."
        relationships_str = "\n".join(
            f"- {power}: {status}" for power, status in relationships.items()
        ) if relationships else "No specific relationship data."

        tool_instruction = ""
        if tools_available:
            tool_instruction = (
                "\n\nIf you need to access external information or perform complex calculations "
                "to make your decision, you can use the available tools. "
                "To use a tool, output a JSON object with a 'tool_name' and 'tool_input' field. "
                "For example: {\"tool_name\": \"calculator\", \"tool_input\": \"2+2\"}. "
                "Wait for the tool's response before proceeding with your orders. "
                "If you do not need a tool, provide your orders directly."
            )

        prompt = f"""You are an AI agent playing as {country} in a game of Diplomacy.
It is currently the order generation phase.

Your Goals:
{goals_str}

Your Relationships with other powers:
{relationships_str}

Recent Diary Entries:
{formatted_diary}

Game Context and Relevant Information:
{context_text}
{tool_instruction}

Based on all the information above, your strategic goals, and your relationships, decide on your orders for this phase.
Return your response as a JSON object with a single key "orders", which should be a list of strings.
Each string in the list is an order. For example:
{{
  "orders": [
    "A BUD H",
    "A VIE - GAL",
    "F TRI - ADR"
  ]
}}
Do not add any commentary or explanation outside of the JSON structure.
Ensure your orders are valid and strategically sound.
"""
        return prompt

    def build_negotiation_prompt(
        self,
        country: str,
        active_powers: List[str],
        goals: List[str],
        relationships: Dict[str, str],
        formatted_diary: str,
        context_text: str,
        tools_available: bool,
    ) -> str:
        """
        Constructs the prompt for generating diplomatic messages.
        """
        goals_str = "\n".join(f"- {goal}" for goal in goals) if goals else "No specific goals set."
        relationships_str = "\n".join(
            f"- {power}: {status}" for power, status in relationships.items()
        ) if relationships else "No specific relationship data."
        
        active_powers_str = ", ".join(active_powers) if active_powers else "None"

        tool_instruction = ""
        if tools_available:
            tool_instruction = (
                "\n\nIf you need to access external information or perform complex calculations "
                "to formulate your messages, you can use the available tools. "
                "To use a tool, output a JSON object with a 'tool_name' and 'tool_input' field. "
                "Wait for the tool's response before proceeding with your messages. "
                "If you do not need a tool, provide your messages directly."
            )

        prompt = f"""You are an AI agent playing as {country} in a game of Diplomacy.
It is currently the diplomatic negotiation phase.
The other active powers in the game are: {active_powers_str}.

Your Goals:
{goals_str}

Your Relationships with other powers:
{relationships_str}

Recent Diary Entries:
{formatted_diary}

Game Context and Relevant Information (e.g., messages from previous phases, current board state):
{context_text}
{tool_instruction}

Based on all the information above, your strategic goals, and your relationships, decide on any diplomatic messages you want to send to other powers.
Return your response as a JSON object with a single key "messages".
The value of "messages" should be a list of JSON objects, where each object represents a message and has the following structure:
{{
  "recipient": "COUNTRY_NAME",  // The country you are sending the message to
  "content": "Your message text here...", // The actual message content
  "message_type": "PROPOSAL" // Type of message (e.g., PROPOSAL, INFO, WARNING, QUESTION, RESPONSE, CHAT)
}}
For example:
{{
  "messages": [
    {{
      "recipient": "FRANCE",
      "content": "Shall we form an alliance against Germany?",
      "message_type": "PROPOSAL"
    }},
    {{
      "recipient": "GERMANY",
      "content": "I noticed your army in Burgundy. I have no aggressive intentions towards you at this time.",
      "message_type": "INFO"
    }}
  ]
}}
If you do not want to send any messages this phase, return an empty list: {{"messages": []}}.
Do not add any commentary or explanation outside of the JSON structure.
Ensure your messages are strategically sound and contribute to your goals.
"""
        return prompt

    def build_diary_generation_prompt(
        self,
        country: str,
        phase_name: str,
        power_units: List[str],
        power_centers: List[str],
        is_game_over: bool,
        events: List[Dict[str, Any]],
        goals: List[str],
        relationships: Dict[str, str],
    ) -> str:
        """
        Constructs the prompt for generating a diary entry.
        """
        units_str = ", ".join(power_units) if power_units else "None"
        centers_str = ", ".join(power_centers) if power_centers else "None"
        goals_str = "\n".join(f"- {goal}" for goal in goals) if goals else "No specific goals set."
        relationships_str = "\n".join(
            f"- {power}: {status}" for power, status in relationships.items()
        ) if relationships else "No specific relationship data."
        
        events_str = "\n".join(str(event) for event in events) if events else "No significant events."

        game_status = "The game is now over." if is_game_over else "The game is ongoing."

        prompt = f"""You are an AI agent playing as {country} in a game of Diplomacy.
The phase '{phase_name}' has just concluded.
{game_status}

Your situation:
- Your Units: {units_str}
- Your Supply Centers: {centers_str}
- Your Current Goals:
{goals_str}
- Your Relationships:
{relationships_str}

Events that occurred during the '{phase_name}' phase:
{events_str}

Reflect on what happened in this phase. Consider the outcomes of your orders, any surprising moves by other powers, changes in your relationships, and progress towards your goals.
Write a brief, insightful diary entry from the perspective of {country}. This entry is for your private thoughts and should help you plan for future phases.
Focus on your key observations, successes, failures, and any new intentions or suspicions.

Return your response as a JSON object with a single key "diary_entry", which should be a string.
For example:
{{
  "diary_entry": "The move to Burgundy was successful, but Germany's support for Austria in Galicia is concerning. I need to watch Germany closely. Italy seems open to an alliance."
}}
Do not add any commentary or explanation outside of the JSON structure.
"""
        return prompt

    def build_goal_analysis_prompt(
        self,
        country: str,
        phase_name: str,
        power_units: List[str],
        power_centers: List[str],
        all_power_centers: Dict[str, int], # Map of power_name to num_centers
        is_game_over: bool,
        current_goals: List[str],
        relationships: Dict[str, str],
    ) -> str:
        """
        Constructs the prompt for goal analysis and potential updates.
        """
        units_str = ", ".join(power_units) if power_units else "None"
        centers_str = ", ".join(power_centers) if power_centers else "None"
        current_goals_str = "\n".join(f"- {goal}" for goal in current_goals) if current_goals else "No specific goals currently set."
        relationships_str = "\n".join(
            f"- {power}: {status}" for power, status in relationships.items()
        ) if relationships else "No specific relationship data."
        
        all_power_centers_str = "\n".join(
            f"- {power}: {count} centers" for power, count in all_power_centers.items()
        ) if all_power_centers else "Supply center data unavailable."
        
        game_status = "The game is now over." if is_game_over else "The game is ongoing."

        prompt = f"""You are an AI agent playing as {country} in a game of Diplomacy.
The phase '{phase_name}' has just concluded.
{game_status}

Your Current Situation:
- Your Units: {units_str}
- Your Supply Centers ({len(power_centers)}): {centers_str}
- Your Current Goals:
{current_goals_str}
- Your Relationships:
{relationships_str}

Overall Game State:
- Supply Center Counts for all Powers:
{all_power_centers_str}

Analyze your current situation, the overall game state, your relationships, and your progress towards your current goals.
Consider if your current goals are still relevant and achievable.
Suggest a new list of strategic goals for the upcoming phases. These goals should be concrete and actionable.
Provide a brief reasoning for your suggested goals.

Return your response as a JSON object with two keys: "updated_goals" and "reasoning".
- "updated_goals": A list of strings, where each string is a goal.
- "reasoning": A string explaining your analysis and why these new goals are appropriate.

For example:
{{
  "updated_goals": [
    "Secure an alliance with Italy to counter German expansion.",
    "Gain control of Munich by Fall 1903.",
    "Prevent England from establishing a naval presence in the North Sea."
  ],
  "reasoning": "Germany has become the primary threat with 7 centers. An alliance with Italy (5 centers) is crucial for mutual defense and to apply pressure on Germany's southern front. Capturing Munich is key to weakening Germany. England (4 centers) is attempting to expand southwards, which needs to be checked to protect my northern centers."
}}
If the game is over, the goals might reflect on final objectives or be empty.
If no change to goals is needed, you can return the current goals.
Do not add any commentary or explanation outside of the JSON structure.
"""
        return prompt

# Example Usage (can be removed or kept for testing)
if __name__ == "__main__":
    strategy = LLMPromptStrategy()

    # Example for build_order_prompt
    order_prompt = strategy.build_order_prompt(
        country="FRANCE",
        goals=["Capture Munich", "Secure Belgium"],
        relationships={"GERMANY": "Enemy", "ENGLAND": "Friendly"},
        formatted_diary="[Spring 1901] Moved to Burgundy. Germany seems aggressive.",
        context_text="Current Phase: Fall 1901 Movement. Germany has units in Ruhr and Munich. England has fleets in North Sea.",
        tools_available=True,
    )
    print("--- ORDER PROMPT ---")
    print(order_prompt)

    # Example for build_negotiation_prompt
    negotiation_prompt = strategy.build_negotiation_prompt(
        country="ITALY",
        active_powers=["FRANCE", "GERMANY", "AUSTRIA", "TURKEY", "RUSSIA", "ENGLAND"],
        goals=["Form a defensive alliance against Austria", "Gain control of Tunis"],
        relationships={"AUSTRIA": "Enemy", "FRANCE": "Neutral", "TURKEY": "Friendly"},
        formatted_diary="[Spring 1901] Austria moved to Tyrolia, seems hostile.",
        context_text="Messages from Spring 1901: France proposed a DMZ in Piedmont. Austria has not responded to requests.",
        tools_available=False,
    )
    print("\n--- NEGOTIATION PROMPT ---")
    print(negotiation_prompt)

    # Example for build_diary_generation_prompt
    diary_prompt = strategy.build_diary_generation_prompt(
        country="RUSSIA",
        phase_name="Fall 1902 Movement",
        power_units=["A MOS", "A WAR", "F STP/SC", "F SEV"],
        power_centers=["MOSCOW", "WARSAW", "STPETERSBURG", "SEVASTOPOL"],
        is_game_over=False,
        events=[
            {"type": "MOVE", "unit": "A WAR", "destination": "GAL", "success": True},
            {"type": "ATTACK", "attacker": "TURKEY", "target_unit": "F SEV", "success": False},
        ],
        goals=["Expand southwards", "Secure Warsaw"],
        relationships={"TURKEY": "Enemy", "GERMANY": "Neutral"},
    )
    print("\n--- DIARY GENERATION PROMPT ---")
    print(diary_prompt)

    # Example for build_goal_analysis_prompt
    goal_analysis_prompt = strategy.build_goal_analysis_prompt(
        country="ENGLAND",
        phase_name="Spring 1903 Build Phase",
        power_units=["F LON", "F EDI", "A LVP"],
        power_centers=["LONDON", "EDINBURGH", "LIVERPOOL"],
        all_power_centers={"ENGLAND": 3, "FRANCE": 5, "GERMANY": 6, "RUSSIA": 4, "AUSTRIA": 3, "ITALY": 3, "TURKEY": 2},
        is_game_over=False,
        current_goals=["Prevent French naval dominance", "Secure North Sea"],
        relationships={"FRANCE": "Unfriendly", "GERMANY": "Neutral"},
    )
    print("\n--- GOAL ANALYSIS PROMPT ---")
    print(goal_analysis_prompt)
