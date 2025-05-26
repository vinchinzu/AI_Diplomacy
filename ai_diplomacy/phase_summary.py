import logging
from typing import Optional, Dict, List, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from diplomacy import Game
    from .game_history import GameHistory, Phase # Added Phase for type hint
    from .llm_interface import AgentLLMInterface
    from .game_config import GameConfig

logger = logging.getLogger(__name__)

class PhaseSummaryGenerator:
    """
    Generates and records a summary of a game phase for a specific power.
    This was previously handled by phase_summary_callback in lm_game.py.
    """

    def __init__(self, llm_interface: 'AgentLLMInterface', game_config: 'GameConfig'):
        """
        Initializes the PhaseSummaryGenerator.

        Args:
            llm_interface: The LLM interface for the agent of the power for which
                           the summary is being generated.
            game_config: The global game configuration object.
        """
        self.llm_interface = llm_interface
        self.game_config = game_config
        # The power_name is implicitly handled by the specific llm_interface instance passed.
        self.power_name = self.llm_interface.power_name


    def _get_all_orders_for_phase(self, game_history: 'GameHistory', phase_name: str) -> Dict[str, List[str]]:
        """
        Helper to retrieve all orders for a given phase from game history.
        """
        phase_data: Optional['Phase'] = game_history.get_phase_by_name(phase_name)
        if phase_data and phase_data.orders_by_power:
            return phase_data.orders_by_power
        
        # Fallback if not in history (e.g. very first phase, or if history population is delayed)
        # This part might need adjustment based on when orders are added to GameHistory
        # For now, assume GameHistory is up-to-date when this is called.
        logger.warning(f"[{self.power_name}] Orders for phase {phase_name} not found in game_history.orders_by_power. This might be normal for initial phases.")
        return {}


    async def generate_and_record_phase_summary(
        self,
        game: 'Game', # Current game state
        game_history: 'GameHistory', # History up to the phase *before* the one being summarized if current_short_phase is used
        phase_to_summarize_name: str, # e.g., "SPRING 1901M" (Movement phase that just ended)
        # Summary text of what happened in the phase (e.g. from game engine or observer)
        # This was 'phase_summary_text' in original lm_game.py, passed to phase_result_diary
        phase_events_summary_text: str, 
        all_orders_for_phase: Dict[str, List[str]] # Orders for the phase being summarized
    ) -> str:
        """
        Generates a phase result diary entry (which serves as a phase summary from the agent's perspective),
        records it in the game history, and returns the generated summary.

        Args:
            game: The current diplomacy.Game object.
            game_history: The GameHistory object.
            phase_to_summarize_name: The name of the phase that has just been completed and needs summarizing
                                     (e.g., the movement phase that just resolved).
            phase_events_summary_text: A textual summary of key events that occurred during this phase.
            all_orders_for_phase: A dictionary mapping power names to their orders for the phase being summarized.

        Returns:
            The generated summary string for the power, or an error message string.
        """
        logger.info(f"[{self.power_name}] Generating phase result diary (summary) for {phase_to_summarize_name}...")

        # Prepare variables for the prompt, similar to original phase_summary_callback
        # The llm_interface for this power will use its own self.power_name, goals, relationships.
        
        # Format all orders for the prompt
        all_orders_formatted = ""
        for power, orders in all_orders_for_phase.items():
            orders_str = ", ".join(orders) if orders else "No orders"
            all_orders_formatted += f"{power}: {orders_str}\n"
        
        your_orders_str = ", ".join(all_orders_for_phase.get(self.power_name, [])) if all_orders_for_phase.get(self.power_name) else "No orders submitted by you"

        # Get negotiations relevant to this phase (from history)
        # GameHistory needs a method to get messages *for a specific phase* easily
        # Assuming get_messages_by_phase exists or can be added to GameHistory
        messages_this_phase = game_history.get_messages_by_phase(phase_to_summarize_name) # You'd need to implement/verify this
        
        your_negotiations_text = ""
        if messages_this_phase:
            for msg_obj in messages_this_phase: # Assuming msg_obj has sender, recipient, content
                if msg_obj.sender == self.power_name:
                    your_negotiations_text += f"To {msg_obj.recipient}: {msg_obj.content}\n"
                elif msg_obj.recipient == self.power_name:
                    your_negotiations_text += f"From {msg_obj.sender}: {msg_obj.content}\n"
        if not your_negotiations_text:
            your_negotiations_text = "No negotiations involving your power recorded for this phase."

        # Agent's state (goals, relationships) are accessed via self.llm_interface.power_name 
        # and then by getting the agent instance if needed, or they are passed directly.
        # For phase_result_diary, the prompt expects current goals and relationships.
        # This implies the agent's state is needed. The llm_interface has power_name,
        # but not direct access to agent's goals/relationships.
        # This suggests PhaseSummaryGenerator might need access to the agent instance or its state.
        # For now, let's assume these are passed or are part of game_config for the agent.
        # The original agent.generate_phase_result_diary_entry used self.relationships and self.goals.
        # This means the llm_interface's generate_phase_result_diary needs these.
        # Let's assume these are part of prompt_template_vars passed to the interface.

        # The current AgentLLMInterface.generate_phase_result_diary takes prompt_template_vars.
        # We need to construct these vars here.
        
        # This part requires access to the agent's current state (goals, relationships).
        # For now, placeholder. This needs to be resolved by how Agent state is accessed here.
        # Let's assume GameConfig holds a reference to the agent or relevant state.
        # This is a simplification; likely, the Agent instance itself calls this method,
        # or the orchestrator passes the agent's state.
        # Given the current AgentLLMInterface, it doesn't hold goals/relationships.
        # So, we construct them here.
        
        # This is a temporary workaround. Ideally, the agent's state (goals, relationships)
        # should be available more directly. The `self.llm_interface` is tied to an agent.
        # We need to fetch the agent from somewhere to get its goals/relationships.
        # This indicates a potential design dependency issue to be resolved in the Orchestrator/AgentManager.
        # For now, let's assume they are placeholders or fetched from a (yet to be defined) source.
        
        agent_goals_str = "Goals not available to PhaseSummaryGenerator directly."
        agent_relationships_str = "Relationships not available to PhaseSummaryGenerator directly."

        # If game_config.agents exists and contains the current agent:
        if self.game_config.agents and self.power_name in self.game_config.agents:
            current_agent = self.game_config.agents[self.power_name]
            agent_goals_str = "\n".join([f"- {g}" for g in current_agent.goals]) if current_agent.goals else "None"
            agent_relationships_str = "\n".join([f"{p}: {r}" for p, r in current_agent.relationships.items()])
        else:
            logger.warning(f"Agent {self.power_name} not found in game_config.agents. Using placeholder goals/relationships for summary generation.")


        prompt_template_vars: Dict[str, Any] = {
            "power_name": self.power_name,
            "current_phase": phase_to_summarize_name,
            "phase_summary": phase_events_summary_text, # This is the general summary of events
            "all_orders_formatted": all_orders_formatted,
            "your_negotiations": your_negotiations_text,
            "pre_phase_relationships": agent_relationships_str, # Agent's relationships before this phase's impact
            "agent_goals": agent_goals_str, # Agent's current goals
            "your_actual_orders": your_orders_str
        }
        
        generated_summary = await self.llm_interface.generate_phase_result_diary(
            prompt_template_vars=prompt_template_vars,
            log_file_path=self.game_config.llm_log_path, # Assuming game_config has this
            game_phase=phase_to_summarize_name # The phase being summarized
        )

        if generated_summary and not generated_summary.startswith("(Error:"):
            # Record this generated summary (which is a diary entry reflecting on results)
            # The original lm_game added this as a diary entry to the agent.
            # Here, we might add it to game_history for the *power* associated with this llm_interface
            # The method in GameHistory is `add_phase_summary(phase_name, power_name, summary)`
            # However, the prompt is "phase_result_diary_prompt.txt", so it's an agent's reflection.
            # This should be added to the agent's diary.
            # The PhaseSummaryGenerator itself doesn't have the agent instance's add_diary_entry.
            # This implies the summary should be returned and the caller (agent or orchestrator) adds it.
            
            # For now, let's assume it's recorded in game_history as a power-specific summary/reflection.
            game_history.add_phase_summary(phase_to_summarize_name, self.power_name, generated_summary)
            logger.info(f"[{self.power_name}] Generated and recorded phase summary/diary for {phase_to_summarize_name}.")
            return generated_summary
        else:
            logger.error(f"[{self.power_name}] Failed to generate phase summary/diary for {phase_to_summarize_name}. LLM response: {generated_summary}")
            error_message = f"(Error: Failed to generate phase summary for {self.power_name} for {phase_to_summarize_name})"
            game_history.add_phase_summary(phase_to_summarize_name, self.power_name, error_message)
            return error_message

