import os
import json
from json import JSONDecodeError
import re
import logging
import ast
import asyncio  # Added for async operations

from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

# Use Async versions of clients
from openai import AsyncOpenAI
from openai import AsyncOpenAI as AsyncDeepSeekOpenAI # Alias for clarity
from anthropic import AsyncAnthropic

os.environ["GRPC_PYTHON_LOG_LEVEL"] = "10"
import google.generativeai as genai

from diplomacy.engine.message import GLOBAL
from .game_history import GameHistory
from .utils import load_prompt, run_llm_and_log

# set logger back to just info
logger = logging.getLogger("client")
logger.setLevel(logging.DEBUG) # Keep debug for now during async changes
# Note: BasicConfig might conflict if already configured in lm_game. Keep client-specific for now.
# logging.basicConfig(level=logging.DEBUG) # Might be redundant if lm_game configures root

load_dotenv()

##############################################################################
# 1) Base Interface
##############################################################################
class BaseModelClient:
    """
    Base interface for any LLM client we want to plug in.
    Each must provide:
      - generate_response(prompt: str) -> str
      - get_orders(board_state, power_name, possible_orders) -> List[str]
      - get_conversation_reply(power_name, conversation_so_far, game_phase) -> str
    """

    def __init__(self, model_name: str):
        self.model_name = model_name
        # Load a default initially, can be overwritten by set_system_prompt
        self.system_prompt = load_prompt("system_prompt.txt") 

    def set_system_prompt(self, content: str):
        """Allows updating the system prompt after initialization."""
        self.system_prompt = content
        logger.info(f"[{self.model_name}] System prompt updated.")

    async def generate_response(self, prompt: str) -> str:
        """
        Returns a raw string from the LLM.
        Subclasses override this.
        """
        raise NotImplementedError("Subclasses must implement generate_response().")

    def build_context_prompt(
        self,
        game,
        board_state,
        power_name: str,
        possible_orders: Dict[str, List[str]],
        game_history: GameHistory,
        agent_goals: Optional[List[str]] = None,
        agent_relationships: Optional[Dict[str, str]] = None,
    ) -> str:
        context = load_prompt("context_prompt.txt")

        # === Agent State Debug Logging ===
        if agent_goals:
            logger.debug(f"[{self.model_name}] Using goals for {power_name}: {agent_goals}")
        if agent_relationships:
            logger.debug(f"[{self.model_name}] Using relationships for {power_name}: {agent_relationships}")
        # ================================

        # Get our units and centers
        units_info = board_state["units"].get(power_name, [])
        units_info_set = set(units_info)
        centers_info = board_state["centers"].get(power_name, [])

        # Get the current phase
        year_phase = board_state["phase"]  # e.g. 'S1901M'

        # Get enemy units and centers and label them for each power
        enemy_units = {}
        enemy_centers = {}
        for power, info in board_state["units"].items():
            if power != power_name:
                enemy_units[power] = info
                enemy_centers[power] = board_state["centers"].get(power, [])

        # Get possible orders
        possible_orders_str = ""
        for loc, orders in possible_orders.items():
            possible_orders_str += f"  {loc}: {orders}\n"


        # Get messages for the current round
        messages_this_round_text = game_history.get_messages_this_round(
            power_name=power_name,
            current_phase_name=year_phase
        )
        if not messages_this_round_text.strip():
            messages_this_round_text = "\n(No messages this round)\n"

        # Get history from previous phases
        previous_history_text = game_history.get_previous_phases_history(
            power_name=power_name,
            current_phase_name=year_phase
            # include_plans and num_prev_phases will use defaults
        )
        if not previous_history_text.strip():
            previous_history_text = "\n(No previous game history)\n"

        # Load in current context values
        # Simplified map representation based on DiploBench approach
        units_repr = "\n".join([f"  {p}: {u}" for p, u in board_state["units"].items()])
        centers_repr = "\n".join([f"  {p}: {c}" for p, c in board_state["centers"].items()])

        context = context.format(
            power_name=power_name,
            current_phase=year_phase,
            all_unit_locations=units_repr, 
            all_supply_centers=centers_repr, 
            messages_this_round=messages_this_round_text,
            previous_game_history=previous_history_text,
            possible_orders=possible_orders_str,
            agent_goals="\n".join(f"- {g}" for g in agent_goals) if agent_goals else "None specified",
            agent_relationships="\n".join(f"- {p}: {s}" for p, s in agent_relationships.items()) if agent_relationships else "None specified",
        )

        return context

    def build_prompt(
        self,
        game,
        board_state,
        power_name: str,
        possible_orders: Dict[str, List[str]],
        game_history: GameHistory,
        agent_goals: Optional[List[str]] = None,
        agent_relationships: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Unified prompt approach: incorporate conversation and 'PARSABLE OUTPUT' requirements.
        """
        # Load prompts
        few_shot_example = load_prompt("few_shot_example.txt")
        instructions = load_prompt("order_instructions.txt")

        # Build the context prompt
        context = self.build_context_prompt(
            game,
            board_state,
            power_name,
            possible_orders,
            game_history,
            agent_goals=agent_goals,
            agent_relationships=agent_relationships,
        )

        # Prepend the system prompt!
        return self.system_prompt + "\n\n" + context + "\n\n" + instructions

    async def get_orders(
        self,
        game,
        board_state,
        power_name: str,
        possible_orders: Dict[str, List[str]],
        conversation_text: str,
        model_error_stats: dict,
        log_file_path: str,
        phase: str,
        agent_goals: Optional[List[str]] = None,
        agent_relationships: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        """
        1) Builds the prompt with conversation context if available
        2) Calls LLM
        3) Parses JSON block
        """
        prompt = self.build_prompt(
            game,
            board_state,
            power_name,
            possible_orders,
            conversation_text,
            agent_goals=agent_goals,
            agent_relationships=agent_relationships,
        )

        raw_response = ""

        try:
            # Call LLM using the logging wrapper
            raw_response = await run_llm_and_log(
                client=self,
                prompt=prompt,
                log_file_path=log_file_path,
                power_name=power_name,
                phase=phase,
                response_type='order',
            )
            logger.debug(
                f"[{self.model_name}] Raw LLM response for {power_name}:\n{raw_response}"
            )

            # Attempt to parse the final "orders" from the LLM
            move_list = self._extract_moves(raw_response, power_name)

            if not move_list:
                logger.warning(
                    f"[{self.model_name}] Could not extract moves for {power_name}. Using fallback."
                )
                if model_error_stats is not None:
                    model_error_stats[self.model_name]["order_decoding_errors"] += 1
                return self.fallback_orders(possible_orders)
            # Validate or fallback
            validated_moves = self._validate_orders(move_list, possible_orders)
            logger.debug(f"[{self.model_name}] Validated moves for {power_name}: {validated_moves}")
            return validated_moves

        except Exception as e:
            logger.error(f"[{self.model_name}] LLM error for {power_name}: {e}")
            return self.fallback_orders(possible_orders)

    def _extract_moves(self, raw_response: str, power_name: str) -> Optional[List[str]]:
        """
        Attempt multiple parse strategies to find JSON array of moves.

        1. Regex for PARSABLE OUTPUT lines.
        2. If that fails, also look for fenced code blocks with { ... }.
        3. Attempt bracket-based fallback if needed.

        Returns a list of move strings or None if everything fails.
        """
        # 1) Regex for "PARSABLE OUTPUT:{...}"
        pattern = r"PARSABLE OUTPUT:\s*(\{[\s\S]*\})"
        matches = re.search(pattern, raw_response, re.DOTALL)

        if not matches:
            # Some LLMs might not put the colon or might have triple backtick fences.
            logger.debug(
                f"[{self.model_name}] Regex parse #1 failed for {power_name}. Trying alternative patterns."
            )

            # 1b) Check for inline JSON after "PARSABLE OUTPUT"
            pattern_alt = r"PARSABLE OUTPUT\s*\{(.*?)\}\s*$"
            matches = re.search(pattern_alt, raw_response, re.DOTALL)

        if not matches:
            logger.debug(
                f"[{self.model_name}] Regex parse #2 failed for {power_name}. Trying triple-backtick code fences."
            )

        # 2) If still no match, check for triple-backtick code fences containing JSON
        if not matches:
            code_fence_pattern = r"```json\s*(\{.*?\})\s*```"
            matches = re.search(code_fence_pattern, raw_response, re.DOTALL)
            if matches:
                logger.debug(
                    f"[{self.model_name}] Found triple-backtick JSON block for {power_name}."
                )

        # 3) Attempt to parse JSON if we found anything
        json_text = None
        if matches:
            # Add braces back around the captured group
            if matches.group(1).strip().startswith(r"{{"):
                json_text = matches.group(1).strip()[1:-1]
            elif matches.group(1).strip().startswith(r"{"):
                json_text = matches.group(1).strip()
            else:
                json_text = "{%s}" % matches.group(1).strip

            json_text = json_text.strip()

        if not json_text:
            logger.debug(
                f"[{self.model_name}] No JSON text found in LLM response for {power_name}."
            )
            return None

        # 3a) Try JSON loading
        try:
            data = json.loads(json_text)
            return data.get("orders", None)
        except json.JSONDecodeError as e:
            logger.warning(
                f"[{self.model_name}] JSON decode failed for {power_name}: {e}. Trying bracket fallback."
            )

        # 3b) Attempt bracket fallback: we look for the substring after "orders"
        #     E.g. "orders: ['A BUD H']" and parse it. This is risky but can help with minor JSON format errors.
        #     We only do this if we see something like "orders": ...
        bracket_pattern = r'["\']orders["\']\s*:\s*\[([^\]]*)\]'
        bracket_match = re.search(bracket_pattern, json_text, re.DOTALL)
        if bracket_match:
            try:
                raw_list_str = "[" + bracket_match.group(1).strip() + "]"
                moves = ast.literal_eval(raw_list_str)
                if isinstance(moves, list):
                    return moves
            except Exception as e2:
                logger.warning(
                    f"[{self.model_name}] Bracket fallback parse also failed for {power_name}: {e2}"
                )

        # If all attempts failed
        return None

    def _validate_orders(
        self, moves: List[str], possible_orders: Dict[str, List[str]]
    ) -> List[str]:
        """
        Filter out invalid moves, fill missing with HOLD, else fallback.
        """
        logger.debug(f"[{self.model_name}] Proposed LLM moves: {moves}")
        validated = []
        used_locs = set()

        if not isinstance(moves, list):
            logger.debug(f"[{self.model_name}] Moves not a list, fallback.")
            return self.fallback_orders(possible_orders)

        for move in moves:
            move_str = move.strip()
            # Check if it's in possible orders
            if any(move_str in loc_orders for loc_orders in possible_orders.values()):
                validated.append(move_str)
                parts = move_str.split()
                if len(parts) >= 2:
                    used_locs.add(parts[1][:3])
            else:
                logger.debug(f"[{self.model_name}] Invalid move from LLM: {move_str}")

        # Fill missing with hold
        for loc, orders_list in possible_orders.items():
            if loc not in used_locs and orders_list:
                hold_candidates = [o for o in orders_list if o.endswith("H")]
                validated.append(
                    hold_candidates[0] if hold_candidates else orders_list[0]
                )

        if not validated:
            logger.warning(f"[{self.model_name}] All moves invalid, fallback.")
            return self.fallback_orders(possible_orders)

        return validated

    def fallback_orders(self, possible_orders: Dict[str, List[str]]) -> List[str]:
        """
        Just picks HOLD if possible, else first option.
        """
        fallback = []
        for loc, orders_list in possible_orders.items():
            if orders_list:
                holds = [o for o in orders_list if o.endswith("H")]
                fallback.append(holds[0] if holds else orders_list[0])
        return fallback

    def build_planning_prompt(
        self,
        game,
        board_state,
        power_name: str,
        possible_orders: Dict[str, List[str]],
        game_history: GameHistory,
        game_phase: str,
        log_file_path: str,
        agent_goals: Optional[List[str]] = None,
        agent_relationships: Optional[Dict[str, str]] = None,
    ) -> str:
        
        instructions = load_prompt("planning_instructions.txt")

        context = self.build_context_prompt(
            game,
            board_state,
            power_name,
            possible_orders,
            game_history,
            agent_goals=agent_goals,
            agent_relationships=agent_relationships,
        )

        return context + "\n\n" + instructions

    def build_conversation_prompt(
        self,
        game,
        board_state,
        power_name: str,
        possible_orders: Dict[str, List[str]],
        game_history: GameHistory,
        game_phase: str,
        log_file_path: str,
        agent_goals: Optional[List[str]] = None,
        agent_relationships: Optional[Dict[str, str]] = None,
    ) -> str:
        instructions = load_prompt("conversation_instructions.txt")

        context = self.build_context_prompt(
            game,
            board_state,
            power_name,
            possible_orders,
            game_history,
            agent_goals=agent_goals,
            agent_relationships=agent_relationships,
        )

        return context + "\n\n" + instructions

    async def get_planning_reply(
        self,
        game,
        board_state,
        power_name: str,
        possible_orders: Dict[str, List[str]],
        game_history: GameHistory,
        game_phase: str,
        log_file_path: str,
        agent_goals: Optional[List[str]] = None,
        agent_relationships: Optional[Dict[str, str]] = None,
    ) -> str:
        
        prompt = self.build_planning_prompt(
            game,
            board_state,
            power_name,
            possible_orders,
            game_history,
            game_phase,
            log_file_path,
            agent_goals=agent_goals,
            agent_relationships=agent_relationships,
        )

        raw_response = await self.generate_response(prompt)
        logger.debug(f"[{self.model_name}] Raw LLM response for {power_name}:\n{raw_response}")
        return raw_response
    
    async def get_conversation_reply(
        self,
        game,
        board_state,
        power_name: str,
        possible_orders: Dict[str, List[str]],
        game_history: GameHistory,
        game_phase: str,
        log_file_path: str,
        active_powers: Optional[List[str]] = None,
        agent_goals: Optional[List[str]] = None,
        agent_relationships: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, str]]:
        """
        Generates a negotiation message, considering agent state.

        Args:
            game: The Diplomacy game instance.
            board_state: Current state dictionary.
            power_name: The negotiating power.
            possible_orders: Dictionary of possible orders.
            game_history: The GameHistory object.
            game_phase: The current phase string.
            active_powers: List of powers still active.
            agent_goals: The agent's goals.
            agent_relationships: The agent's relationships.
            log_file_path: Path to the log file.

        Returns:
            List[Dict[str, str]]: Parsed JSON messages from the LLM response.
        """

        # Call build_conversation_prompt and pass agent state
        prompt = self.build_conversation_prompt(
            game,
            board_state,
            power_name,
            possible_orders,
            game_history,
            game_phase,
            log_file_path,
            agent_goals=agent_goals,
            agent_relationships=agent_relationships,
        )

        logger.debug(f"[{self.model_name}] Conversation prompt for {power_name}:\n{prompt}")

        try:
            # Call LLM using the logging wrapper
            response = await run_llm_and_log(
                client=self,
                prompt=prompt,
                log_file_path=log_file_path,
                power_name=power_name,
                phase=game_phase,
                response_type='negotiation',
            )
            logger.debug(f"[{self.model_name}] Raw LLM response for {power_name}:\n{response}")
            
            messages = []
            # Extract JSON blocks from the response
            json_blocks = []
            
            # First try to find {{ ... }} blocks (common in Claude responses)
            double_brace_blocks = re.findall(r'\{\{(.*?)\}\}', response, re.DOTALL)
            if double_brace_blocks:
                json_blocks.extend(['{' + block.strip() + '}' for block in double_brace_blocks])
            else:
                 # Fallback: try finding JSON within ```json ... ``` blocks, like in get_orders
                 code_block_match = re.search(r"```json\n(.*?)\n```", response, re.DOTALL)
                 if code_block_match:
                     potential_json = code_block_match.group(1).strip()
                     # Sometimes the LLM might put multiple JSONs in one block
                     json_blocks = re.findall(r'\{.*?\}', potential_json, re.DOTALL)
                 else:
                     # Final fallback: try finding any {...} block
                     json_blocks = re.findall(r'\{.*?\}', response, re.DOTALL)

            if not json_blocks:
                logger.warning(f"[{self.model_name}] No JSON message blocks found in response for {power_name}. Raw response:\n{response}")
                return []

            for block in json_blocks:
                try:
                    # Clean the block and ensure it's valid JSON
                    cleaned_block = block.strip()
                    
                    # Attempt to parse the individual JSON block
                    parsed_message = json.loads(cleaned_block)
                    
                    # Basic validation (can be expanded)
                    if isinstance(parsed_message, dict) and "message_type" in parsed_message and "content" in parsed_message:
                         messages.append(parsed_message)
                    else:
                         logger.warning(f"[{self.model_name}] Invalid message structure in block for {power_name}: {cleaned_block}")
                         
                except json.JSONDecodeError:
                    logger.warning(f"[{self.model_name}] Failed to decode JSON block for {power_name}. Block content:\n{block}")
                    # Continue to next block if one fails

            if not messages:
                 logger.warning(f"[{self.model_name}] No valid messages extracted after parsing blocks for {power_name}. Raw response:\n{response}")

            logger.debug(f"[{self.model_name}] Validated conversation replies for {power_name}: {messages}")
            return messages
            
        except Exception as e:
            # Catch any other exceptions during generation or processing
            logger.error(f"[{self.model_name}] Error in get_conversation_reply for {power_name}: {e}")
            return []

    async def get_plan(
        self,
        game,
        board_state,
        power_name: str,
        possible_orders: Dict[str, List[str]],
        game_history: GameHistory,
        log_file_path: str,
        agent_goals: Optional[List[str]] = None,
        agent_relationships: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Generates a strategic plan for the given power based on the current state.

        Args:
            game: The current Diplomacy game object.
            board_state: The current board state dictionary.
            power_name: The name of the power for which to generate a plan.
            game_history: The history of the game.
            log_file_path: Path to the log file.
            agent_goals: The agent's goals.
            agent_relationships: The agent's relationships.

        Returns:
            A string containing the generated strategic plan.
        """
        logger.info(f"Generating strategic plan for {power_name}...")
        
        # 1. Load the specific planning instructions
        planning_instructions = load_prompt("planning_instructions.txt")
        if not planning_instructions:
            logger.error("Could not load planning_instructions.txt! Cannot generate plan.")
            return "Error: Planning instructions not found."

        # 2. Build the context prompt (reusing the existing method)
        # We don't need possible_orders for planning instructions, but build_context_prompt needs it.
        # Pass an empty dict or calculate it if context depends heavily on it.
        # For simplicity, let's assume context building doesn't strictly require possible_orders
        # or can handle it being empty/None for planning purposes.
        # If necessary, calculate possible_orders here: 
        # possible_orders = game.get_all_possible_orders()
        possible_orders = {} # Pass empty for planning context
        context_prompt = self.build_context_prompt(
            game,
            board_state,
            power_name,
            possible_orders,
            game_history,
            agent_goals=agent_goals,
            agent_relationships=agent_relationships,
        )

        # 3. Combine context and planning instructions into the final prompt
        # Ensure the system prompt is prepended if it exists
        full_prompt = f"{context_prompt}\n\n{planning_instructions}"
        if self.system_prompt:
            full_prompt = f"{self.system_prompt}\n\n{full_prompt}"

        # 4. Generate the response from the LLM
        try:
            raw_plan = await run_llm_and_log(
                client=self,
                prompt=full_prompt,
                log_file_path=log_file_path,
                power_name=power_name,
                phase=game.current_short_phase, # Get phase from game object
                response_type='plan',
            )
            logger.debug(f"[{self.model_name}] Raw LLM response for {power_name}:\n{raw_plan}")
            logger.info(f"[{self.model_name}] Validated plan for {power_name}: {raw_plan}")
            # No parsing needed for the plan, return the raw string
            return raw_plan.strip()
        except Exception as e:
            logger.error(f"Failed to generate plan for {power_name}: {e}")
            return f"Error: Failed to generate plan due to exception: {e}"


