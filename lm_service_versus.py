import os
import json
import re
import logging
import ast

from typing import List, Dict, Optional
from dotenv import load_dotenv

# Anthropics
import anthropic

# Google Generative AI
# Set gemini to more verbose
os.environ['GRPC_PYTHON_LOG_LEVEL'] = '10' 
import google.generativeai as genai  # Import after setting log level

# DeepSeek
from openai import OpenAI as DeepSeekOpenAI

# set logger back to just info
logger = logging.getLogger('lm_service_versus')
logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO)

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
        self.system_prompt_response = """
        You are a Diplomacy expert.
        You are given a board state and a list of possible orders for a power.
        You need to produce the final orders for that power.
        You have a lot of information to work with:
            Power
            Current Phase
            Enemy Units
            Enemy Centers
            Your Units
            Your Centers
            Possible Orders

        After thinking about the information, you must produce a list of orders.
        You must respond with a JSON object in the format:
        PARSABLE OUTPUT:
        {
            "orders": ["Your move 1","Your move 2"]
        }
        it's paramount that you include the parsable output block.
        """
        self.system_prompt_conversation = """
            You are playing as {power_name} in a Diplomacy negotiation during phase {game_phase}.
            You have read all messages so far. Now produce a single new message with your strategy or statement.
            REQUIRED FORMAT:
            For any message, you must respond with one of these exact JSON structures:

            1. For global messages:
            {{
                "message_type": "global",
                "content": "Your message here"
            }}

            2. For private messages:
            {{
                "message_type": "private",
                "recipient": "POWER_NAME",
                "content": "Your message here"
            }}

            IMPORTANT RULES:
            - Your response must be ONLY the JSON object, nothing else
            - Do not include any explanation or additional text
            - Ensure the JSON is properly formatted and escaped
            - The content field should contain your diplomatic message
            - For private messages, recipient must be one of: AUSTRIA, FRANCE, GERMANY, ITALY, RUSSIA, TURKEY, ENGLAND

            Example valid responses:
            {{
                "message_type": "global",
                "content": "I propose we all work together against Turkey."
            }}

            {{
                "message_type": "private",
                "recipient": "FRANCE",
                "content": "Let's form a secret alliance against Germany."
            }}
        """
    def generate_response(self, prompt: str) -> str:
        """
        Returns a raw string from the LLM.
        Subclasses override this.
        """
        raise NotImplementedError("Subclasses must implement generate_response().")


    def build_prompt(
        self, 
        board_state, 
        power_name: str, 
        possible_orders: Dict[str, List[str]], 
        conversation_text: str,
        phase_summaries: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Unified prompt approach: incorporate conversation and 'PARSABLE OUTPUT' requirements.
        """
        # Get our units and centers
        units_info = board_state["units"].get(power_name, [])
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


        summary = (
            f"Power: {power_name}\n"
            f"Current Phase: {year_phase}\n"
            f"Enemy Units: {enemy_units}\n"
            f"Enemy Centers: {enemy_centers}\n"
            f"Your Units: {units_info}\n"
            f"Your Centers: {centers_info}\n"
            f"Possible Orders:\n"
        )
        for loc, orders in possible_orders.items():
            summary += f"  {loc}: {orders}\n"

        few_shot_example = """
--- EXAMPLE ---
Power: FRANCE
Phase: S1901M
Your Units: ['A PAR','F BRE']
Possible Orders:
  PAR: ['A PAR H','A PAR - BUR','A PAR - GAS']
  BRE: ['F BRE H','F BRE - MAO']

Chain-of-thought:
[Be consistent with your secret chain-of-thought here, but do not reveal it. 
Think about the enemy units and centers and how they might move, think about your units and centers, the conversation that's happened, the game phase summaries so far, any public and private goals you have or others might have based on conversation and reality of positions.
Aim for best strategic moves based on the possible orders, 
and produce an output in PARSABLE JSON format as shown below.]

PARSABLE OUTPUT:{
  "orders": ["A PAR - BUR","F BRE - MAO"]
}
--- END EXAMPLE ---
"""

        instructions = (
            "IMPORTANT:\n"
            "For your chain of thought, think about the enemy units and centers and how they might move, think about your units and centers, the conversation that's happened, the game phase summaries so far, any public and private goals you have or others might have based on conversation and reality of positions.\n"
            "Return your chain-of-thought and end with EXACTLY one JSON block:\n"
            "PARSABLE OUTPUT:{\n"
            '  "orders": [ ... ]\n'
            "}\n"
            "No extra braces outside that block.\n"
            "The most important thing is to make SURE to include your orders in the JSON block.\n"

        )

        # 1) Prepare a block of text for the phase_summaries
        if phase_summaries:
            historical_summaries = "\nPAST PHASE SUMMARIES:\n"
            for phase_key, summary_txt in phase_summaries.items():
                # You can format the summary however you prefer
                logger.info(f"[DEBUG] phase_key: {phase_key}, summary_txt: {summary_txt}")
                historical_summaries += f"\nPHASE {phase_key}:\n{summary_txt}\n"
        else:
            historical_summaries = "\n(No historical summaries provided)\n"

        prompt = (
            "Relevant Conversation:\n" + conversation_text + "\n\n"
            + "Historical Summaries:\n" + historical_summaries + "\n\n"
            + summary + few_shot_example + "\n"
            + instructions
        )
        return prompt

    def get_orders(
        self, 
        board_state, 
        power_name: str, 
        possible_orders: Dict[str, List[str]], 
        conversation_text: str,
        phase_summaries: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        """
        1) Builds the prompt with conversation context if available
        2) Calls LLM
        3) Parses JSON block
        """
        prompt = self.build_prompt(board_state, power_name, possible_orders, conversation_text, phase_summaries)

        raw_response = ""

        try:
            raw_response = self.generate_response(prompt)
            logger.info(f"[{self.model_name}] Raw LLM response for {power_name}:\n{raw_response}")

            # Attempt to parse the final "orders" from the LLM
            move_list = self._extract_moves(raw_response, power_name)
            if not move_list:
                logger.warning(f"[{self.model_name}] Could not extract moves for {power_name}. Using fallback.")
                return self.fallback_orders(possible_orders)

            # Validate or fallback
            validated_moves = self._validate_orders(move_list, possible_orders)
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
        pattern = r"PARSABLE OUTPUT\s*:\s*\{(.*?)\}\s*$"
        matches = re.search(pattern, raw_response, re.DOTALL)
        if not matches:
            # Some LLMs might not put the colon or might have triple backtick fences.
            logger.debug(f"[{self.model_name}] Regex parse #1 failed for {power_name}. Trying alternative patterns.")
            
            # 1b) Check for inline JSON after "PARSABLE OUTPUT"
            pattern_alt = r"PARSABLE OUTPUT\s*\{(.*?)\}\s*$"
            matches = re.search(pattern_alt, raw_response, re.DOTALL)

        # 2) If still no match, check for triple-backtick code fences containing JSON
        if not matches:
            code_fence_pattern = r"```json\s*\{(.*?)\}\s*```"
            matches = re.search(code_fence_pattern, raw_response, re.DOTALL)
            if matches:
                logger.debug(f"[{self.model_name}] Found triple-backtick JSON block for {power_name}.")
        
        # 3) Attempt to parse JSON if we found anything
        json_text = None
        if matches:
            # Add braces back around the captured group
            json_text = "{%s}" % matches.group(1).strip()
            json_text = json_text.strip()

        if not json_text:
            logger.debug(f"[{self.model_name}] No JSON text found in LLM response for {power_name}.")
            return None

        # 3a) Try JSON loading
        try:
            data = json.loads(json_text)
            return data.get("orders", None)
        except json.JSONDecodeError as e:
            logger.warning(f"[{self.model_name}] JSON decode failed for {power_name}: {e}. Trying bracket fallback.")

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
                logger.warning(f"[{self.model_name}] Bracket fallback parse also failed for {power_name}: {e2}")

        # If all attempts failed
        return None

    def _validate_orders(self, moves: List[str], possible_orders: Dict[str, List[str]]) -> List[str]:
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
                validated.append(hold_candidates[0] if hold_candidates else orders_list[0])

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

    def build_conversation_reply(
        self, 
        power_name: str, 
        conversation_so_far: str, 
        game_phase: str,
        phase_summaries: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Produce a single message in valid JSON with 'message_type' etc.
        """
        prompt = f"""
You are playing a power named {power_name} in a Diplomacy game during the {game_phase} phase.

Here are the past phase summaries:
{phase_summaries}

Here is the conversation so far:
{conversation_so_far}

You must now respond with exactly ONE JSON object. 

Example response formats:
1. For a global message:
{{
    "message_type": "global",
    "content": "I propose we all work together against Turkey."
}}

2. For a private message:
{{
    "message_type": "private",
    "recipient": "FRANCE",
    "content": "Let's form a secret alliance against Germany."
}}

Think strategically about your diplomatic position the past phase summaries and respond with your message in the correct JSON format:"""
        return prompt
    
    def generate_conversation_reply(self, power_name: str, conversation_so_far: str, game_phase: str) -> str:
        """
        Overwritten by subclasses.
        """
        raise NotImplementedError("Subclasses must implement generate_conversation_reply().")