if __name__ == '__main__':
    # This is for example usage/testing of PhaseSummaryGenerator
    # It requires mocked or dummy versions of Game, GameHistory, AgentLLMInterface, GameConfig
    
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # --- Mocking dependencies ---
    class MockLLMInterface:
        def __init__(self, power_name="FRANCE"):
            self.power_name = power_name
            self.logger = logging.getLogger(f"MockLLMInterface.{power_name}")

        async def generate_phase_result_diary(self, prompt_template_vars, log_file_path, game_phase):
            self.logger.info(f"generate_phase_result_diary called for {game_phase} with vars: {list(prompt_template_vars.keys())}")
            # Simulate a successful response
            return f"This is a generated summary for {prompt_template_vars.get('power_name')} for phase {game_phase}. Events: {prompt_template_vars.get('phase_summary')[:30]}..."

    class MockGame:
        def __init__(self, current_phase_name="SPRING 1901M"):
            self.current_short_phase = current_phase_name
            # Add other attributes if needed by the class, e.g., get_state()
            self.powers = {"FRANCE": None, "GERMANY": None} # Dummy powers

        def get_current_phase(self): # Ensure this method exists
            return self.current_short_phase


    class MockPhase:
        def __init__(self, name):
            self.name = name
            self.orders_by_power = {}
            self.messages = []
            self.phase_summaries = {}
        
        def add_phase_summary(self, power_name, summary): # Corrected method name
            self.phase_summaries[power_name] = summary

    class MockGameHistory:
        def __init__(self):
            self.phases: List[MockPhase] = []
        
        def get_phase_by_name(self, name_to_find: str) -> Optional[MockPhase]:
            for p in self.phases:
                if p.name == name_to_find:
                    return p
            # Add the phase if not found, for testing simplicity of summary generation
            new_phase = MockPhase(name_to_find)
            self.phases.append(new_phase)
            logger.info(f"[MockGameHistory] Auto-added phase {name_to_find} for summary testing.")
            return new_phase

        def get_messages_by_phase(self, phase_name: str) -> List[Any]: # Return list of mock messages
            # Simplified: return empty list or some mock messages
            phase = self.get_phase_by_name(phase_name)
            return phase.messages if phase else []

        def add_phase_summary(self, phase_name: str, power_name: str, summary: str):
            phase = self.get_phase_by_name(phase_name) # Ensures phase exists
            if phase:
                phase.add_phase_summary(power_name, summary) # Corrected call
            else: # Should not happen with get_phase_by_name's auto-add for this test
                logger.error(f"[MockGameHistory] Phase {phase_name} not found to add summary for {power_name}")


    from .game_config import GameConfig
    
    class MockGameConfig(GameConfig):
        def __init__(self, power_name="FRANCE"):
            # Create minimal mock args for parent constructor
            class MockArgs:
                def __init__(self):
                    self.game_id = "test_phase_summary"
                    self.game_id_prefix = "test"
                    self.log_level = "INFO"
                    self.log_to_file = True
                    self.log_dir = None
                    self.power_name = power_name
                    self.model_id = None
                    self.num_players = 7
                    self.perform_planning_phase = False
                    self.num_negotiation_rounds = 1
                    self.negotiation_style = "simultaneous"
                    self.fixed_models = None
                    self.randomize_fixed_models = False
                    self.exclude_powers = None
                    self.max_years = None
                    self.dev_mode = False
                    self.verbose_llm_debug = False
                    self.max_diary_tokens = 6500
                    self.models_config_file = "models.toml"
            
            # Call parent constructor
            super().__init__(MockArgs())
            
            # Override for testing
            self.llm_log_path = "dummy_llm_log.csv"
            self.agents = {} # To store mock agents if needed for goal/relationship fetching

            # Mock an agent for testing goal/relationship fetching
            class MockAgent:
                def __init__(self, p_name):
                    self.power_name = p_name
                    self.goals = [f"Goal 1 for {p_name}", f"Goal 2 for {p_name}"]
                    self.relationships = {"GERMANY": "Neutral", "ENGLAND": "Friendly"} if p_name == "FRANCE" else {}
            if power_name:
                 self.agents[power_name] = MockAgent(power_name)


    async def run_summary_generator_test():
        logger.info("--- Testing PhaseSummaryGenerator ---")
        
        # Setup
        power_name_test = "FRANCE"
        mock_llm_interface = MockLLMInterface(power_name=power_name_test)
        mock_game_config = MockGameConfig(power_name=power_name_test)
        
        summary_generator = PhaseSummaryGenerator(mock_llm_interface, mock_game_config)
        
        mock_game = MockGame(current_phase_name="AUTUMN 1901M") # Phase after the one being summarized
        mock_history = MockGameHistory()
        
        phase_to_summarize = "SPRING 1901M"
        # Add some history for the phase being summarized
        spring_1901_phase = mock_history.get_phase_by_name(phase_to_summarize) # Creates if not exists
        if spring_1901_phase:
             spring_1901_phase.orders_by_power = {
                "FRANCE": ["A PAR H", "F MAR H"],
                "GERMANY": ["A BER H", "A MUN - RUH"]
            }
             spring_1901_phase.messages = [
                type('MockMessage', (), {'sender': 'GERMANY', 'recipient': 'FRANCE', 'content': 'Hello France!'})()
            ]


        phase_events_text = "France took Paris. Germany moved to Ruhr."
        all_orders_for_spring_1901 = spring_1901_phase.orders_by_power if spring_1901_phase else {}
        
        # Generate summary
        generated_text = await summary_generator.generate_and_record_phase_summary(
            game=mock_game,
            game_history=mock_history,
            phase_to_summarize_name=phase_to_summarize,
            phase_events_summary_text=phase_events_text,
            all_orders_for_phase=all_orders_for_spring_1901
        )
        
        logger.info(f"Generated Summary Text for {power_name_test}: {generated_text}")
        
        # Check if summary was recorded in history (basic check)
        recorded_phase = mock_history.get_phase_by_name(phase_to_summarize)
        if recorded_phase and recorded_phase.phase_summaries.get(power_name_test):
            logger.info(f"Summary for {power_name_test} correctly recorded in history for {phase_to_summarize}: {recorded_phase.phase_summaries[power_name_test][:50]}...")
        else:
            logger.error(f"Summary for {power_name_test} NOT recorded in history for {phase_to_summarize}.")

    import asyncio
    asyncio.run(run_summary_generator_test())
    logger.info("--- PhaseSummaryGenerator test complete ---")
