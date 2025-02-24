import os
import json
from json import JSONDecodeError
import re
import logging
import ast

from typing import List, Dict, Optional
from dotenv import load_dotenv

import anthropic

os.environ["GRPC_PYTHON_LOG_LEVEL"] = "10"
from openai import OpenAI as DeepSeekOpenAI
from openai import OpenAI
from anthropic import Anthropic
from google import genai

from diplomacy.engine.message import GLOBAL

from .game_history import GameHistory
from .long_story_short import get_optimized_context
from .model_loader import load_model_client

# set logger back to just info
logger = logging.getLogger("client")
logger.setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)

load_dotenv()


##############################################################################
# 1) Base Interface
##############################################################################
class BaseModelClient:
    """
    Base interface for any LLM client we want to plug in.
    Each must provide:
      - generate_response(prompt: str) -> str (with empty_system=True if needed)
      - get_orders(board_state, power_name, possible_orders, game_history, phase_summaries) -> List[str]
      - get_conversation_reply(power_name, conversation_so_far, game_phase) -> str
    """

    def __init__(self, model_name: str, power_name: Optional[str] = None, emptysystem: bool = False):
        self.model_name = model_name
        self.power_name = power_name
        self.emptysystem = emptysystem

        # Conditionally load system prompt
        if not self.emptysystem:
            if self.power_name:
                try:
                    self.system_prompt = load_prompt(f"{self.power_name.lower()}_system_prompt.txt")
                except FileNotFoundError:
                    logger.warning(f"No specific system prompt found for {self.power_name}; using default.")
                    self.system_prompt = load_prompt("system_prompt.txt")
            else:
                self.system_prompt = load_prompt("system_prompt.txt")
        else:
            # If emptysystem is True, skip loading any system prompt
            self.system_prompt = ""
    # emptysystem defaults to false but if true will tell the LLM to not add a system prompt
    def generate_response(self, prompt: str, empty_system: bool = False) -> str:
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
        game_history,  # Or GameHistory instance
        phase_summaries: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Overhauled to delegate the final formatting to context_prompt.txt, inserting
        placeholders for expansions (phase info, supply centers, units, blah blah).

        This version is 'surgical' and uses placeholders from @context_prompt.txt 
        rather than building large strings in code.
        """
        from ai_diplomacy.utils import (
            expand_phase_info,
            format_power_units_and_centers,  # Now includes neutral centers info
            organize_history_by_relationship,
            format_possible_orders,
            format_convoy_paths,
            generate_threat_assessment,
            generate_sc_projection
        )
        # 1) Grab the template from context_prompt.txt
        template_text = load_prompt("context_prompt.txt")

        # 2) Expand the current phase 
        phase_expanded = expand_phase_info(game, board_state)

        # 3) Our forces (units + centers, including neutral centers)
        our_forces_summary = format_power_units_and_centers(game, power_name, board_state)

        # 4) Summaries for enemies
        enemies_forces_summary = ""
        for pwr in board_state["units"]:
            if pwr != power_name:
                enemies_forces_summary += format_power_units_and_centers(game, pwr, board_state)

        # 5) Neutral Supply Centers
        neutral_supply_centers_summary = format_power_units_and_centers(game, 'NEUTRAL', board_state)

        # 6) Gather the conversation text
        raw_conversation_text = ""
        if hasattr(game_history, "get_game_history"):
            raw_conversation_text = game_history.get_game_history(power_name) or "(No history yet)"
        else:
            # Might be a plain string
            raw_conversation_text = game_history if isinstance(game_history, str) else "(No history yet)"

        # Organize history by relationship
        organized_history = organize_history_by_relationship(raw_conversation_text)

        # Get optimized context (summaries if needed)
        optimized_phases, optimized_messages = get_optimized_context(
            game, 
            game_history, 
            power_name, 
            organized_history
        )

        # Use the optimized message history
        history_text = optimized_messages

        # 7) Format possible orders
        possible_orders_text = format_possible_orders(game, possible_orders)

        # 8) Convoy Paths
        logger.debug(f"convoy_paths_possible is: {game.convoy_paths_possible}")
        convoy_paths_text = format_convoy_paths(game, game.convoy_paths_possible, power_name)

        # 9) Threat Assessment
        threat_text = generate_threat_assessment(game, board_state, power_name)

        # 10) Supply Center Projection
        sc_projection_text = generate_sc_projection(game, board_state, power_name)

        # 11) Past Phase Summaries
        if optimized_phases:
            # Combine each phase summary for reference
            lines = []
            for ph, summ in optimized_phases.items():
                # Check if this is a summary entry
                if ph.startswith("SUMMARY_UNTIL_"):
                    lines.append(f"HISTORICAL SUMMARY (until {ph[13:]}):\n{summ}\n")
                else:
                    lines.append(f"PHASE {ph}:\n{summ}\n")
            historical_summaries = "\n".join(lines)
        else:
            historical_summaries = "(No historical summaries yet)"

        # 12) Plug everything into context_prompt.txt
        final_prompt = template_text.format(
            power_name=power_name,
            phase_expanded=phase_expanded,
            our_forces_summary=our_forces_summary,
            neutral_supply_centers_summary=neutral_supply_centers_summary,
            enemies_forces_summary=enemies_forces_summary,
            history_text=history_text,
            possible_orders_text=possible_orders_text,
            convoy_paths_text=convoy_paths_text,
            threat_text=threat_text,
            sc_projection_text=sc_projection_text,
            historical_summaries=historical_summaries,
        )

        return final_prompt

    def build_prompt(
        self,
        game,
        board_state,
        power_name: str,
        possible_orders: Dict[str, List[str]],
        game_history: GameHistory,
        phase_summaries: Optional[Dict[str, str]] = None,
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
            phase_summaries,
        )

        return context + "\n\n" + instructions

    def get_orders(
        self,
        game,
        board_state,
        power_name: str,
        possible_orders: Dict[str, List[str]],
        conversation_text: str,
        phase_summaries: Optional[Dict[str, str]] = None,
        model_error_stats=None,
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
            phase_summaries,
        )

        raw_response = ""

        try:
            raw_response = self.generate_response(prompt)
            logger.info(
                f"[{self.model_name}] Raw LLM response for {power_name}:\n{raw_response}"
            )

            # Attempt to parse the final "orders" from the LLM
            move_list = self._extract_moves(raw_response, power_name)

            if not move_list:
                logger.warning(
                    f"[{self.model_name}] Could not extract moves for {power_name}. Using fallback."
                )
                if model_error_stats is not None:
                    # forcibly convert sets to string
                    model_name_for_stats = str(self.model_name)
                    model_error_stats[model_name_for_stats]["order_decoding_errors"] += 1

                return self.fallback_orders(possible_orders)
            # Validate or fallback
            validated_moves = self._validate_orders(move_list, possible_orders)
            return validated_moves

        except Exception as e:
            logger.error(f"[{self.model_name}] LLM error for {power_name}: {e}")
            if model_error_stats is not None:
                # forcibly convert sets to string
                model_name_for_stats = str(self.model_name)
                model_error_stats[model_name_for_stats]["order_decoding_errors"] += 1

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
            # Add braces back around the captured group as needed
            captured = matches.group(1).strip()

            if captured.startswith("{{") and captured.endswith("}}"):
                # remove ONE leading '{' and ONE trailing '}'
                # so {{ "orders": [...] }} becomes { "orders": [...] }
                logger.debug(f"[{self.model_name}] Detected double braces for {power_name}, trimming extra braces.")
                # strip exactly one brace pair
                trimmed = captured[1:-1].strip()
                json_text = trimmed
            elif captured.startswith("{"):
                json_text = captured
            else:
                json_text = "{" + captured + "}"

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

        logger.debug(f"[{self.model_name}] Validated moves: {validated}")
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

    def build_conversation_prompt(
        self,
        game,
        board_state,
        power_name: str,
        possible_orders: Dict[str, List[str]],
        game_history: GameHistory,
        game_phase: str,
        phase_summaries: Optional[Dict[str, str]] = None,
    ) -> str:
        instructions = load_prompt("conversation_instructions.txt")

        context = self.build_context_prompt(
            game,
            board_state,
            power_name,
            possible_orders,
            game_history,
            phase_summaries,
        )

        return context + "\n\n" + instructions

    def get_conversation_reply(
        self,
        game,
        board_state,
        power_name: str,
        possible_orders: Dict[str, List[str]],
        game_history: GameHistory,
        game_phase: str,
        active_powers: Optional[List[str]] = None,
        phase_summaries: Optional[Dict[str, str]] = None,
    ) -> str:
        prompt = self.build_conversation_prompt(
            game,
            board_state,
            power_name,
            possible_orders,
            game_history,
            game_phase,
            phase_summaries,
        )

        raw_response = self.generate_response(prompt)

        messages = []
        if raw_response:
            try:
                # Find the JSON block between double curly braces
                json_matches = re.findall(r"\{\{(.*?)\}\}", raw_response, re.DOTALL)

                if not json_matches:
                    # try normal
                    logger.debug(
                        f"[{self.model_name}] No JSON block found in LLM response for {power_name}. Trying double braces."
                    )
                    json_matches = re.findall(
                        r"PARSABLE OUTPUT:\s*\{(.*?)\}", raw_response, re.DOTALL
                    )

                if not json_matches:
                    # try backtick fences
                    logger.debug(
                        f"[{self.model_name}] No JSON block found in LLM response for {power_name}. Trying backtick fences."
                    )
                    json_matches = re.findall(
                        r"```json\n(.*?)\n```", raw_response, re.DOTALL
                    )

                for match in json_matches:
                    try:
                        if match.strip().startswith(r"{"):
                            message_data = json.loads(match.strip())
                        else:
                            message_data = json.loads(f"{{{match}}}")

                        # Extract message details
                        message_type = message_data.get("message_type", "global")
                        content = message_data.get("content", "").strip()
                        recipient = message_data.get("recipient", GLOBAL)

                        # Validate recipient if private message
                        if message_type == "private" and recipient not in active_powers:
                            logger.warning(
                                f"Invalid recipient {recipient} for private message, defaulting to GLOBAL"
                            )
                            recipient = GLOBAL

                        # For private messages, ensure recipient is specified
                        if message_type == "private" and recipient == GLOBAL:
                            logger.warning(
                                "Private message without recipient specified, defaulting to GLOBAL"
                            )

                        # Log for debugging
                        logger.info(
                            f"Power {power_name} sends {message_type} message to {recipient}"
                        )

                        # Keep local record for building future conversation context
                        message = {
                            "sender": power_name,
                            "recipient": recipient,
                            "content": content,
                        }

                        messages.append(message)

                    except (json.JSONDecodeError, AttributeError) as e:
                        message = None

            except AttributeError:
                logger.error("Error parsing raw response")

        # Deduplicate messages
        messages = list(set([json.dumps(m) for m in messages]))
        messages = [json.loads(m) for m in messages]

        return messages


##############################################################################
# 2) Concrete Implementations
##############################################################################


class OpenAIClient(BaseModelClient):
    """
    For 'o3-mini', 'gpt-4o', or other OpenAI model calls.
    """

    def __init__(self, model_name: str, power_name: Optional[str] = None, emptysystem: bool = False):
        super().__init__(model_name, power_name, emptysystem)
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    def generate_response(self, prompt: str, empty_system: bool = False) -> str:
        # Updated to new API format
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt if not empty_system else ""},
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

    def __init__(self, model_name: str, power_name: Optional[str] = None, emptysystem: bool = False):
        super().__init__(model_name, power_name, emptysystem)
        self.client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    def generate_response(self, prompt: str, empty_system: bool = False) -> str:
        # Updated Claude messages format
        try:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=2000,
                system=self.system_prompt if not empty_system else "", 
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

    def __init__(self, model_name: str, power_name: Optional[str] = None, emptysystem: bool = False):
        super().__init__(model_name, power_name, emptysystem)
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    def generate_response(self, prompt: str, empty_system: bool = False) -> str:
        if empty_system:
            full_prompt = prompt
        else:
            full_prompt = self.system_prompt + prompt

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
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

    def __init__(self, model_name: str, power_name: Optional[str] = None, emptysystem: bool = False):
        super().__init__(model_name, power_name, emptysystem)
        self.api_key = os.environ.get("DEEPSEEK_API_KEY")
        self.client = DeepSeekOpenAI(
            api_key=self.api_key, base_url="https://api.deepseek.com/"
        )

    def generate_response(self, prompt: str, empty_system: bool = False) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt if not empty_system else ""},
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


##############################################################################
# 4) Example Usage in a Diplomacy "main" or Similar
##############################################################################


def example_game_loop(game):
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
        client = load_model_client(model_id, power_name=power_name)

        # Get possible orders from the game
        possible_orders = game.get_all_possible_orders()
        board_state = game.get_state()

        # Get orders from the client
        orders = client.get_orders(board_state, power_name, possible_orders)
        game.set_orders(power_name, orders)

    # Then process, etc.
    game.process()


class LMServiceVersus:
    """
    Optional wrapper class if you want extra control.
    For example, you could store or reuse clients, etc.
    """

    def __init__(self):
        self.power_model_map = assign_models_to_powers(randomize=True)

    def get_orders_for_power(self, game, power_name):
        model_id = self.power_model_map.get(power_name, "o3-mini")
        client = load_model_client(model_id, power_name=power_name)
        possible_orders = gather_possible_orders(game, power_name)
        board_state = game.get_state()
        return client.get_orders(board_state, power_name, possible_orders)


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


def load_prompt(filename: str) -> str:
    """Helper to load prompt text from file"""
    with open(f"./ai_diplomacy/prompts/{filename}", "r") as f:
        return f.read().strip()