##############################################################################
# 2) Concrete Implementations
##############################################################################

class OpenAIClient(BaseModelClient):
    """
    For 'o3-mini', 'gpt-4o', or other OpenAI model calls.
    """
    def __init__(self, model_name: str):
        super().__init__(model_name)
        from openai import OpenAI  # Import the new client
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    def generate_response(self, prompt: str) -> str:
        # Updated to new API format
        system_prompt = self.system_prompt_response
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
            )
            if not response or not hasattr(response, "choices") or not response.choices:
                logger.warning(f"[{self.model_name}] Empty or invalid result in generate_response. Returning empty.")
                return ""
            return response.choices[0].message.content.strip()
        except json.JSONDecodeError as json_err:
            logger.error(f"[{self.model_name}] JSON decoding failed in generate_response: {json_err}")
            return ""
        except Exception as e:
            logger.error(f"[{self.model_name}] Unexpected error in generate_response: {e}")
            return ""

    def get_conversation_reply(
        self, 
        power_name: str, 
        conversation_so_far: str, 
        game_phase: str, 
        phase_summaries: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Produces a single message with the appropriate JSON format.
        """
        import json
        from json.decoder import JSONDecodeError
        # load the system prompt but formatted with the power name and game phase
        system_prompt = self.system_prompt_conversation.format(power_name=power_name, game_phase=game_phase)
        conversation_prompt = self.build_conversation_reply(power_name, conversation_so_far, game_phase, phase_summaries)

        try:
            # Perform the request
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": conversation_prompt}
                ],
                max_completion_tokens=2000
            )

            # If there's no valid response or choices, return empty
            if not response or not hasattr(response, "choices") or not response.choices:
                logger.warning(f"[{self.model_name}] Empty or invalid response for {power_name}. Returning empty.")
                return ""

            # Attempt to parse the content (OpenAI library usually does this, but we add a safety net)
            return response.choices[0].message.content.strip()

        except JSONDecodeError as json_err:
            logger.error(f"[{self.model_name}] JSON decoding failed for {power_name}: {json_err}")
            return ""  # Fallback
        except Exception as e:
            logger.error(f"[{self.model_name}] Unexpected error for {power_name}: {e}")
            return ""

class ClaudeClient(BaseModelClient):
    """
    For 'claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', etc.
    """
    def __init__(self, model_name: str):
        super().__init__(model_name)
        self.client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY")
        )

    def generate_response(self, prompt: str) -> str:
        system_prompt = self.system_prompt_response
        # Updated Claude messages format
        try:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=2000,
                system=system_prompt,  # system is now a top-level parameter
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            if not response.content:
                logger.warning(f"[{self.model_name}] Empty content in Claude generate_response. Returning empty.")
                return ""
            return response.content[0].text.strip() if response.content else ""
        except json.JSONDecodeError as json_err:
            logger.error(f"[{self.model_name}] JSON decoding failed in generate_response: {json_err}")
            return ""
        except Exception as e:
            logger.error(f"[{self.model_name}] Unexpected error in generate_response: {e}")
            return ""

    def get_conversation_reply(
        self, 
        power_name: str, 
        conversation_so_far: str, 
        game_phase: str, 
        phase_summaries: Optional[Dict[str, str]] = None,
    ) -> str:
        system_prompt = f"You are playing as {power_name} in this Diplomacy negotiation phase {game_phase}."
        user_prompt = self.build_conversation_reply(power_name, conversation_so_far, game_phase, phase_summaries)
        try:
            response = self.client.messages.create(
                model=self.model_name,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=2000
            )
            if not response.content:
                logger.warning(f"[{self.model_name}] No content in Claude conversation. Returning empty.")
                return ""
            return response.content[0].text.strip()
        except json.JSONDecodeError as json_err:
            logger.error(f"[{self.model_name}] JSON decoding failed in conversation: {json_err}")
            return ""
        except Exception as e:
            logger.error(f"[{self.model_name}] Unexpected error in conversation: {e}")
            return ""

class GeminiClient(BaseModelClient):
    """
    For 'gemini-1.5-flash' or other Google Generative AI models.
    """
    def __init__(self, model_name: str):
        super().__init__(model_name)
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        self.generation_config = {
            "temperature": 0.7,
            "max_output_tokens": 2000,
        }

    def generate_response(self, prompt: str) -> str:
        system_prompt = self.system_prompt_response
        full_prompt = system_prompt + prompt
        
        try:
            model = genai.GenerativeModel(
                self.model_name,
                generation_config=self.generation_config
            )
            response = model.generate_content(full_prompt)
            if not response or not response.text:
                logger.warning(f"[{self.model_name}] Empty Gemini generate_response. Returning empty.")
                return ""
            return response.text.strip()
        except Exception as e:
            logger.error(f"[{self.model_name}] Error in Gemini generate_response: {e}")
            return ""

    def get_conversation_reply(
        self, 
        power_name: str, 
        conversation_so_far: str, 
        game_phase: str, 
        phase_summaries: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Produce a single short conversation message from the Gemini model, 
        given existing conversation context.
        """
        # Similar approach: create a system plus user prompt, then call model.generate_content
        system_prompt = f"You are playing as {power_name} in this Diplomacy negotiation phase {game_phase}.\n"
        user_prompt = self.build_conversation_reply(power_name, conversation_so_far, game_phase, phase_summaries)
        full_prompt = system_prompt + user_prompt

        try:
            model = genai.GenerativeModel(
                self.model_name,
                generation_config=self.generation_config
            )
            response = model.generate_content(full_prompt)
            if not response or not response.text:
                logger.warning(f"[{self.model_name}] Empty Gemini conversation response. Returning empty.")
                return ""
            else:
                logger.info(f"[{self.model_name}] Gemini message succesfully generated.")
            return response.text.strip()
        except json.JSONDecodeError as json_err:
            logger.error(f"[{self.model_name}] JSON decode error in conversation: {json_err}")
            return ""
        except Exception as e:
            logger.error(f"[{self.model_name}] Error in Gemini get_conversation_reply: {e}")
            return ""

class DeepSeekClient(BaseModelClient):
    """
    For DeepSeek R1 'deepseek-reasoner'
    """
    def __init__(self, model_name: str):
        super().__init__(model_name)
        self.api_key = os.environ.get("DEEPSEEK_API_KEY")
        self.client = DeepSeekOpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com/"
        )

    def generate_response(self, prompt: str) -> str:
        system_prompt = self.system_prompt_response
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                stream=False
            )
            logger.debug(f"[{self.model_name}] Raw DeepSeek response:\n{response}")

            if not response or not response.choices:
                logger.warning(f"[{self.model_name}] No valid response in generate_response.")
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
                    logger.error(f"[{self.model_name}] Missing required fields in response: {content}")
                    return ""
                return content
            except json.JSONDecodeError:
                logger.error(f"[{self.model_name}] Response is not valid JSON: {content}")
                content = content.replace("'", '"')
                try:
                    json.loads(content)
                    return content
                except:
                    return ""

        except Exception as e:
            logger.error(f"[{self.model_name}] Unexpected error in generate_response: {e}")
            return ""
    
    def get_conversation_reply(
        self, 
        power_name: str, 
        conversation_so_far: str, 
        game_phase: str, 
        phase_summaries: Optional[Dict[str, str]] = None,
    ) -> str:
        system_prompt = self.system_prompt_conversation.format(power_name=power_name, game_phase=game_phase)
        user_prompt = self.build_conversation_reply(power_name, conversation_so_far, game_phase, phase_summaries)
        user_prompt += "\n\nPlease provide ONLY a single JSON object as per the examples above."

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                max_completion_tokens=2000
            )
            logger.debug(f"[{self.model_name}] Raw DeepSeek conversation response:\n{response}")

            if not response or not response.choices:
                logger.warning(f"[{self.model_name}] No valid choices in conversation reply.")
                return ""
            return response.choices[0].message.content.strip()
        except json.JSONDecodeError as json_err:
            logger.error(f"[{self.model_name}] JSON decode error in conversation: {json_err}")
            return ""
        except Exception as e:
            logger.error(f"[{self.model_name}] Unexpected error in conversation: {e}")
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
    if "claude" in lower_id:
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

