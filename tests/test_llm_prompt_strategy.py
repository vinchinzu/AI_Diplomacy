import unittest
from ai_diplomacy.agents.llm_prompt_strategy import LLMPromptStrategy

class TestLLMPromptStrategy(unittest.TestCase):

    def setUp(self):
        self.strategy = LLMPromptStrategy()
        self.country = "FRANCE"
        self.goals = ["Expand East", "Secure borders"]
        self.relationships = {"ENGLAND": "Ally", "GERMANY": "Enemy", "ITALY": "Neutral"}
        self.formatted_diary = "[Spring1901] Made a deal with England.\n[Autumn1901] Germany attacked Belgium."
        self.context_text = "Strategic overview: Germany is aggressive."
        self.active_powers = ["ENGLAND", "GERMANY", "ITALY", "RUSSIA", "AUSTRIA", "TURKEY"]
        self.phase_name = "Autumn1901 Movement"
        self.power_units = ["A PAR", "F BRE", "A MAR"]
        self.power_centers = ["PARIS", "BREST", "MARSEILLES"]
        self.is_game_over = False
        self.events = [{"type": "attack", "attacker": "GERMANY", "target": "BELGIUM", "success": True}]
        self.all_power_centers = {"FRANCE": 3, "GERMANY": 4, "ENGLAND": 3, "ITALY": 3, "AUSTRIA": 3, "RUSSIA": 3, "TURKEY": 2}
        
        self.tool_instruction_snippet = "If you need to access external information"
        self.order_json_instruction = '"orders": ['
        self.message_json_instruction = '"messages": ['
        self.message_recipient_instruction = '"recipient": "COUNTRY_NAME"'
        self.message_content_instruction = '"content": "Your message text here..."'
        self.message_type_instruction = '"message_type": "PROPOSAL"'
        self.diary_json_instruction = '"diary_entry":'
        self.goal_json_instruction_updated = '"updated_goals":'
        self.goal_json_instruction_reasoning = '"reasoning":'

    def test_build_order_prompt_with_tools(self):
        prompt = self.strategy.build_order_prompt(
            country=self.country,
            goals=self.goals,
            relationships=self.relationships,
            formatted_diary=self.formatted_diary,
            context_text=self.context_text,
            tools_available=True,
        )
        self.assertIn(f"You are an AI agent playing as {self.country}", prompt)
        for goal in self.goals:
            self.assertIn(goal, prompt)
        for power, status in self.relationships.items():
            self.assertIn(f"- {power}: {status}", prompt)
        self.assertIn(self.formatted_diary, prompt)
        self.assertIn(self.context_text, prompt)
        self.assertIn(self.tool_instruction_snippet, prompt)
        self.assertIn(self.order_json_instruction, prompt)
        self.assertIn("Your Goals:", prompt)
        self.assertIn("Your Relationships with other powers:", prompt)
        self.assertIn("Recent Diary Entries:", prompt)
        self.assertIn("Game Context and Relevant Information:", prompt)


    def test_build_order_prompt_without_tools(self):
        prompt = self.strategy.build_order_prompt(
            country=self.country,
            goals=self.goals,
            relationships=self.relationships,
            formatted_diary=self.formatted_diary,
            context_text=self.context_text,
            tools_available=False,
        )
        self.assertIn(f"You are an AI agent playing as {self.country}", prompt)
        self.assertNotIn(self.tool_instruction_snippet, prompt)
        self.assertIn(self.order_json_instruction, prompt)

    def test_build_negotiation_prompt_with_tools(self):
        prompt = self.strategy.build_negotiation_prompt(
            country=self.country,
            active_powers=self.active_powers,
            goals=self.goals,
            relationships=self.relationships,
            formatted_diary=self.formatted_diary,
            context_text=self.context_text,
            tools_available=True,
        )
        self.assertIn(f"You are an AI agent playing as {self.country}", prompt)
        self.assertIn(", ".join(self.active_powers), prompt)
        for goal in self.goals:
            self.assertIn(goal, prompt)
        for power, status in self.relationships.items():
            self.assertIn(f"- {power}: {status}", prompt)
        self.assertIn(self.formatted_diary, prompt)
        self.assertIn(self.context_text, prompt)
        self.assertIn(self.tool_instruction_snippet, prompt)
        self.assertIn(self.message_json_instruction, prompt)
        self.assertIn(self.message_recipient_instruction, prompt)
        self.assertIn(self.message_content_instruction, prompt)
        self.assertIn(self.message_type_instruction, prompt)
        self.assertIn("The other active powers in the game are:", prompt)

    def test_build_negotiation_prompt_without_tools(self):
        prompt = self.strategy.build_negotiation_prompt(
            country=self.country,
            active_powers=self.active_powers,
            goals=self.goals,
            relationships=self.relationships,
            formatted_diary=self.formatted_diary,
            context_text=self.context_text,
            tools_available=False,
        )
        self.assertIn(f"You are an AI agent playing as {self.country}", prompt)
        self.assertNotIn(self.tool_instruction_snippet, prompt)
        self.assertIn(self.message_json_instruction, prompt)

    def test_build_diary_generation_prompt(self):
        prompt = self.strategy.build_diary_generation_prompt(
            country=self.country,
            phase_name=self.phase_name,
            power_units=self.power_units,
            power_centers=self.power_centers,
            is_game_over=self.is_game_over,
            events=self.events,
            goals=self.goals,
            relationships=self.relationships,
        )
        self.assertIn(f"You are an AI agent playing as {self.country}", prompt)
        self.assertIn(f"The phase '{self.phase_name}' has just concluded.", prompt)
        self.assertIn(", ".join(self.power_units), prompt)
        self.assertIn(", ".join(self.power_centers), prompt)
        self.assertIn("The game is ongoing.", prompt) # from is_game_over = False
        for event_dict in self.events:
            self.assertIn(str(event_dict), prompt) # Check if event string is in prompt
        for goal in self.goals:
            self.assertIn(goal, prompt)
        for power, status in self.relationships.items():
            self.assertIn(f"- {power}: {status}", prompt)
        self.assertIn(self.diary_json_instruction, prompt)
        self.assertIn("Reflect on what happened in this phase.", prompt)
        self.assertIn("Your situation:", prompt)
        self.assertIn("- Your Units:", prompt)
        self.assertIn("- Your Supply Centers:", prompt)
        self.assertIn("- Your Current Goals:", prompt)
        self.assertIn("- Your Relationships:", prompt)
        self.assertIn(f"Events that occurred during the '{self.phase_name}' phase:", prompt)

    def test_build_diary_generation_prompt_game_over(self):
        prompt = self.strategy.build_diary_generation_prompt(
            country=self.country,
            phase_name="End Game",
            power_units=[],
            power_centers=[],
            is_game_over=True,
            events=[],
            goals=[],
            relationships={},
        )
        self.assertIn("The game is now over.", prompt)

    def test_build_goal_analysis_prompt(self):
        prompt = self.strategy.build_goal_analysis_prompt(
            country=self.country,
            phase_name=self.phase_name,
            power_units=self.power_units,
            power_centers=self.power_centers,
            all_power_centers=self.all_power_centers,
            is_game_over=self.is_game_over,
            current_goals=self.goals,
            relationships=self.relationships,
        )
        self.assertIn(f"You are an AI agent playing as {self.country}", prompt)
        self.assertIn(f"The phase '{self.phase_name}' has just concluded.", prompt)
        self.assertIn(", ".join(self.power_units), prompt)
        self.assertIn(f"({len(self.power_centers)}): {', '.join(self.power_centers)}", prompt)
        for power, count in self.all_power_centers.items():
            self.assertIn(f"- {power}: {count} centers", prompt)
        self.assertIn("The game is ongoing.", prompt)
        for goal in self.goals: # Current goals
            self.assertIn(goal, prompt)
        for power, status in self.relationships.items():
            self.assertIn(f"- {power}: {status}", prompt)
        self.assertIn(self.goal_json_instruction_updated, prompt)
        self.assertIn(self.goal_json_instruction_reasoning, prompt)
        self.assertIn("Analyze your current situation", prompt)
        self.assertIn("Suggest a new list of strategic goals", prompt)
        self.assertIn("Your Current Situation:", prompt)
        self.assertIn("Overall Game State:", prompt)
        self.assertIn("- Supply Center Counts for all Powers:", prompt)


    def test_build_goal_analysis_prompt_game_over(self):
        prompt = self.strategy.build_goal_analysis_prompt(
            country=self.country,
            phase_name="Post Game Analysis",
            power_units=[],
            power_centers=[],
            all_power_centers=self.all_power_centers,
            is_game_over=True,
            current_goals=[],
            relationships={},
        )
        self.assertIn("The game is now over.", prompt)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False) 