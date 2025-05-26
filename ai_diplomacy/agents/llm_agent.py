"""
LLM-based agent implementation.
Extracts all LLM-specific logic from the original DiplomacyAgent while implementing the clean BaseAgent interface.
"""
import logging
from typing import List, Dict, Optional, Any

from .base import BaseAgent, Order, Message, PhaseState
from ..services.llm_coordinator import LLMCoordinator
from ..services.config import AgentConfig, resolve_context_provider
from ..services.context_provider import ContextProviderFactory, ContextData
from .. import llm_utils

logger = logging.getLogger(__name__)

# Constants moved from agent.py
ALL_POWERS = frozenset({"AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"})
ALLOWED_RELATIONSHIPS = ["Enemy", "Unfriendly", "Neutral", "Friendly", "Ally"]


class LLMAgent(BaseAgent):
    """
    LLM-based diplomacy agent that implements the BaseAgent interface.
    
    This agent uses Large Language Models to make decisions, maintain relationships,
    and generate diplomatic communications. It receives immutable PhaseState objects
    and returns orders/messages without direct game engine access.
    """
    
    def __init__(
        self, 
        agent_id: str, 
        country: str,
        config: AgentConfig,
        game_id: str = "unknown_game",
        llm_coordinator: Optional[LLMCoordinator] = None,
        context_provider_factory: Optional[ContextProviderFactory] = None
    ):
        """
        Initialize the LLM agent.
        
        Args:
            agent_id: Unique identifier for this agent instance
            country: The country/power this agent represents
            config: Agent configuration containing model_id and other settings
            game_id: Game identifier for tracking
            llm_coordinator: LLM coordinator instance (will create if None)
            context_provider_factory: Context provider factory (will create if None)
        """
        super().__init__(agent_id, country)
        self.config = config
        self.power_name = country  # Added for direct access
        self.model_id = config.model_id  # Added for direct access
        self.game_id = game_id
        self.llm_coordinator = llm_coordinator or LLMCoordinator()
        
        # Context provider setup
        self.context_factory = context_provider_factory or ContextProviderFactory()
        self.resolved_context_provider_type = resolve_context_provider(config)
        self.context_provider = self.context_factory.get_provider(self.resolved_context_provider_type)
        
        # Update resolved type to reflect actual provider used (handles fallbacks)
        self.resolved_context_provider_type = self.context_provider.get_provider_type()
        
        # Agent state
        self.goals: List[str] = []
        self.relationships: Dict[str, str] = {p: "Neutral" for p in ALL_POWERS if p != self.country}
        self.private_journal: List[str] = []
        self.private_diary: List[str] = []
        
        # Load system prompt
        self.system_prompt = self._load_system_prompt()
        
        logger.info(f"Initialized LLMAgent for {self.country} with model {self.config.model_id}, context provider: {self.resolved_context_provider_type}")
        self.add_journal_entry(f"Agent initialized with model {self.config.model_id}, context provider: {self.resolved_context_provider_type}")
    
    def _load_system_prompt(self) -> Optional[str]:
        """Load power-specific or default system prompt."""
        power_prompt_filename = f"{self.country.lower()}_system_prompt.txt"
        default_prompt_filename = "system_prompt.txt"
        
        system_prompt = llm_utils.load_prompt_file(power_prompt_filename)
        if not system_prompt:
            logger.warning(f"Power-specific prompt '{power_prompt_filename}' not found. Loading default.")
            system_prompt = llm_utils.load_prompt_file(default_prompt_filename)
        else:
            logger.info(f"Loaded power-specific system prompt for {self.country}.")
        
        if not system_prompt:
            logger.error(f"Could not load system prompt for {self.country}!")
        
        return system_prompt
    
    def add_journal_entry(self, entry: str):
        """Add an entry to the agent's private journal."""
        if not isinstance(entry, str):
            entry = str(entry)
        self.private_journal.append(entry)
        logger.debug(f"[{self.country} Journal]: {entry}")
    
    def add_diary_entry(self, entry: str, phase: str):
        """Add an entry to the agent's private diary."""
        if not isinstance(entry, str):
            entry = str(entry)
        formatted_entry = f"[{phase}] {entry}"
        self.private_diary.append(formatted_entry)
        logger.info(f"[{self.country}] DIARY ENTRY ADDED for {phase}: {entry[:100]}...")
    
    def format_private_diary_for_prompt(self, max_entries: int = 40) -> str:
        """Format diary entries for inclusion in prompts."""
        if not self.private_diary:
            return "(No diary entries yet)"
        
        # Take the most recent entries
        recent_entries = self.private_diary[-max_entries:] if len(self.private_diary) > max_entries else self.private_diary
        return "\n".join(recent_entries)
    
    async def decide_orders(self, phase: PhaseState) -> List[Order]:
        """
        Decide what orders to submit for the current phase.
        
        Args:
            phase: Immutable snapshot of current game state
            
        Returns:
            List of orders to submit
        """
        logger.info(f"[{self.country}] Deciding orders for phase {phase.phase_name}")
        
        # Check if we have units to command
        my_units = phase.get_power_units(self.country)
        if not my_units:
            logger.info(f"[{self.country}] No units to command")
            return []
        
        # Build context using context provider
        try:
            # Prepare context data (simplified for now - in real implementation would include more details)
            context_data = ContextData(
                phase_state=phase,
                possible_orders={"MOCK": ["Hold"]},  # TODO: Get real possible orders
                game_history=None,
                recent_messages=None,
                strategic_analysis=None
            )
            
            # Get context from provider
            context_result = await self.context_provider.provide_context(
                agent_id=self.agent_id,
                country=self.country,
                context_data=context_data,
                agent_config=self.config
            )
            
            # Build prompt using context
            prompt = self._build_order_prompt_with_context(phase, context_result)
            
            # Call LLM
            result = await self.llm_coordinator.call_json(
                prompt=prompt,
                model_id=self.config.model_id,
                agent_id=self.agent_id,
                game_id=self.game_id,
                phase=phase.phase_name,
                system_prompt=self.system_prompt,
                expected_fields=["orders"],
                tools=context_result.get("tools", []) if context_result.get("tools_available") else None
            )
            
            # Extract orders from response
            orders = self._extract_orders_from_response(result, my_units)
            
            logger.info(f"[{self.country}] Generated {len(orders)} orders using {context_result.get('provider_type', 'unknown')} context")
            return orders
            
        except Exception as e:
            logger.error(f"[{self.country}] Error deciding orders: {e}", exc_info=True)
            # Fallback: hold all units
            return [Order(f"{unit} H") for unit in my_units]
    
    def _build_order_prompt(self, phase: PhaseState) -> str:
        """Build prompt for order generation (legacy method)."""
        # This is a simplified version - in real implementation this would be more sophisticated
        prompt = f"""
        You are playing as {self.country} in Diplomacy.
        
        Current Phase: {phase.phase_name}
        Your Units: {phase.get_power_units(self.country)}
        Your Centers: {phase.get_power_centers(self.country)}
        
        Your Goals: {self.goals}
        Your Relationships: {self.relationships}
        
        Recent Diary: {self.format_private_diary_for_prompt()}
        
        Decide your orders for this phase. Return JSON with "orders" field containing a list of order strings.
        """
        return prompt
    
    def _build_order_prompt_with_context(self, phase: PhaseState, context_result: Dict[str, Any]) -> str:
        """Build prompt for order generation using context provider."""
        base_instructions = f"""
You are playing as {self.country} in Diplomacy.

Your Goals: {self.goals}
Your Relationships: {self.relationships}

Recent Diary: {self.format_private_diary_for_prompt()}

{context_result.get('context_text', '')}

Decide your orders for this phase. Return JSON with "orders" field containing a list of order strings.
        """.strip()
        
        # If using MCP tools, add tool usage instructions
        if context_result.get("tools_available"):
            base_instructions += """

IMPORTANT: You have access to tools to get detailed game information. Use them to gather the information you need before deciding on orders.
            """
        
        return base_instructions
    
    def _extract_orders_from_response(self, response: Dict[str, Any], my_units: List[str]) -> List[Order]:
        """Extract and validate orders from LLM response."""
        orders = []
        
        if "orders" not in response:
            logger.warning(f"[{self.country}] No 'orders' field in LLM response")
            return [Order(f"{unit} H") for unit in my_units]  # Default to hold
        
        order_strings = response["orders"]
        if not isinstance(order_strings, list):
            logger.warning(f"[{self.country}] Orders field is not a list")
            return [Order(f"{unit} H") for unit in my_units]
        
        for order_str in order_strings:
            if isinstance(order_str, str) and order_str.strip():
                orders.append(Order(order_str.strip()))
        
        # If no valid orders, default to holding
        if not orders:
            orders = [Order(f"{unit} H") for unit in my_units]
        
        return orders
    
    async def negotiate(self, phase: PhaseState) -> List[Message]:
        """
        Generate diplomatic messages to send to other powers.
        
        Args:
            phase: Immutable snapshot of current game state
            
        Returns:
            List of messages to send
        """
        logger.info(f"[{self.country}] Generating messages for phase {phase.phase_name}")
        
        try:
            # Prepare context data for negotiations
            context_data = ContextData(
                phase_state=phase,
                possible_orders={"MOCK": ["Hold"]},  # TODO: Get real possible orders
                game_history=None,
                recent_messages=None,
                strategic_analysis=None
            )
            
            # Get context from provider
            context_result = await self.context_provider.provide_context(
                agent_id=self.agent_id,
                country=self.country,
                context_data=context_data,
                agent_config=self.config
            )
            
            # Build prompt using context
            prompt = self._build_negotiation_prompt_with_context(phase, context_result)
            
            # Call LLM
            result = await self.llm_coordinator.call_json(
                prompt=prompt,
                model_id=self.config.model_id,
                agent_id=self.agent_id,
                game_id=self.game_id,
                phase=phase.phase_name,
                system_prompt=self.system_prompt,
                expected_fields=["messages"],
                tools=context_result.get("tools", []) if context_result.get("tools_available") else None
            )
            
            # Extract messages from response
            messages = self._extract_messages_from_response(result, phase)
            
            logger.info(f"[{self.country}] Generated {len(messages)} messages using {context_result.get('provider_type', 'unknown')} context")
            return messages
            
        except Exception as e:
            logger.error(f"[{self.country}] Error generating messages: {e}", exc_info=True)
            return []
    
    def _build_negotiation_prompt(self, phase: PhaseState) -> str:
        """Build prompt for message generation (legacy method)."""
        active_powers = [p for p in phase.powers if not phase.is_power_eliminated(p) and p != self.country]
        
        prompt = f"""
        You are playing as {self.country} in Diplomacy.
        
        Current Phase: {phase.phase_name}
        Active Powers: {", ".join(active_powers)}
        
        Your Goals: {self.goals}
        Your Relationships: {self.relationships}
        
        Recent Diary: {self.format_private_diary_for_prompt()}
        
        Generate diplomatic messages to send to other powers. 
        Return JSON with "messages" field containing a list of message objects.
        Each message should have "recipient", "content", and "message_type" fields.
        """
        return prompt
    
    def _build_negotiation_prompt_with_context(self, phase: PhaseState, context_result: Dict[str, Any]) -> str:
        """Build prompt for message generation using context provider."""
        active_powers = [p for p in phase.powers if not phase.is_power_eliminated(p) and p != self.country]
        
        base_instructions = f"""
You are playing as {self.country} in Diplomacy.
Active Powers: {", ".join(active_powers)}

Your Goals: {self.goals}
Your Relationships: {self.relationships}

Recent Diary: {self.format_private_diary_for_prompt()}

{context_result.get('context_text', '')}

Generate diplomatic messages to send to other powers. 
Return JSON with "messages" field containing a list of message objects.
Each message should have "recipient", "content", and "message_type" fields.
        """.strip()
        
        # If using MCP tools, add tool usage instructions
        if context_result.get("tools_available"):
            base_instructions += """

IMPORTANT: You have access to tools to get detailed game information. Use them to understand the current situation before writing messages.
            """
        
        return base_instructions
    
    def _extract_messages_from_response(self, response: Dict[str, Any], phase: PhaseState) -> List[Message]:
        """Extract and validate messages from LLM response."""
        messages = []
        
        if "messages" not in response:
            return messages
        
        message_dicts = response["messages"]
        if not isinstance(message_dicts, list):
            return messages
        
        for msg_dict in message_dicts:
            if not isinstance(msg_dict, dict):
                continue
            
            recipient = msg_dict.get("recipient", "").upper()
            content = msg_dict.get("content", "")
            message_type = msg_dict.get("message_type", "private")
            
            if content and recipient:
                # Validate recipient
                if recipient in phase.powers or recipient == "GLOBAL":
                    messages.append(Message(recipient, content, message_type))
                else:
                    logger.warning(f"[{self.country}] Invalid recipient: {recipient}")
        
        return messages
    
    async def update_state(self, phase: PhaseState, events: List[Dict[str, Any]]) -> None:
        """
        Update internal agent state based on phase results and events.
        
        Args:
            phase: The phase that just completed
            events: List of events that occurred
        """
        logger.info(f"[{self.country}] Updating state after phase {phase.phase_name}")
        
        # Generate a diary entry about the phase results
        await self._generate_phase_diary_entry(phase, events)
        
        # Update relationships based on events
        self._update_relationships_from_events(events)
        
        # Optionally update goals based on game state analysis
        await self._analyze_and_update_goals(phase)
    
    async def _generate_phase_diary_entry(self, phase: PhaseState, events: List[Dict[str, Any]]):
        """Generate a diary entry reflecting on the phase results."""
        try:
            prompt = f"""
            You are {self.country}. The phase {phase.phase_name} just ended.
            
            Current situation:
            - Your units: {phase.get_power_units(self.country)}
            - Your centers: {phase.get_power_centers(self.country)}
            - Game over: {phase.is_game_over}
            
            Events that occurred: {events}
            
            Your current goals: {self.goals}
            Your relationships: {self.relationships}
            
            Write a brief diary entry reflecting on what happened this phase.
            Return JSON with "diary_entry" field.
            """
            
            result = await self.llm_coordinator.call_json(
                prompt=prompt,
                model_id=self.config.model_id,
                agent_id=self.agent_id,
                game_id=self.game_id,
                phase=phase.phase_name,
                system_prompt=self.system_prompt,
                expected_fields=["diary_entry"]
            )
            
            diary_text = result.get("diary_entry", f"Phase {phase.phase_name} completed.")
            self.add_diary_entry(diary_text, phase.phase_name)
            
        except Exception as e:
            logger.error(f"[{self.country}] Error generating diary entry: {e}", exc_info=True)
            self.add_diary_entry(f"Phase {phase.phase_name} completed (diary generation failed).", phase.phase_name)
    
    def _update_relationships_from_events(self, events: List[Dict[str, Any]]):
        """Update relationships based on game events."""
        for event in events:
            event_type = event.get("type")
            
            if event_type == "attack":
                attacker = event.get("attacker")
                target = event.get("target")
                
                if target == self.country and attacker in self.relationships:
                    # We were attacked - worsen relationship
                    current = self.relationships[attacker]
                    if current == "Ally":
                        self.relationships[attacker] = "Friendly"
                    elif current == "Friendly":
                        self.relationships[attacker] = "Neutral"
                    elif current == "Neutral":
                        self.relationships[attacker] = "Unfriendly"
                    elif current == "Unfriendly":
                        self.relationships[attacker] = "Enemy"
                    
                    logger.info(f"[{self.country}] {attacker} attacked us, relationship now: {self.relationships[attacker]}")
            
            elif event_type == "support":
                supporter = event.get("supporter")
                supported = event.get("supported")
                
                if supported == self.country and supporter in self.relationships:
                    # We were supported - improve relationship
                    current = self.relationships[supporter]
                    if current == "Enemy":
                        self.relationships[supporter] = "Unfriendly"
                    elif current == "Unfriendly":
                        self.relationships[supporter] = "Neutral"
                    elif current == "Neutral":
                        self.relationships[supporter] = "Friendly"
                    elif current == "Friendly":
                        self.relationships[supporter] = "Ally"
                    
                    logger.info(f"[{self.country}] {supporter} supported us, relationship now: {self.relationships[supporter]}")
    
    async def _analyze_and_update_goals(self, phase: PhaseState):
        """Analyze current situation and potentially update goals."""
        try:
            # Simple goal analysis - more sophisticated logic could be added
            my_center_count = phase.get_center_count(self.country)
            
            # Basic goal updates based on situation
            new_goals = []
            
            if my_center_count < 3:
                new_goals.append("Survive and avoid elimination")
            elif my_center_count < 8:
                new_goals.append("Expand territory and gain supply centers")
            else:
                new_goals.append("Consolidate position and prepare for victory")
            
            # Check if anyone is getting too strong
            max_centers = max(phase.get_center_count(p) for p in phase.powers if not phase.is_power_eliminated(p))
            if max_centers > 10 and phase.get_center_count(self.country) != max_centers:
                new_goals.append("Form coalition against the leader")
            
            # Update goals if they've changed significantly
            if new_goals != self.goals:
                old_goals = self.goals.copy()
                self.goals = new_goals
                self.add_journal_entry(f"Goals updated from {old_goals} to {new_goals}")
                
        except Exception as e:
            logger.error(f"[{self.country}] Error analyzing goals: {e}", exc_info=True)
    
    def get_agent_info(self) -> Dict[str, Any]:
        """Return information about this agent."""
        return {
            "agent_id": self.agent_id,
            "country": self.country,
            "type": "LLMAgent",
            "model_id": self.config.model_id,
            "goals": self.goals,
            "relationships": self.relationships,
            "diary_entries": len(self.private_diary),
            "journal_entries": len(self.private_journal)
        } 