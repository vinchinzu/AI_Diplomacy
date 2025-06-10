import pytest
from unittest.mock import MagicMock, patch
from generic_llm_framework.prompt_strategy import BasePromptStrategy
from generic_llm_framework.llm_utils import load_prompt_file # To mock its path

class TestBasePromptStrategy:
    def test_init_defaults(self):
        """Test BasePromptStrategy initialization with default config."""
        with patch('generic_llm_framework.prompt_strategy.llm_utils.load_prompt_file') as mock_load_prompt:
            mock_load_prompt.return_value = "Default system prompt content"
            strategy = BasePromptStrategy()
            assert strategy.config == {}
            assert strategy.base_prompts_dir is None
            assert strategy.system_prompt_template == "Default system prompt content"
            mock_load_prompt.assert_called_once_with("generic_system_prompt.txt", base_prompts_dir=None)

    def test_init_with_config_and_dir(self):
        """Test BasePromptStrategy initialization with specific config and base_prompts_dir."""
        mock_config = {"system_prompt_filename": "custom_prompt.txt", "some_key": "some_value"}
        mock_base_dir = "/test/prompts"
        with patch('generic_llm_framework.prompt_strategy.llm_utils.load_prompt_file') as mock_load_prompt:
            mock_load_prompt.return_value = "Custom system prompt"
            strategy = BasePromptStrategy(config=mock_config, base_prompts_dir=mock_base_dir)
            assert strategy.config == mock_config
            assert strategy.base_prompts_dir == mock_base_dir
            assert strategy.system_prompt_template == "Custom system prompt"
            mock_load_prompt.assert_called_once_with("custom_prompt.txt", base_prompts_dir=mock_base_dir)

    def test_build_prompt_raises_not_implemented_error(self):
        """Test that build_prompt raises NotImplementedError."""
        strategy = BasePromptStrategy()
        with pytest.raises(NotImplementedError, match="Subclasses must implement build_prompt."):
            strategy.build_prompt(action_type="any_action", context={})

    def test_load_generic_system_prompt_success(self):
        """Test _load_generic_system_prompt successfully loads a prompt."""
        strategy = BasePromptStrategy() # __init__ calls it
        with patch('generic_llm_framework.prompt_strategy.llm_utils.load_prompt_file') as mock_load_prompt:
            mock_load_prompt.return_value = "Test system prompt from file"
            # Call directly to test isolated behavior, though __init__ already calls it
            loaded_prompt = strategy._load_generic_system_prompt()
            assert loaded_prompt == "Test system prompt from file"
            # Called by __init__ and then by our direct call
            assert mock_load_prompt.call_count >= 1
            mock_load_prompt.assert_any_call("generic_system_prompt.txt", base_prompts_dir=None)


    def test_load_generic_system_prompt_file_not_found_uses_default(self):
        """Test _load_generic_system_prompt uses default when file not found."""
        strategy = BasePromptStrategy() # __init__ calls it
        with patch('generic_llm_framework.prompt_strategy.llm_utils.load_prompt_file') as mock_load_prompt:
            mock_load_prompt.return_value = None # Simulate file not found
            # Call directly
            loaded_prompt = strategy._load_generic_system_prompt()
            assert loaded_prompt == "You are a helpful AI assistant."
            assert mock_load_prompt.call_count >= 1
            mock_load_prompt.assert_any_call("generic_system_prompt.txt", base_prompts_dir=None)


    def test_get_formatted_system_prompt_success(self):
        """Test _get_formatted_system_prompt successfully formats."""
        strategy = BasePromptStrategy()
        strategy.system_prompt_template = "Hello {name}, welcome to {place}."
        formatted = strategy._get_formatted_system_prompt(name="Tester", place="Testville")
        assert formatted == "Hello Tester, welcome to Testville."

    def test_get_formatted_system_prompt_missing_key(self, caplog):
        """Test _get_formatted_system_prompt handles missing keys gracefully."""
        strategy = BasePromptStrategy()
        raw_template = "Hello {name}, your ID is {id}."
        strategy.system_prompt_template = raw_template

        formatted = strategy._get_formatted_system_prompt(name="Tester") # 'id' is missing
        assert formatted == raw_template # Should return raw template
        assert "Missing key in system prompt formatting: 'id'" in caplog.text

    def test_get_formatted_system_prompt_unexpected_error(self, caplog):
        """Test _get_formatted_system_prompt handles unexpected formatting errors."""
        strategy = BasePromptStrategy()
        # Malformed template
        raw_template = "Hello {name, welcome."
        strategy.system_prompt_template = raw_template

        formatted = strategy._get_formatted_system_prompt(name="Tester")
        assert formatted == raw_template # Should return raw template
        assert "Error formatting system prompt:" in caplog.text

    def test_init_load_prompt_filename_from_config(self):
        """Test that system_prompt_filename from config is used by _load_generic_system_prompt."""
        config = {"system_prompt_filename": "my_special_prompt.txt"}
        with patch('generic_llm_framework.prompt_strategy.llm_utils.load_prompt_file') as mock_load_prompt:
            mock_load_prompt.return_value = "Special prompt content"
            strategy = BasePromptStrategy(config=config)
            assert strategy.system_prompt_template == "Special prompt content"
            mock_load_prompt.assert_called_once_with("my_special_prompt.txt", base_prompts_dir=None)

    def test_init_base_prompts_dir_passed_to_load(self):
        """Test that base_prompts_dir is passed to load_prompt_file."""
        my_dir = "/custom/prompts/"
        with patch('generic_llm_framework.prompt_strategy.llm_utils.load_prompt_file') as mock_load_prompt:
            mock_load_prompt.return_value = "Prompt from custom dir"
            strategy = BasePromptStrategy(base_prompts_dir=my_dir)
            assert strategy.system_prompt_template == "Prompt from custom dir"
            mock_load_prompt.assert_called_once_with("generic_system_prompt.txt", base_prompts_dir=my_dir)

    def test_init_config_and_base_dir_passed_to_load(self):
        """Test config's filename and base_prompts_dir are both passed to load_prompt_file."""
        config = {"system_prompt_filename": "specific_prompt.txt"}
        my_dir = "/another/dir/"
        with patch('generic_llm_framework.prompt_strategy.llm_utils.load_prompt_file') as mock_load_prompt:
            mock_load_prompt.return_value = "Specific prompt from another dir"
            strategy = BasePromptStrategy(config=config, base_prompts_dir=my_dir)
            assert strategy.system_prompt_template == "Specific prompt from another dir"
            mock_load_prompt.assert_called_once_with("specific_prompt.txt", base_prompts_dir=my_dir)

    # Example of how DiplomacyPromptStrategy might be tested (subset of tests)
    # This would ideally be in its own test file if it grows complex, or if it were truly standalone.
    # For now, as it's closely related and part of the same file, a small test here is okay.
    # from generic_llm_framework.prompt_strategy import DiplomacyPromptStrategy
    # def test_diplomacy_prompt_strategy_build_prompt_dispatch(self):
    #     # This is a conceptual test. DiplomacyPromptStrategy's build_prompt
    #     # internally calls other methods. We'd mock those if testing in isolation.
    #     # For now, this just shows where such tests would go.
    #     # strategy = DiplomacyPromptStrategy()
    #     # with pytest.raises(ValueError): # e.g. if action_type is unknown
    #     #     strategy.build_prompt("unknown_diplomacy_action", {})
    #     pass

pytest_plugins = ['pytester'] # For caplog