##############################################################################
# 2) Concrete Implementations
##############################################################################


class OpenAIClient(BaseModelClient):
    """
    For 'o3-mini', 'gpt-4o', or other OpenAI model calls.
    """

    def __init__(self, model_name: str):
        super().__init__(model_name)
        self.client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    async def generate_response(self, prompt: str) -> str:
        # Updated to new API format
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt},
                ],
            )
            if not response or not hasattr(response, "choices") or not response.choices:
                logger.warning(
                    f"[{self.model_name}] Empty or invalid result in generate_response. Returning empty."
                )
                return ""
            return response.choices[0].message.content.strip()
        except json.JSONDecodeError as json_err:
            logger.error(
                f"[{self.model_name}] JSON decoding failed in generate_response: {json_err}"
            )
            return ""
        except Exception as e:
            logger.error(
                f"[{self.model_name}] Unexpected error in generate_response: {e}"
            )
            return ""


class ClaudeClient(BaseModelClient):
    """
    For 'claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', etc.
    """

    def __init__(self, model_name: str):
        super().__init__(model_name)
        self.client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    async def generate_response(self, prompt: str) -> str:
        # Updated Claude messages format
        try:
            response = await self.client.messages.create(
                model=self.model_name,
                max_tokens=2000,
                system=self.system_prompt,  # system is now a top-level parameter
                messages=[{"role": "user", "content": prompt}],
            )
            if not response.content:
                logger.warning(
                    f"[{self.model_name}] Empty content in Claude generate_response. Returning empty."
                )
                return ""
            return response.content[0].text.strip() if response.content else ""
        except json.JSONDecodeError as json_err:
            logger.error(
                f"[{self.model_name}] JSON decoding failed in generate_response: {json_err}"
            )
            return ""
        except Exception as e:
            logger.error(
                f"[{self.model_name}] Unexpected error in generate_response: {e}"
            )
            return ""


