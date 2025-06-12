from typing import Any, List, Dict
import logging

from .core import GenericLLMAgentInterface
from .prompt_strategy import BasePromptStrategy
from .llm_coordinator import LLMCoordinator
from . import constants as generic_constants  # For default game_id, phase etc.

logger = logging.getLogger(__name__)


class GenericLLMAgent(GenericLLMAgentInterface):
    """
    A generic LLM agent implementation that uses a prompt strategy and an LLM coordinator.
    """

    def __init__(
        self,
        agent_id: str,
        config: Any,
        llm_coordinator: LLMCoordinator,
        prompt_strategy: BasePromptStrategy,
    ):
        """
        Initializes the GenericLLMAgent.

        Args:
            agent_id: The unique identifier for the agent.
            config: Configuration for the agent. Expected to have 'model_id',
                    and optionally 'system_prompt', 'game_id', 'phase', 'verbose_llm_debug'.
            llm_coordinator: An instance to coordinate LLM interactions.
            prompt_strategy: An instance of BasePromptStrategy for building prompts.
        """
        self.agent_id = agent_id
        self.config = config  # Should contain model_id, system_prompt etc.
        self.llm_coordinator = llm_coordinator
        self.prompt_strategy = prompt_strategy
        self._internal_state: Dict[str, Any] = {}  # Basic internal state
        logger.info(f"Agent {self.agent_id} initialized with model {self.config.get('model_id')}.")

    async def decide_action(
        self, state: Any, possible_actions: Any, action_type: str = "decide_action"
    ) -> Any:
        """
        Decides the next action to take based on the current state and possible actions.
        """
        logger.debug(
            f"Agent {self.agent_id}: Deciding action with type '{action_type}'. State: {state}, Possible Actions: {possible_actions}"
        )
        try:
            # Construct prompt_context, flattening state if it's a dictionary
            prompt_context = {
                "possible_actions": possible_actions,
                "internal_state": self._internal_state,
            }
            if isinstance(state, dict):
                prompt_context.update(state)
            else:
                prompt_context["state"] = state

            prompt = self.prompt_strategy.build_prompt(action_type=action_type, context=prompt_context)

            # Extract necessary params from config, with defaults
            model_id = self.config.get("model_id")
            if not model_id:
                logger.error(f"Agent {self.agent_id}: model_id not found in config.")
                return {"error": "Missing model_id in agent configuration"}

            system_prompt = self.config.get(
                "system_prompt", self.prompt_strategy.system_prompt_template
            )  # Use strategy's generic system prompt if none in config
            game_id = self.config.get("game_id", generic_constants.DEFAULT_GAME_ID)
            phase = self.config.get(
                "phase", "decide_action"
            )  # Or use a more specific phase from state if available
            verbose_llm_debug = self.config.get("verbose_llm_debug", False)

            logger.debug(f"Agent {self.agent_id}: Calling LLM for action decision. Model: {model_id}")
            response_json = await self.llm_coordinator.call_json(
                prompt=prompt,
                model_id=model_id,
                agent_id=self.agent_id,
                game_id=game_id,
                phase=phase,
                system_prompt=system_prompt,
                verbose_llm_debug=verbose_llm_debug,
                # tools=self.config.get('tools'), # If tools are part of config
                # expected_fields=self.config.get('expected_action_fields') # If specific fields are expected
            )
            logger.info(f"Agent {self.agent_id}: Action decision received: {response_json}")
            return response_json
        except Exception as e:
            logger.error(f"Agent {self.agent_id}: Error during decide_action: {e}", exc_info=True)
            return {"error": str(e), "details": "Failed to decide action via LLM."}

    async def generate_communication(
        self, state: Any, recipients: Any, action_type: str = "generate_communication"
    ) -> Any:
        """
        Generates communication content for specified recipients.
        """
        logger.debug(
            f"Agent {self.agent_id}: Generating communication with type '{action_type}'. State: {state}, Recipients: {recipients}"
        )
        try:
            # Construct prompt_context, flattening state if it's a dictionary
            prompt_context = {
                "recipients": recipients,
                "internal_state": self._internal_state,
            }
            if isinstance(state, dict):
                prompt_context.update(state)
            else:
                prompt_context["state"] = state

            prompt = self.prompt_strategy.build_prompt(action_type=action_type, context=prompt_context)

            model_id = self.config.get("model_id")
            if not model_id:
                logger.error(f"Agent {self.agent_id}: model_id not found in config.")
                return {"error": "Missing model_id in agent configuration"}

            system_prompt = self.config.get("system_prompt", self.prompt_strategy.system_prompt_template)
            game_id = self.config.get("game_id", generic_constants.DEFAULT_GAME_ID)
            phase = self.config.get(
                "phase", "generate_communication"
            )  # Or use a more specific phase from state
            verbose_llm_debug = self.config.get("verbose_llm_debug", False)

            logger.debug(
                f"Agent {self.agent_id}: Calling LLM for communication generation. Model: {model_id}"
            )
            response_json = await self.llm_coordinator.call_json(
                prompt=prompt,
                model_id=model_id,
                agent_id=self.agent_id,
                game_id=game_id,
                phase=phase,
                system_prompt=system_prompt,
                verbose_llm_debug=verbose_llm_debug,
            )
            logger.info(f"Agent {self.agent_id}: Communication content generated: {response_json}")
            return response_json
        except Exception as e:
            logger.error(
                f"Agent {self.agent_id}: Error during generate_communication: {e}",
                exc_info=True,
            )
            return {
                "error": str(e),
                "details": "Failed to generate communication via LLM.",
            }

    async def update_internal_state(self, state: Any, events: List[Dict[str, Any]]) -> None:
        """
        Updates the agent's internal state based on recent events and current environment state.
        This is a placeholder and should be expanded based on specific agent needs.
        """
        logger.info(
            f"Agent {self.agent_id}: Updating internal state. Current env state: {state}, Events: {events}"
        )
        # Example: Store last seen state and events. More sophisticated logic would go here.
        self._internal_state["last_env_state"] = state
        self._internal_state["recent_events"] = events
        self._internal_state["last_updated"] = (
            logger.name
        )  # Using logger.name as a placeholder for a timestamp or version

        # Potentially, this method could also involve an LLM call to summarize or reflect on events
        # For example, using prompt_strategy.build_prompt(action_type='update_state_reflection', context=...)
        # and then calling llm_coordinator.call_text(...) to get a summary to store.
        pass

    def get_agent_info(self) -> Dict[str, Any]:
        """
        Retrieves information about the agent.
        """
        return {
            "agent_id": self.agent_id,
            "agent_class": self.__class__.__name__,
            "model_id": self.config.get("model_id", "N/A"),
            "prompt_strategy_class": self.prompt_strategy.__class__.__name__,
            "llm_coordinator_class": self.llm_coordinator.__class__.__name__,
            "internal_state_summary": {
                k: type(v).__name__ for k, v in self._internal_state.items()
            },  # Summary of state keys and types
        }
