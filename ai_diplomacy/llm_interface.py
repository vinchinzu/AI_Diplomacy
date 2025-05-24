import logging
from typing import Optional, Dict, List, Any # Added Any for prompt_template_vars flexibility

from . import llm_utils
from .llm_coordinator import LocalLLMCoordinator
from .utils import log_llm_response # Assuming log_llm_response handles its own imports like csv, datetime

class AgentLLMInterface:
    """
    Handles all LLM interactions for a DiplomacyAgent, using a coordinator
    for requests and utility functions for prompt loading and JSON parsing.
    """

    def __init__(self, model_id: str, system_prompt: Optional[str], coordinator: LocalLLMCoordinator, power_name: str):
        self.model_id = model_id
        self.system_prompt = system_prompt
        self.coordinator = coordinator
        self.power_name = power_name # For logging and potentially for specific prompt variables
        self.logger = logging.getLogger(__name__) # Logger for this specific interface instance
        self.logger.setLevel(logging.DEBUG) # Or configure as needed

    async def _make_llm_call(
        self,
        prompt_text: str,
        log_file_path: str,
        game_phase: str,
        response_type_for_logging: str,
        expect_json: bool = False
    ) -> Any: # Returns Dict if expect_json else str
        """
        Private helper method to make an LLM call and handle common logic.
        """
        raw_response = ""
        success_status = "FAILURE_UNSPECIFIED" # Default, should be updated
        request_identifier = f"{self.power_name}:{response_type_for_logging}:{game_phase}"

        try:
            raw_response = await self.coordinator.request(
                self.model_id,
                prompt_text,
                self.system_prompt,
                request_identifier=request_identifier
            )

            if expect_json:
                if not raw_response or not raw_response.strip():
                    self.logger.warning(f"[{request_identifier}] LLM returned empty response when JSON was expected.")
                    success_status = "FAILURE_EMPTY_RESPONSE_EXPECTED_JSON"
                    parsed_response = {}
                else:
                    # Use self.logger for parsing, include power_name for context
                    parsed_response = llm_utils.extract_json_from_text(raw_response, self.logger, f"[{self.power_name}]")
                    if parsed_response:
                        success_status = "SUCCESS_PARSED_JSON"
                    else:
                        # extract_json_from_text logs parsing errors, so just mark as failure here
                        self.logger.warning(f"[{request_identifier}] Failed to parse JSON from LLM response. Raw: {raw_response[:200]}")
                        success_status = "FAILURE_JSON_PARSING"
                        # parsed_response is already {} from extract_json_from_text on failure
                
                log_llm_response(
                    log_file_path=log_file_path, model_name=self.model_id, power_name=self.power_name,
                    phase=game_phase, response_type=response_type_for_logging, raw_input_prompt=prompt_text,
                    raw_response=raw_response, success=success_status
                )
                return parsed_response
            else: # Expecting raw string
                if raw_response and raw_response.strip():
                    success_status = "SUCCESS_RAW_TEXT"
                else:
                    self.logger.warning(f"[{request_identifier}] LLM returned empty response for raw text request.")
                    success_status = "FAILURE_EMPTY_RESPONSE"
                
                log_llm_response(
                    log_file_path=log_file_path, model_name=self.model_id, power_name=self.power_name,
                    phase=game_phase, response_type=response_type_for_logging, raw_input_prompt=prompt_text,
                    raw_response=raw_response, success=success_status
                )
                return raw_response.strip() if raw_response else ""

        except Exception as e:
            self.logger.error(f"[{request_identifier}] Exception during LLM call or processing: {e}", exc_info=True)
            success_status = f"FAILURE_EXCEPTION_{type(e).__name__}"
            log_llm_response(
                log_file_path=log_file_path, model_name=self.model_id, power_name=self.power_name,
                phase=game_phase, response_type=response_type_for_logging, raw_input_prompt=prompt_text,
                raw_response=raw_response if raw_response else f"Exception: {e}", success=success_status
            )
            return {} if expect_json else "" # Return empty dict/str on error

    async def generate_diary_consolidation(
        self, year: str, year_diary_text: str, log_file_path: str, game_phase: str, power_name_for_prompt: str
    ) -> str:
        template_name = 'diary_consolidation_prompt.txt'
        prompt_text_template = llm_utils.load_prompt_file(template_name)
        if not prompt_text_template:
            self.logger.error(f"[{self.power_name}] Could not load prompt template: {template_name}")
            return f"(Error: Prompt template '{template_name}' not found)"

        prompt_template_vars = {
            "power_name": power_name_for_prompt, # Use the passed power_name for the prompt content
            "year": year,
            "year_diary_entries": year_diary_text
        }
        try:
            prompt_text = prompt_text_template.format(**prompt_template_vars)
        except KeyError as e:
            self.logger.error(f"[{self.power_name}] Missing key in prompt_template_vars for {template_name}: {e}")
            return f"(Error: Missing data for prompt template '{template_name}')"

        return await self._make_llm_call(
            prompt_text, log_file_path, game_phase, "diary_consolidation", expect_json=False
        )

    async def generate_negotiation_diary(
        self, prompt_template_vars: Dict[str, Any], log_file_path: str, game_phase: str
    ) -> Dict:
        template_name = 'negotiation_diary_prompt.txt'
        prompt_text_template = llm_utils.load_prompt_file(template_name)
        if not prompt_text_template:
            self.logger.error(f"[{self.power_name}] Could not load prompt template: {template_name}")
            return {"error": f"Prompt template '{template_name}' not found"}
        
        # Preprocess template for specific keys that cause issues with .format()
        # This logic might be better in load_prompt_file or a dedicated preprocessor if widely needed
        problematic_json_keys = ['negotiation_summary', 'updated_relationships', 'relationship_updates', 'intent']
        for key in problematic_json_keys:
            prompt_text_template = prompt_text_template.replace(f'\n  "{key}"', f'"{key}"')
        
        # Escape JSON-like braces before formatting
        temp_vars_placeholders = {key: f"<<{key}>>" for key in prompt_template_vars.keys()}
        temp_template = prompt_text_template
        for key, placeholder in temp_vars_placeholders.items():
            temp_template = temp_template.replace(f"{{{key}}}", placeholder)
        
        temp_template = temp_template.replace('{', '{{').replace('}', '}}')
        
        for key, placeholder in temp_vars_placeholders.items():
            temp_template = temp_template.replace(placeholder, f"{{{key}}}")

        try:
            prompt_text = temp_template.format(**prompt_template_vars)
        except KeyError as e:
            self.logger.error(f"[{self.power_name}] Missing key in prompt_template_vars for {template_name}: {e}")
            return {"error": f"Missing data for prompt template '{template_name}'"}

        return await self._make_llm_call(
            prompt_text, log_file_path, game_phase, "negotiation_diary", expect_json=True
        )

    async def generate_order_diary(
        self, prompt_template_vars: Dict[str, Any], log_file_path: str, game_phase: str
    ) -> Optional[str]: # Returns string content of "order_summary" or None
        template_name = 'order_diary_prompt.txt'
        prompt_text_template = llm_utils.load_prompt_file(template_name)
        if not prompt_text_template:
            self.logger.error(f"[{self.power_name}] Could not load prompt template: {template_name}")
            return None # Fallback handled by agent

        # Simplified preprocessing for order_diary_prompt if needed
        for key in ['order_summary']:
             prompt_text_template = prompt_text_template.replace(f'\n  "{key}"', f'"{key}"')
        
        # Escape JSON-like braces
        temp_vars_placeholders = {key: f"<<{key}>>" for key in prompt_template_vars.keys()}
        temp_template = prompt_text_template
        for key, placeholder in temp_vars_placeholders.items():
            temp_template = temp_template.replace(f"{{{key}}}", placeholder)
        temp_template = temp_template.replace('{', '{{').replace('}', '}}')
        for key, placeholder in temp_vars_placeholders.items():
            temp_template = temp_template.replace(placeholder, f"{{{key}}}")

        try:
            prompt_text = temp_template.format(**prompt_template_vars)
        except KeyError as e:
            self.logger.error(f"[{self.power_name}] Missing key in prompt_template_vars for {template_name}: {e}")
            return None

        parsed_response = await self._make_llm_call(
            prompt_text, log_file_path, game_phase, "order_diary", expect_json=True
        )
        return parsed_response.get("order_summary") if isinstance(parsed_response, dict) else None


    async def generate_phase_result_diary(
        self, prompt_template_vars: Dict[str, Any], log_file_path: str, game_phase: str
    ) -> str:
        template_name = 'phase_result_diary_prompt.txt'
        prompt_text_template = llm_utils.load_prompt_file(template_name)
        if not prompt_text_template:
            self.logger.error(f"[{self.power_name}] Could not load prompt template: {template_name}")
            return f"(Error: Prompt template '{template_name}' not found)"
        
        try:
            prompt_text = prompt_text_template.format(**prompt_template_vars)
        except KeyError as e:
            self.logger.error(f"[{self.power_name}] Missing key in prompt_template_vars for {template_name}: {e}")
            return f"(Error: Missing data for prompt template '{template_name}')"

        return await self._make_llm_call(
            prompt_text, log_file_path, game_phase, "phase_result_diary", expect_json=False
        )

    async def analyze_phase_and_update_state(
        self, prompt_template_vars: Dict[str, Any], log_file_path: str, game_phase: str
    ) -> Dict:
        template_name = 'state_update_prompt.txt'
        prompt_text_template = llm_utils.load_prompt_file(template_name)
        if not prompt_text_template:
            self.logger.error(f"[{self.power_name}] Could not load prompt template: {template_name}")
            return {"error": f"Prompt template '{template_name}' not found"}

        try:
            prompt_text = prompt_text_template.format(**prompt_template_vars)
        except KeyError as e:
            self.logger.error(f"[{self.power_name}] Missing key in prompt_template_vars for {template_name}: {e}")
            return {"error": f"Missing data for prompt template '{template_name}'"}

        return await self._make_llm_call(
            prompt_text, log_file_path, game_phase, "state_update", expect_json=True
        )

    async def generate_plan(
        self, context_prompt_text: str, planning_prompt_template_name: str, log_file_path: str, game_phase: str
    ) -> str:
        planning_prompt_instructions = llm_utils.load_prompt_file(planning_prompt_template_name)
        if not planning_prompt_instructions:
            self.logger.error(f"[{self.power_name}] Could not load planning prompt template: {planning_prompt_template_name}")
            return "Error: Planning prompt file not found."

        # The context_prompt_text is assumed to be pre-formatted
        full_prompt = f"{context_prompt_text}\n\n{planning_prompt_instructions}"

        return await self._make_llm_call(
            full_prompt, log_file_path, game_phase, "plan_generation", expect_json=False
        )

    async def generate_messages(
        self, full_prompt_for_messages: str, log_file_path: str, game_phase: str
    ) -> List[Dict[str, str]]:
        # full_prompt_for_messages is already constructed and formatted by the agent
        # It includes context + conversation_instructions.txt content
        
        # The _make_llm_call expects a dictionary if expect_json is true.
        # If the LLM is expected to return a list of messages directly as JSON root,
        # extract_json_from_text should handle it or be adapted.
        # For now, assume the LLM wraps it like {"messages": [...]} or it's handled by extract_json_from_text.
        parsed_response = await self._make_llm_call(
            full_prompt_for_messages, log_file_path, game_phase, "message_generation", expect_json=True
        )

        if isinstance(parsed_response, dict) and "messages" in parsed_response and isinstance(parsed_response["messages"], list):
            return parsed_response["messages"]
        elif isinstance(parsed_response, list): # If LLM directly returns a list
             # Perform basic validation
            valid_messages = []
            for msg in parsed_response:
                if isinstance(msg, dict) and "recipient" in msg and "content" in msg and "message_type" in msg:
                    valid_messages.append(msg)
                else:
                    self.logger.warning(f"[{self.power_name}:message_generation] Invalid message structure in direct list from LLM: {msg}")
            return valid_messages
        else:
            self.logger.warning(f"[{self.power_name}:message_generation] LLM response for messages was not a list under 'messages' key or a direct list. Parsed: {parsed_response}")
            return []