class GeminiClient(BaseModelClient):
    """
    For 'gemini-1.5-flash' or other Google Generative AI models.
    """

    def __init__(self, model_name: str):
        super().__init__(model_name)
        # Configure and get the model (corrected initialization)
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model_name)
        logger.debug(f"[{self.model_name}] Initialized Gemini client (genai.GenerativeModel)")

    async def generate_response(self, prompt: str) -> str:
        full_prompt = self.system_prompt + prompt

        try:
            response = await self.client.generate_content_async(
                contents=full_prompt,
            )
            if not response or not response.text:
                logger.warning(
                    f"[{self.model_name}] Empty Gemini generate_response. Returning empty."
                )
                return ""
            return response.text.strip()
        except Exception as e:
            logger.error(f"[{self.model_name}] Error in Gemini generate_response: {e}")
            return ""


class DeepSeekClient(BaseModelClient):
    """
    For DeepSeek R1 'deepseek-reasoner'
    """

    def __init__(self, model_name: str):
        super().__init__(model_name)
        self.api_key = os.environ.get("DEEPSEEK_API_KEY")
        self.client = AsyncDeepSeekOpenAI(
            api_key=self.api_key, base_url="https://api.deepseek.com/"
        )

    async def generate_response(self, prompt: str) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt},
                ],
                stream=False,
            )
            logger.debug(f"[{self.model_name}] Raw DeepSeek response:\n{response}")

            if not response or not response.choices:
                logger.warning(
                    f"[{self.model_name}] No valid response in generate_response."
                )
                return ""

            content = response.choices[0].message.content.strip()
            if not content:
                logger.warning(f"[{self.model_name}] DeepSeek returned empty content.")
                return ""

            try:
                json_response = json.loads(content)
                required_fields = ["message_type", "content"]
                if json_response["message_type"] == "private":
                    required_fields.append("recipient")
                if not all(field in json_response for field in required_fields):
                    logger.error(
                        f"[{self.model_name}] Missing required fields in response: {content}"
                    )
                    return ""
                return content
            except JSONDecodeError:
                logger.error(
                    f"[{self.model_name}] Response is not valid JSON: {content}"
                )
                content = content.replace("'", '"')
                try:
                    json.loads(content)
                    return content
                except JSONDecodeError:
                    return ""

        except Exception as e:
            logger.error(
                f"[{self.model_name}] Unexpected error in generate_response: {e}"
            )
            return ""


