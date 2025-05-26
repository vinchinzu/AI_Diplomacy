import pytest # For fixtures like tmp_path
import os
import logging
import json
from ai_diplomacy import llm_utils # Import the module to be tested

# Setup a simple logger for tests that require one
test_logger = logging.getLogger("test_llm_utils")
test_logger.setLevel(logging.DEBUG)
# If you want to see log output during pytest runs, you might need to configure pytest
# or add a handler, e.g., logging.StreamHandler(). For now, this is minimal.

ALL_POWERS = {"AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"}
ALLOWED_RELATIONSHIPS = ["Enemy", "Unfriendly", "Neutral", "Friendly", "Ally"]


def test_load_prompt_file(tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    dummy_prompt_file = prompts_dir / "test_prompt.txt"
    dummy_prompt_content = "This is a test prompt."
    dummy_prompt_file.write_text(dummy_prompt_content)

    # Test loading an existing file
    content = llm_utils.load_prompt_file('test_prompt.txt', base_prompts_dir=str(tmp_path))
    assert content == dummy_prompt_content

    # Test loading a non-existent file
    non_existent_content = llm_utils.load_prompt_file('non_existent_prompt.txt', base_prompts_dir=str(tmp_path))
    assert non_existent_content is None

    # Test loading when base_prompts_dir is not provided (should look relative to llm_utils.py, will likely fail to find 'test_prompt.txt')
    # This tests the default path logic, expecting None as tmp_path won't be its default search location.
    # We can't easily create a file in the expected default location (ai_diplomacy/prompts) from here
    # without making assumptions about the test execution directory relative to the project root.
    # So, we test that it returns None for a file it definitely won't find in its default path.
    content_default_path_non_existent = llm_utils.load_prompt_file('some_random_non_existent_prompt_123.txt')
    assert content_default_path_non_existent is None


def test_extract_json_basic():
    json_string = 'Plain JSON: {"name": "Test", "items": [1, 2, "three"]}'
    expected = {"name": "Test", "items": [1, 2, "three"]}
    assert llm_utils.extract_json_from_text(json_string, test_logger, '[TestBasic]') == expected

def test_extract_json_with_markdown_fences():
    json_string = 'Some text before ```json\n{\n  "key": "value",\n  "number": 123\n}\n``` and after.'
    expected = {"key": "value", "number": 123}
    assert llm_utils.extract_json_from_text(json_string, test_logger, '[TestMarkdown]') == expected

    json_string_no_type = 'Some text before ```\n{\n  "key2": "value2",\n  "number2": 456\n}\n``` and after.'
    expected2 = {"key2": "value2", "number2": 456}
    #This specific pattern "```\n(JSON)\n```" is not explicitly handled by default in extract_json_from_text
    #It is "```(?:json)?\s*\n(.*?)\n\s*```"
    #The provided string "```\n{...}\n```" should match (?:json)? as optional, and \s*\n should match the newline.
    assert llm_utils.extract_json_from_text(json_string_no_type, test_logger, '[TestMarkdownNoType]') == expected2


def test_extract_json_malformed_trailing_comma():
    # Note: json_repair or json5 might handle this, so the original clean_json_text might not even be hit for this.
    # The goal is that *something* parses it correctly.
    json_string = 'Malformed: {"foo": "bar",}'
    expected = {"foo": "bar"}
    # Depending on which parser (json, json5, json_repair) handles it, logging might differ.
    # json.loads would fail, but json_repair or json5 should pass.
    assert llm_utils.extract_json_from_text(json_string, test_logger, '[TestTrailingComma]') == expected

def test_extract_json_double_braces():
    # This pattern "```{{ ... }}```" was in the original inline test,
    # but extract_json_from_text has r"```\s*\{\{\s*(.*?)\s*\}\}\s*```" which is looking for {{ and }}
    # It seems the example string was intended to be ````{{ "example": "double_brace_json" }}````
    # but the actual string used in the inline test was "Text with ```{{ \"example\": \"double_brace_json\" }}```"
    # which has extra quotes. Let's test the pattern it seems to be designed for.
    json_string = "Text with ```{{ \"example\": \"double_brace_json\" }}```" # Original inline test string
    expected = {"example": "double_brace_json"}
    # The regex is r"```\s*\{\{\s*(.*?)\s*\}\}\s*```" - this implies the JSON content is *inside* the {{ }}
    # So, the string should ideally be ```{{ {"example": "value"} }}```
    # Let's test the original string and see. The regex might be too greedy or not match as expected.
    # The regex `r"```\s*\{\{\s*(.*?)\s*\}\}\s*```"` expects the JSON part to be *inside* the double braces.
    # The string "Text with ```{{ \"example\": \"double_brace_json\" }}```" won't be parsed by this regex
    # because ` \"example\": \"double_brace_json\" ` is not valid JSON by itself.
    # It's more likely that the original intent was to extract JSON *wrapped* in those markers.
    # The current patterns in `extract_json_from_text` might parse this using a more general pattern if the specific one fails.
    # The most general regex r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})" might pick up `{"example": "double_brace_json"}`
    # if the `{{` and `}}` are stripped by context or another pattern.
    # Given the current patterns, this specific string is more likely to be caught by the general fallback
    # r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})" if the outer markers are ignored or not matched by stricter patterns.
    # Let's test what the current implementation does:
    result = llm_utils.extract_json_from_text(json_string, test_logger, '[TestDoubleBraceOriginal]')
    # Based on the function's logic, it's likely the general pattern `r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})"`
    # would pick out `{"example": "double_brace_json"}` if the `{{` and `}}` are handled as non-JSON parts.
    # The most robust interpretation is that the content *inside* {{ and }} should be JSON.
    # If the string was: ```{{ {"example": "double_brace_json"} }}```
    # then the regex `r"```\s*\{\{\s*(.*?)\s*\}\}\s*```"` would extract `{"example": "double_brace_json"}`
    
    # Re-evaluating the original test string: "Text with ```{{ \"example\": \"double_brace_json\" }}```"
    # The pattern `r"```\s*\{\{\s*(.*?)\s*\}\}\s*```"` will attempt to match.
    # `(.*?)` will capture ` \"example\": \"double_brace_json\" `. This is NOT valid JSON.
    # So this specific pattern will fail to parse.
    # The code will then try other patterns.
    # The pattern `r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})"` would find `{\"example\": \"double_brace_json\"}`. This IS valid JSON.
    # So, the test should pass.
    assert result == expected

    # A more direct test for the double brace pattern:
    json_string_direct = "```{{ {\"direct_example\": \"value\"} }}```"
    expected_direct = {"direct_example": "value"}
    assert llm_utils.extract_json_from_text(json_string_direct, test_logger, '[TestDoubleBraceDirect]') == expected_direct


def test_extract_json_empty_string():
    assert llm_utils.extract_json_from_text("", test_logger, '[TestEmpty]') == {}

def test_extract_json_non_json_string():
    assert llm_utils.extract_json_from_text("This is just a regular sentence.", test_logger, '[TestNonJSON]') == {}

def test_extract_json_with_escaped_quotes_in_values():
    # Test case from the original clean_json_text, implies it should be handled.
    json_string = '{"problem": "He said \\"this is fine\\" to me"}' # Valid JSON
    expected = {"problem": "He said \"this is fine\" to me"}
    assert llm_utils.extract_json_from_text(json_string, test_logger, '[TestEscapedQuotes]') == expected

    # Test for the risky fix: re.sub(r':\s*"([^"]*)"([^",}\]]+)"', r': "\1\2"', text)
    # This regex seems to intend to fix unescaped quotes *within* a value if followed by more text not comma or brace.
    # Example: {"value": "text "unescaped" text"}
    # The regex r':\s*"([^"]*)"([^",}\]]+)"'
    # For '{"key": "value "unescaped" string"}'
    # It would match: 'key": "value "' as group 1, and 'unescaped"' as group 2.
    # This would result in: 'key": "value unescaped"' which is still broken.
    # The original clean_json_text's regex for this is:
    # text = re.sub(r':\s*"([^"]*)"([^",}\]]+)"', r': "\1\2"', text)
    # This is very specific. Let's try an example it might fix.
    # If the LLM produced: {"error": "This is "badly" quoted"}
    # The regex would find `": "This is "` as \1, and `"badly"` as \2 (because `"` is not in `[^",}\]]`)
    # The replacement would be `": "This is "badly""` - this is still not quite right.
    # This specific regex in clean_json_text is probably too fragile to test reliably without knowing the exact LLM failure modes it targets.
    # Most robust JSON extractors (json_repair) should handle common issues better.
    # For now, we'll rely on json_repair for complex non-standard quoting.
    pass


def test_extract_relationships_valid():
    data_updated = {"updated_relationships": {"FRANCE": "Ally", "GERMANY": "Neutral"}}
    data_regular = {"relationships": {"ITALY": "Enemy"}}
    data_updates = {"relationship_updates": {"RUSSIA": "Friendly"}}
    
    assert llm_utils.extract_relationships(data_updated) == {"FRANCE": "Ally", "GERMANY": "Neutral"}
    assert llm_utils.extract_relationships(data_regular) == {"ITALY": "Enemy"}
    assert llm_utils.extract_relationships(data_updates) == {"RUSSIA": "Friendly"}

def test_extract_relationships_invalid_or_missing():
    assert llm_utils.extract_relationships({}) is None # Empty dict
    assert llm_utils.extract_relationships({"foo": "bar"}) is None # Wrong keys
    assert llm_utils.extract_relationships({"updated_relationships": "not a dict"}) is None # Wrong type
    assert llm_utils.extract_relationships(None) is None # Input is None
    assert llm_utils.extract_relationships("string input") is None # Input is not a dict

def test_extract_goals_valid():
    data_updated = {"updated_goals": ["Goal 1", "Goal 2"]}
    data_regular = {"goals": ["Survive", "Expand"]}
    data_updates = {"goal_updates": ["Form alliance with X"]}
    
    assert llm_utils.extract_goals(data_updated) == ["Goal 1", "Goal 2"]
    assert llm_utils.extract_goals(data_regular) == ["Survive", "Expand"]
    assert llm_utils.extract_goals(data_updates) == ["Form alliance with X"]

def test_extract_goals_invalid_or_missing():
    assert llm_utils.extract_goals({}) is None # Empty dict
    assert llm_utils.extract_goals({"foo": "bar"}) is None # Wrong keys
    assert llm_utils.extract_goals({"updated_goals": "not a list"}) is None # Wrong type
    assert llm_utils.extract_goals(None) is None # Input is None
    assert llm_utils.extract_goals("string input") is None # Input is not a dict


def test_clean_json_text_trailing_commas():
    assert llm_utils.clean_json_text('{"foo": "bar",}') == '{"foo": "bar"}'
    assert llm_utils.clean_json_text('{"foo": ["bar", "baz"],}') == '{"foo": ["bar", "baz"]}'

def test_clean_json_text_newlines_before_keys():
    # Original: text = re.sub(r'\n\s+"(\w+)"\s*:', r'"\1":', text)
    # This regex is quite specific. It looks for a newline, optional space, then a quoted word key.
    # Example: {\n  "key": "value"} -> {"key": "value"}
    assert llm_utils.clean_json_text('{\n  "key": "value"}') == '{"key": "value"}'
    
    # Test from extract_json_from_text's preprocessing, which is similar:
    # text = re.sub(fr'\n\s*"{pattern}"', f'"{pattern}"', text)
    # This seems to be about specific known keys.
    # The one in clean_json_text is more general.
    # Let's ensure it doesn't break valid JSON.
    assert llm_utils.clean_json_text('{"key1": "value1", "key2": "value2"}') == '{"key1": "value1", "key2": "value2"}'


def test_clean_json_text_single_to_double_quotes_keys():
    # text = re.sub(r"'(\w+)'\s*:", r'"\1":', text)
    assert llm_utils.clean_json_text("{'key': 'value', 'another_key': 123}") == '{"key": "value", "another_key": 123}'
    # Should not affect values
    assert llm_utils.clean_json_text('{"key": "val\'ue"}') == '{"key": "val\'ue"}'

def test_clean_json_text_comments():
    json_with_comments = """
    {
        // This is a key
        "key": "value", // EOL comment
        "another": /* block comment */ "value2" 
    }
    """
    expected = '{\n        "key": "value", \n        "another":  "value2" \n    }' # Exact spacing might vary
    cleaned = llm_utils.clean_json_text(json_with_comments)
    # We'll parse and compare as dicts to avoid issues with whitespace.
    assert json.loads(cleaned) == {"key": "value", "another": "value2"}

def test_clean_json_text_bom_zerowidth():
    assert llm_utils.clean_json_text('\ufeff{"key": "value"}\u200b') == '{"key": "value"}'

# More tests for clean_json_text could be added if specific LLM failure modes are identified.
# The "unescaped quotes in values" part of clean_json_text is noted as risky and its regex seems problematic.
# It's better to rely on robust parsers like json_repair for such complex cases.
# So, no specific test for that part of clean_json_text will be added for now.

# (Constants ALL_POWERS and ALLOWED_RELATIONSHIPS are defined at the top but not directly used by llm_utils functions)
