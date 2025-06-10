"""
Defines strategies for constructing various prompts for LLM-based agents.

This module provides:
- BasePromptStrategy: An abstract base class for generic prompt strategies.
- DiplomacyPromptStrategy: A concrete implementation for Diplomacy game agents
  (this was the original content of this file after a previous refactoring step).
"""

import logging
from typing import Optional, Dict, List, Any

# Assuming llm_utils will be in the same generic framework package.
# This import is for BasePromptStrategy's _load_generic_system_prompt
from . import llm_utils # Ensure this is available
from typing import Optional, Dict, List, Any # Ensure these are available at the top

logger = logging.getLogger(__name__)

__all__ = ["BasePromptStrategy", "DiplomacyPromptStrategy"]


class BasePromptStrategy:
    """
    Base class for managing the construction of prompts for different LLM interaction types.
    Subclasses should implement specific prompt building logic.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, base_prompts_dir: Optional[str] = None):
        """
        Initializes the BasePromptStrategy.

        Args:
            config: A generic configuration dictionary.
            base_prompts_dir: Optional. Path to the base directory for prompts.
        """
        self.config = config or {}
        self.base_prompts_dir = base_prompts_dir
        self.system_prompt_template = self._load_generic_system_prompt()

    def _load_generic_system_prompt(self) -> str:
        """Loads a generic system prompt template from file or provides a default."""
        filename = self.config.get("system_prompt_filename", "generic_system_prompt.txt")
        prompt_content = llm_utils.load_prompt_file(
            filename, base_prompts_dir=self.base_prompts_dir
        )
        if prompt_content is None:
            logger.warning(
                f"Failed to load generic system prompt '{filename}'. Using a default prompt."
            )
            return "You are a helpful AI assistant."
        return prompt_content

    def _get_formatted_system_prompt(self, **kwargs) -> str:
        """Formats the system prompt with provided arguments."""
        try:
            return self.system_prompt_template.format(**kwargs)
        except KeyError as e:
            logger.error(
                f"Missing key in system prompt formatting: {e}. Using raw template."
            )
            return self.system_prompt_template
        except Exception as e:
            logger.error(f"Error formatting system prompt: {e}. Using raw template.")
            return self.system_prompt_template

    def build_prompt(self, action_type: str, context: Dict[str, Any]) -> str:
        """
        Builds a prompt for a given action type and context.
        This is the primary method for generic agents.

        Args:
            action_type: A string identifying the type of action (e.g., "decide_action", "generate_communication").
            context: A dictionary containing all necessary information to build the prompt.

        Returns:
            The constructed prompt string.
        """
        raise NotImplementedError("Subclasses must implement build_prompt.")


class DiplomacyPromptStrategy(BasePromptStrategy): # Inherit from BasePromptStrategy
    """
    Handles construction of prompts for various LLM interactions specific to the game of Diplomacy.
    This class implements the generic build_prompt method by dispatching to its
    Diplomacy-specific prompt construction methods.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, base_prompts_dir: Optional[str] = None) -> None:
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
        if action_type == 'decide_diplomacy_orders':
            # Ensure all necessary keys are in context, or handle missing keys
            # Expected keys by build_order_prompt: country, goals, relationships, formatted_diary, context_text, tools_available
            return self.build_order_prompt(
                country=context.get("country"),
                goals=context.get("goals", []),
                relationships=context.get("relationships", {}),
                formatted_diary=context.get("formatted_diary", ""),
                context_text=context.get("context_text", ""),
                tools_available=context.get("tools_available", False)
            )
        elif action_type == 'generate_diplomacy_messages':
            # Expected keys: country, active_powers, goals, relationships, formatted_diary, context_text, tools_available
            return self.build_negotiation_prompt(
                country=context.get("country"),
                active_powers=context.get("active_powers", []),
                goals=context.get("goals", []),
                relationships=context.get("relationships", {}),
                formatted_diary=context.get("formatted_diary", ""),
                context_text=context.get("context_text", ""),
                tools_available=context.get("tools_available", False)
            )
        elif action_type == 'generate_diplomacy_diary':
            # Expected keys: country, phase_name, power_units, power_centers, is_game_over, events, goals, relationships
            return self.build_diary_generation_prompt(
                country=context.get("country"),
                phase_name=context.get("phase_name", "Unknown Phase"),
                power_units=context.get("power_units", []),
                power_centers=context.get("power_centers", []),
                is_game_over=context.get("is_game_over", False),
                events=context.get("events", []),
                goals=context.get("goals", []),
                relationships=context.get("relationships", {})
            )
        elif action_type == 'analyze_diplomacy_goals':
            # Expected keys: country, phase_name, power_units, power_centers, all_power_centers, is_game_over, current_goals, relationships
            return self.build_goal_analysis_prompt(
                country=context.get("country"),
                phase_name=context.get("phase_name", "Unknown Phase"),
                power_units=context.get("power_units", []),
                power_centers=context.get("power_centers", []),
                all_power_centers=context.get("all_power_centers", {}),
                is_game_over=context.get("is_game_over", False),
                current_goals=context.get("current_goals", []),
                relationships=context.get("relationships", {})
            )
        else:
            logger.warning(f"Unknown action_type '{action_type}' for DiplomacyPromptStrategy. Falling back to generic system prompt or error.")
            # Fallback or error, or try to use a generic prompt if BasePromptStrategy has one
            # For now, let's indicate an issue.
            # return super().build_prompt(action_type, context) # If BasePromptStrategy had a default
            raise ValueError(f"Unsupported action_type for DiplomacyPromptStrategy: {action_type}")
        elif action_type == 'decide_bloc_orders': # For BlocLLMAgent
            # This action_type implies the context contains a pre-rendered prompt
            if "prompt_content" not in context:
                logger.error("Context must contain 'prompt_content' for 'decide_bloc_orders'")
                raise ValueError("Context must contain 'prompt_content' for 'decide_bloc_orders'")
            # The system prompt for bloc agent might be different, handled by BlocLLMAgent itself
            # or passed in context if generic_agent needs to set it.
            # For now, assume prompt_content is the full user prompt.
            return context["prompt_content"]
        else:
            logger.warning(f"Unknown action_type '{action_type}' for DiplomacyPromptStrategy. Falling back to generic system prompt or error.")
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
        goals_str = (
            "\n".join(f"- {goal}" for goal in goals)
            if goals
            else "No specific goals set."
        )
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
        goals_str = (
            "\n".join(f"- {goal}" for goal in goals)
            if goals
            else "No specific goals set."
        )
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
        goals_str = (
            "\n".join(f"- {goal}" for goal in goals)
            if goals
            else "No specific goals set."
        )
        relationships_str = (
            "\n".join(f"- {power}: {status}" for power, status in relationships.items())
            if relationships
            else "No specific relationship data."
        )

        events_str = (
            "\n".join(str(event) for event in events)
            if events
            else "No significant events."
        )

        game_status = (
            "The game is now over." if is_game_over else "The game is ongoing."
        )

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
            "\n".join(
                f"- {power}: {count} centers"
                for power, count in all_power_centers.items()
            )
            if all_power_centers
            else "Supply center data unavailable."
        )

        game_status = (
            "The game is now over." if is_game_over else "The game is ongoing."
        )

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
    # Example for BasePromptStrategy (though it's abstract)
    base_config = {"system_prompt_filename": "custom_system_prompt.txt"}
    # base_strategy = BasePromptStrategy(config=base_config) # Won't work directly due to NotImplementedError
    # print(f"Base strategy system prompt: {base_strategy.system_prompt_template}")
    # try:
    #     base_strategy.build_prompt("some_action", {})
    # except NotImplementedError as e:
    #     print(f"Caught expected error for BasePromptStrategy: {e}")


    # Example for DiplomacyPromptStrategy
    diplomacy_strategy = DiplomacyPromptStrategy()

    order_prompt = diplomacy_strategy.build_order_prompt(
        country="FRANCE",
        goals=["Capture Munich", "Secure Belgium"],
        relationships={"GERMANY": "Enemy", "ENGLAND": "Friendly"},
        formatted_diary="[Spring 1901] Moved to Burgundy. Germany seems aggressive.",
        context_text="Current Phase: Fall 1901 Movement. Germany has units in Ruhr and Munich. England has fleets in North Sea.",
        tools_available=True,
    )
    print("\n--- DIPLOMACY ORDER PROMPT ---")
    print(order_prompt)

    negotiation_prompt = diplomacy_strategy.build_negotiation_prompt(
        country="ITALY",
        active_powers=["FRANCE", "GERMANY", "AUSTRIA", "TURKEY", "RUSSIA", "ENGLAND"],
        goals=["Form a defensive alliance against Austria", "Gain control of Tunis"],
        relationships={"AUSTRIA": "Enemy", "FRANCE": "Neutral", "TURKEY": "Friendly"},
        formatted_diary="[Spring 1901] Austria moved to Tyrolia, seems hostile.",
        context_text="Messages from Spring 1901: France proposed a DMZ in Piedmont. Austria has not responded to requests.",
        tools_available=False,
    )
    print("\n--- DIPLOMACY NEGOTIATION PROMPT ---")
    print(negotiation_prompt)
```