class OpenRouterClient(BaseModelClient):
    """
    For OpenRouter models, with default being 'openrouter/quasar-alpha'
    """

    def __init__(self, model_name: str = "openrouter/quasar-alpha"):
        # Allow specifying just the model identifier or the full path
        if not model_name.startswith("openrouter/") and "/" not in model_name:
            model_name = f"openrouter/{model_name}"
        if model_name.startswith("openrouter-"):
            model_name = model_name.replace("openrouter-", "")
            
        super().__init__(model_name)
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required")
            
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key
        )
        
        logger.debug(f"[{self.model_name}] Initialized OpenRouter client")

    async def generate_response(self, prompt: str) -> str:
        """Generate a response using OpenRouter."""
        try:
            # Prepare standard OpenAI-compatible request
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for more deterministic responses
                max_tokens=2048,  # Reasonable default, adjust as needed
            )
            
            if not response.choices:
                logger.warning(f"[{self.model_name}] OpenRouter returned no choices")
                return ""
                
            content = response.choices[0].message.content.strip()
            if not content:
                logger.warning(f"[{self.model_name}] OpenRouter returned empty content")
                return ""
                
            # Parse or return the raw content
            return content
            
        except Exception as e:
            logger.error(f"[{self.model_name}] Error in OpenRouter generate_response: {e}")
            return ""