def assign_models_to_powers():
    """
    Example usage: define which model each power uses.
    Return a dict: { power_name: model_id, ... }
    POWERS = ['AUSTRIA', 'ENGLAND', 'FRANCE', 'GERMANY', 'ITALY', 'RUSSIA', 'TURKEY']
    """
    # "RUSSIA": "deepseek-reasoner", deepseek api having issues
    return {
        "FRANCE": "o3-mini",
        "GERMANY": "claude-3-5-sonnet-20241022",
        "ENGLAND": "gemini-2.0-flash",
        "RUSSIA": "gemini-2.0-flash-lite-preview-02-05",
        "ITALY": "gpt-4o",
        "AUSTRIA": "gpt-4o-mini",
        "TURKEY": "claude-3-5-haiku-20241022",
    }

def example_game_loop(game):
    """
    Pseudocode: Integrate with the Diplomacy loop.
    """
    # Suppose we gather all active powers
    active_powers = [(p_name, p_obj) for p_name, p_obj in game.powers.items() if not p_obj.is_eliminated()]
    power_model_mapping = assign_models_to_powers()

    for power_name, power_obj in active_powers:
        model_id = power_model_mapping.get(power_name, "o3-mini")
        client = load_model_client(model_id)

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
        self.power_model_map = assign_models_to_powers()
    
    def get_orders_for_power(self, game, power_name):
        model_id = self.power_model_map.get(power_name, "o3-mini")
        client = load_model_client(model_id)
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
            msg['recipient'] == 'ALL' or msg['recipient'] == 'GLOBAL'
            or msg['sender'] == power_name
            or msg['recipient'] == power_name
        ):
            visible.append(msg)
    return visible  # already in chronological order if appended that way 