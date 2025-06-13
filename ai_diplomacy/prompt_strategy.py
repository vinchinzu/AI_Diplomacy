"""
Defines strategies for constructing various prompts for LLM-based agents.

This module provides:
- BasePromptStrategy: An abstract base class for generic prompt strategies.
"""

import logging
from typing import Optional, Dict, List, Any

# Assuming llm_utils will be in the same generic framework package.
# This import is for BasePromptStrategy's _load_generic_system_prompt
from generic_llm_framework.prompt_strategy import BasePromptStrategy

logger = logging.getLogger(__name__)

__all__ = ["BasePromptStrategy", "DiplomacyPromptStrategy"]


class DiplomacyPromptStrategy(BasePromptStrategy):  # Inherit from BasePromptStrategy
    """
    Handles construction of prompts for various LLM interactions specific to the game of Diplomacy.
    This class implements the generic build_prompt method by dispatching to its
    Diplomacy-specific prompt construction methods.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        base_prompts_dir: Optional[str] = None,
    ) -> None:
        """
        Initializes the Diplomacy-specific prompt strategy.
        Args:
            config: A generic configuration dictionary, may contain diplomacy specific settings.
            base_prompts_dir: Optional. Path to the base directory for prompts.
        """
        super().__init__(config, base_prompts_dir)
        # DiplomacyPromptStrategy might have its own specific system prompt or use the generic one.
        # If it needs a different system prompt than generic_system_prompt.txt,
        # it can override _load_generic_system_prompt or load its own template here.
        # For now, it will inherit the generic system prompt loading.
        # Example: self.diplomacy_system_prompt = self._load_diplomacy_system_prompt()

    def build_prompt(self, action_type: str, context: Dict[str, Any]) -> str:
        """
        Builds a Diplomacy-specific prompt based on the action_type and context.
        This method routes to the appropriate specialized prompt building method.
        """
        if action_type == "decide_diplomacy_orders":
            # Ensure all necessary keys are in context, or handle missing keys
            # Expected keys by build_order_prompt: country, goals, relationships, formatted_diary, context_text, tools_available
            return self.build_order_prompt(
                country=context.get("country"),
                goals=context.get("goals", []),
                relationships=context.get("relationships", {}),
                formatted_diary=context.get("formatted_diary", ""),
                context_text=context.get("context_text", ""),
                tools_available=context.get("tools_available", False),
            )
        elif action_type == "generate_diplomacy_messages":
            # Expected keys: country, active_powers, goals, relationships, formatted_diary, context_text, tools_available
            return self.build_negotiation_prompt(
                country=context.get("country"),
                active_powers=context.get("active_powers", []),
                goals=context.get("goals", []),
                relationships=context.get("relationships", {}),
                formatted_diary=context.get("formatted_diary", ""),
                context_text=context.get("context_text", ""),
                tools_available=context.get("tools_available", False),
            )
        elif action_type == "generate_diplomacy_diary":
            # Expected keys: country, phase_name, power_units, power_centers, is_game_over, events, goals, relationships
            return self.build_diary_generation_prompt(
                country=context.get("country"),
                phase_name=context.get("phase_name", "Unknown Phase"),
                power_units=context.get("power_units", []),
                power_centers=context.get("power_centers", []),
                is_game_over=context.get("is_game_over", False),
                events=context.get("events", []),
                goals=context.get("goals", []),
                relationships=context.get("relationships", {}),
            )
        elif action_type == "analyze_diplomacy_goals":
            # Expected keys: country, phase_name, power_units, power_centers, all_power_centers, is_game_over, current_goals, relationships
            return self.build_goal_analysis_prompt(
                country=context.get("country"),
                phase_name=context.get("phase_name", "Unknown Phase"),
                power_units=context.get("power_units", []),
                power_centers=context.get("power_centers", []),
                all_power_centers=context.get("all_power_centers", {}),
                is_game_over=context.get("is_game_over", False),
                current_goals=context.get("current_goals", []),
                relationships=context.get("relationships", {}),
            )
        elif action_type == "decide_bloc_orders":  # For BlocLLMAgent
            # This action_type implies the context contains a pre-rendered prompt
            if "prompt_content" not in context:
                logger.error("Context must contain 'prompt_content' for 'decide_bloc_orders'")
                raise ValueError("Context must contain 'prompt_content' for 'decide_bloc_orders'")
            # The system prompt for bloc agent might be different, handled by BlocLLMAgent itself
            # or passed in context if generic_agent needs to set it.
            # For now, assume prompt_content is the full user prompt.
            return context["prompt_content"]
        elif action_type == "update_goals":
            # Use the state_update_prompt.txt template for updating goals and relationships
            return self.build_update_goals_prompt(context)
        elif action_type == "generate_diary_entry":
            # Treat as a diary/phase reflection, use the same logic as generate_diplomacy_diary
            return self.build_diary_generation_prompt(
                country=context.get("country"),
                phase_name=context.get("phase_name", "Unknown Phase"),
                power_units=context.get("power_units", []),
                power_centers=context.get("power_centers", []),
                is_game_over=context.get("is_game_over", False),
                events=context.get("events", []),
                goals=context.get("goals", []),
                relationships=context.get("relationships", {}),
            )
        else:  # This is the single, final else block
            logger.warning(
                f"Unknown action_type '{action_type}' for DiplomacyPromptStrategy. Falling back to generic system prompt or error."
            )
            # Fallback or error, or try to use a generic prompt if BasePromptStrategy has one
            # For now, let's indicate an issue.
            # return super().build_prompt(action_type, context) # If BasePromptStrategy had a default
            raise ValueError(f"Unsupported action_type for DiplomacyPromptStrategy: {action_type}")

    # The existing Diplomacy-specific methods (build_order_prompt, etc.) remain below.
    # Their signatures are assumed to be correct as per the file's current state.

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
        Constructs the prompt for Diplomacy order generation.
        """
        goals_str = "\n".join(f"- {goal}" for goal in goals) if goals else "No specific goals set."
        relationships_str = (
            "\n".join(f"- {power}: {status}" for power, status in relationships.items())
            if relationships
            else "No specific relationship data."
        )

        tool_instruction = ""
        if tools_available:
            tool_instruction = (
                "\n\nIf you need to access external information or perform complex calculations "
                "to make your decision, you can use the available tools. "
                "To use a tool, output a JSON object with a 'tool_name' and 'tool_input' field. "
                'For example: {"tool_name": "calculator", "tool_input": "2+2"}. '
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
        Constructs the prompt for generating Diplomacy diplomatic messages.
        """
        goals_str = "\n".join(f"- {goal}" for goal in goals) if goals else "No specific goals set."
        relationships_str = (
            "\n".join(f"- {power}: {status}" for power, status in relationships.items())
            if relationships
            else "No specific relationship data."
        )

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
        Constructs the prompt for generating a Diplomacy diary entry.
        """
        units_str = ", ".join(power_units) if power_units else "None"
        centers_str = ", ".join(power_centers) if power_centers else "None"
        goals_str = "\n".join(f"- {goal}" for goal in goals) if goals else "No specific goals set."
        relationships_str = (
            "\n".join(f"- {power}: {status}" for power, status in relationships.items())
            if relationships
            else "No specific relationship data."
        )

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
        all_power_centers: Dict[str, int],  # Map of power_name to num_centers
        is_game_over: bool,
        current_goals: List[str],
        relationships: Dict[str, str],
    ) -> str:
        """
        Constructs the prompt for Diplomacy goal analysis and potential updates.
        """
        units_str = ", ".join(power_units) if power_units else "None"
        centers_str = ", ".join(power_centers) if power_centers else "None"
        current_goals_str = (
            "\n".join(f"- {goal}" for goal in current_goals)
            if current_goals
            else "No specific goals currently set."
        )
        relationships_str = (
            "\n".join(f"- {power}: {status}" for power, status in relationships.items())
            if relationships
            else "No specific relationship data."
        )

        all_power_centers_str = (
            "\n".join(f"- {power}: {count} centers" for power, count in all_power_centers.items())
            if all_power_centers
            else "Supply center data unavailable."
        )

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

    def build_update_goals_prompt(self, context: Dict[str, Any]) -> str:
        """
        Constructs the prompt for updating goals and relationships after a phase.
        Uses the state_update_prompt.txt template.
        """
        from ai_diplomacy.prompt_utils import load_prompt
        
        template = load_prompt("state_update_prompt.txt")
        
        # Extract context values with defaults
        power_name = context.get("power_name") or context.get("country") or "UNKNOWN"
        current_year = context.get("current_year", "UNKNOWN")
        current_phase = context.get("current_phase") or context.get("phase_name") or "UNKNOWN"
        board_state_str = context.get("board_state_str", "(No board state)")
        phase_summary = context.get("phase_summary", "(No summary)")
        current_goals = context.get("current_goals", [])
        current_relationships = context.get("current_relationships", {})
        other_powers = context.get("other_powers")
        if other_powers is None:
            # Try to infer from relationships keys if not provided
            if isinstance(current_relationships, dict):
                other_powers = list(current_relationships.keys())
            else:
                other_powers = []
        
        # Format for template
        current_goals_str = "\n".join(f"- {g}" for g in current_goals) if current_goals else "None"
        current_relationships_str = (
            "\n".join(f"- {p}: {s}" for p, s in current_relationships.items())
            if isinstance(current_relationships, dict) and current_relationships else "None"
        )
        other_powers_str = ", ".join(other_powers) if other_powers else "None"
        
        prompt = template.format(
            power_name=power_name,
            current_year=current_year,
            current_phase=current_phase,
            board_state_str=board_state_str,
            phase_summary=phase_summary,
            current_goals=current_goals_str,
            current_relationships=current_relationships_str,
            other_powers=other_powers_str,
        )
        return prompt