##############################################################################
# 3) Factory to Load Model Client
##############################################################################


def load_model_client(model_id: str) -> BaseModelClient:
    """
    Returns the appropriate LLM client for a given model_id string.
    Example usage:
       client = load_model_client("claude-3-5-sonnet-20241022")
    """
    # Basic pattern matching or direct mapping
    lower_id = model_id.lower()
    # Check for OpenRouter first to handle prefixed models like openrouter-deepseek
    if "openrouter" in lower_id or "quasar" in lower_id:
        return OpenRouterClient(model_id)
    elif "claude" in lower_id:
        return ClaudeClient(model_id)
    elif "gemini" in lower_id:
        return GeminiClient(model_id)
    elif "deepseek" in lower_id:
        return DeepSeekClient(model_id)
    else:
        # Default to OpenAI
        return OpenAIClient(model_id)


##############################################################################
# 4) Example Usage in a Diplomacy "main" or Similar
##############################################################################


async def example_game_loop(game):
    """
    Pseudocode: Integrate with the Diplomacy loop.
    """
    # Suppose we gather all active powers
    active_powers = [
        (p_name, p_obj)
        for p_name, p_obj in game.powers.items()
        if not p_obj.is_eliminated()
    ]
    power_model_mapping = assign_models_to_powers()

    for power_name, power_obj in active_powers:
        model_id = power_model_mapping.get(power_name, "o3-mini")
        client = load_model_client(model_id)

        # Get possible orders from the game
        possible_orders = game.get_all_possible_orders()
        board_state = game.get_state()

        # Get orders from the client
        orders = await client.get_orders(board_state, power_name, possible_orders)
        game.set_orders(power_name, orders)

    # Then process, etc.
    game.process()


class LMServiceVersus:
    """
    Optional wrapper class if you want extra control.
    For example, you could store or reuse clients, etc.
    """

    def __init__(self):
        self.power_model_map = assign_models_to_powers()

    async def get_orders_for_power(self, game, power_name):
        model_id = self.power_model_map.get(power_name, "o3-mini")
        client = load_model_client(model_id)
        possible_orders = gather_possible_orders(game, power_name)
        board_state = game.get_state()
        return await client.get_orders(board_state, power_name, possible_orders)


##############################################################################
# 1) Add a method to filter visible messages (near top-level or in BaseModelClient)
##############################################################################
def get_visible_messages_for_power(conversation_messages, power_name):
    """
    Returns a chronological subset of conversation_messages that power_name can legitimately see.
    """
    visible = []
    for msg in conversation_messages:
        # GLOBAL might be 'ALL' or 'GLOBAL' depending on your usage
        if (
            msg["recipient"] == "ALL"
            or msg["recipient"] == "GLOBAL"
            or msg["sender"] == power_name
            or msg["recipient"] == power_name
        ):
            visible.append(msg)
    return visible  # already in chronological order if appended that way
