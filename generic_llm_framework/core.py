from typing import Any, List, Dict


class GenericLLMAgentInterface:
    """
    Interface for a generic LLM agent.
    """

    async def decide_action(self, state: Any, possible_actions: Any) -> Any:
        """
        Decides the next action to take based on the current state and possible actions.

        Args:
            state: The current state of the environment.
            possible_actions: A list or description of possible actions.

        Returns:
            The decided action.
        """
        raise NotImplementedError

    async def generate_communication(self, state: Any, recipients: Any) -> Any:
        """
        Generates communication content for specified recipients.

        Args:
            state: The current state of the environment.
            recipients: Information about the recipients of the communication.

        Returns:
            The generated communication content.
        """
        raise NotImplementedError

    async def update_internal_state(self, state: Any, events: List[Dict[str, Any]]) -> None:
        """
        Updates the agent's internal state based on recent events.

        Args:
            state: The current state of the environment.
            events: A list of events that have occurred.
        """
        raise NotImplementedError

    def get_agent_info(self) -> Dict[str, Any]:
        """
        Retrieves information about the agent.

        Returns:
            A dictionary containing agent information.
        """
        raise NotImplementedError
