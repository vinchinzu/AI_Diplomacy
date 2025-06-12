"""
Provides a stub for the LLMCoordinator for testing purposes.
"""

from unittest.mock import AsyncMock, MagicMock
from typing import Any, Dict, Optional, List
import json

from generic_llm_framework.llm_coordinator import LLMCallResult


def create_llm_stub(
    text_response: Optional[str] = "Default text response",
    json_response: Optional[Dict[str, Any]] = None,
    expected_json_fields: Optional[List[str]] = None,
) -> MagicMock:
    """
    Creates a mock LLMCoordinator with pre-canned responses.

    Args:
        text_response: The string to return from `call_text`.
        json_response: The dict to return from `call_llm_with_json_parsing`.
                       If not provided, a default is used.
        expected_json_fields: A list of fields to validate in the JSON response.
                              This is used by the real `call_llm_with_json_parsing`.

    Returns:
        A MagicMock instance configured to simulate LLMCoordinator.
    """
    mock_coordinator = MagicMock()
    mock_coordinator.call_text = AsyncMock(return_value=text_response)

    # Prepare the JSON response for call_llm_with_json_parsing
    if json_response is None:
        json_response = {"analysis": "Default analysis", "orders": ["HOLD"]}

    # The call_llm_with_json_parsing method returns an LLMCallResult object
    mock_json_result = LLMCallResult(
        raw_response=json.dumps(json_response),
        parsed_json=json_response,
        success=True,
        error_message="",
    )

    # If expected_json_fields is provided, mock a check for missing fields
    if expected_json_fields:
        missing_fields = [field for field in expected_json_fields if field not in json_response]
        if missing_fields:
            mock_json_result.success = False
            mock_json_result.error_message = f"Missing expected fields: {missing_fields}"

    mock_coordinator.call_llm_with_json_parsing = AsyncMock(return_value=mock_json_result)

    return mock_coordinator
