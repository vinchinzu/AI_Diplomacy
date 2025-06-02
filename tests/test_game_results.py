import json
import os
from unittest.mock import MagicMock, mock_open, patch
from pathlib import Path  # Added import
import pytest  # Added import

from ai_diplomacy.game_results import GameResultsProcessor
from ai_diplomacy.game_history import GameHistory  # For creating mock GameHistory
from ai_diplomacy.game_config import GameConfig  # For mock GameConfig

# from diplomacy import Game # For type hinting mock_game if needed, but MagicMock is often sufficient


@pytest.mark.unit
def test_save_game_state_writes_history_json(tmp_path):  # Added tmp_path
    """
    Test that save_game_state calls game_history.to_dict() and writes its output to a JSON file.
    """
    # 1. Create Mock Objects
    mock_game_history = GameHistory()
    mock_game_history.add_phase("S1901M")
    phase1 = mock_game_history.get_phase_by_name("S1901M")
    assert phase1 is not None
    phase1.add_plan("FRANCE", "Test Plan S1901M")
    phase1.add_message("ENGLAND", "FRANCE", "Test Message S1901M")
    phase1.orders_by_power["ITALY"] = [
        "F ROM - NAP"
    ]  # Directly populating for simplicity
    phase1.results_by_power["ITALY"] = [["SUCCESSFUL"]]

    # Mock GameConfig
    # We need a GameConfig that provides paths.
    # Let's mock the args that GameConfig constructor expects.
    mock_cli_args = MagicMock()
    mock_cli_args.log_to_file = True
    mock_cli_args.game_id = "test_game_123"
    mock_cli_args.game_id_prefix = (
        "test_prefix"  # GameConfig uses this if game_id is None
    )
    mock_cli_args.log_dir = str(tmp_path)  # Changed to tmp_path
    # Add any other attributes GameConfig's __init__ might access from args
    mock_cli_args.power_name = None
    mock_cli_args.model_id = None
    mock_cli_args.num_players = 7
    mock_cli_args.log_level = "INFO"
    mock_cli_args.perform_planning_phase = False
    mock_cli_args.num_negotiation_rounds = 1
    mock_cli_args.negotiation_style = "simultaneous"
    mock_cli_args.fixed_models = None
    mock_cli_args.randomize_fixed_models = False
    mock_cli_args.exclude_powers = None
    mock_cli_args.max_years = None
    mock_cli_args.dev_mode = False
    mock_cli_args.verbose_llm_debug = False
    mock_cli_args.max_diary_tokens = 6500
    mock_cli_args.models_config_file = (
        "models.toml"  # So it doesn't try to load a real one and fail tests
    )

    # Patch os.path.exists for models.toml to avoid trying to load it
    with patch("os.path.exists", return_value=False):
        mock_game_config = GameConfig(mock_cli_args)

    # Ensure results_dir is set correctly for the test
    expected_results_dir = os.path.join(
        mock_game_config.game_id_specific_log_dir, "results"
    )
    mock_game_config.results_dir = (
        expected_results_dir  # Override if necessary, though GameConfig should set it
    )

    # Mock diplomacy.Game object
    mock_game_instance = MagicMock()
    # Set attributes on mock_game_instance that save_game_state might access
    # For saving game state JSON (to_saved_game_format part)
    mock_game_instance.is_game_done = True
    # Mock to_saved_game_format if it's complex or from external lib not easily mocked
    # For this test, we are focusing on the history part.
    # We can make to_saved_game_format return a simple string.

    # Instantiate GameResultsProcessor
    results_processor = GameResultsProcessor(mock_game_config)

    # Define expected file paths using tmp_path
    results_dir_path = Path(mock_game_config.results_dir)  # GameConfig sets this up
    expected_history_filepath = (
        results_dir_path / f"{mock_game_config.game_id}_game_history.json"
    )
    expected_final_state_filepath = (
        results_dir_path / f"{mock_game_config.game_id}_final_state.json"
    )

    # Mock to_saved_game_format specifically for the call within save_game_state
    # This patch can remain as its output is what's being written.
    with patch(
        "ai_diplomacy.game_results.to_saved_game_format",
        return_value='{"mock_game_state": "data"}',
    ):
        # Call save_game_state - this will now write to tmp_path
        results_processor.save_game_state(mock_game_instance, mock_game_history)

        # Assert that the files were created in tmp_path
        assert expected_history_filepath.is_file()
        assert expected_final_state_filepath.is_file()

        # Assert the content of the history file
        with open(expected_history_filepath, "r", encoding="utf-8") as f:
            written_data_dict = json.load(f)

        expected_history_dict = mock_game_history.to_dict()
        assert written_data_dict == expected_history_dict
        assert "phases" in written_data_dict
        assert len(written_data_dict["phases"]) == 1
        assert written_data_dict["phases"][0]["name"] == "S1901M"
        assert written_data_dict["phases"][0]["plans"]["FRANCE"] == "Test Plan S1901M"
        assert (
            written_data_dict["phases"][0]["messages"][0]["content"]
            == "Test Message S1901M"
        )
        assert written_data_dict["phases"][0]["orders_by_power"]["ITALY"] == [
            "F ROM - NAP"
        ]

        # Assert the content of the final state file
        with open(expected_final_state_filepath, "r", encoding="utf-8") as f:
            final_state_data = json.load(f)
        assert final_state_data == {"mock_game_state": "data"}

    # Test when log_to_file is False
    # @patch("os.makedirs") # No need to patch if it shouldn't be called
    @pytest.mark.unit
    @patch("builtins.open", new_callable=mock_open)
    def test_save_game_state_log_to_file_false(mock_file_open_disabled):
        mock_cli_args = MagicMock()
        mock_cli_args.log_to_file = False  # Key change for this test
        mock_cli_args.game_id = "test_game_no_log"
        # Fill other necessary args for GameConfig constructor
        mock_cli_args.game_id_prefix = "test_prefix"
        mock_cli_args.log_dir = "dummy_base_log_dir"
        mock_cli_args.power_name = None
        mock_cli_args.model_id = None
        mock_cli_args.num_players = 7
        mock_cli_args.log_level = "INFO"
        mock_cli_args.perform_planning_phase = False
        mock_cli_args.num_negotiation_rounds = 1
        mock_cli_args.negotiation_style = "simultaneous"
        mock_cli_args.fixed_models = None
        mock_cli_args.randomize_fixed_models = False
        mock_cli_args.exclude_powers = None
        mock_cli_args.max_years = None
        mock_cli_args.dev_mode = False
        mock_cli_args.verbose_llm_debug = False
        mock_cli_args.max_diary_tokens = 6500
        mock_cli_args.models_config_file = "models.toml"

        with patch("os.path.exists", return_value=False):  # For models.toml
            mock_game_config_no_log = GameConfig(mock_cli_args)

        mock_game_instance_no_log = MagicMock()
        mock_game_history_no_log = GameHistory()  # Empty history is fine

        results_processor_no_log = GameResultsProcessor(mock_game_config_no_log)
        results_processor_no_log.save_game_state(
            mock_game_instance_no_log, mock_game_history_no_log
        )

        mock_file_open_disabled.assert_not_called()  # open should not be called
        # os.makedirs might still be called by GameConfig if log_to_file=True,
        # but GameResultsProcessor.save_game_state should not proceed to file operations.
        # GameConfig's makedirs is conditional on self.log_to_file for game_id_specific_log_dir
        # so if log_to_file is false from the start, even GameConfig might not call it for that.
        # This specific test is for save_game_state's behavior.

    # Test for GameHistory having a to_dict method (positive check)
    @pytest.mark.unit
    def test_game_history_has_to_dict_method():
        gh = GameHistory()
        assert hasattr(gh, "to_dict")
        assert callable(gh.to_dict)

    # Test for GameHistory to_dict with multiple phases and complex data
    @pytest.mark.unit
    def test_game_history_to_dict_complex():
        gh = GameHistory()
        gh.add_phase("S1901M")
        p1 = gh.get_phase_by_name("S1901M")
        assert p1 is not None
        p1.add_plan("FRANCE", "Invade GER")
        p1.add_message("FRANCE", "GERMANY", "I'm friendly")
        p1.orders_by_power["FRANCE"] = ["A PAR - BUR"]
        p1.results_by_power["FRANCE"] = [["SUCCESSFUL"]]
        p1.phase_summaries["FRANCE"] = "French mobilization"
        p1.experience_updates["FRANCE"] = "Learned about BUR"

        gh.add_phase("F1901M")
        p2 = gh.get_phase_by_name("F1901M")
        assert p2 is not None
        p2.add_plan("GERMANY", "Defend RUH")
        p2.add_message("GERMANY", "FRANCE", "Oh really?")
        p2.orders_by_power["GERMANY"] = ["A MUN H"]
        p2.results_by_power["GERMANY"] = [["SUCCESSFUL"]]

        data = gh.to_dict()
        assert len(data["phases"]) == 2
        assert data["phases"][0]["name"] == "S1901M"
        assert data["phases"][0]["plans"]["FRANCE"] == "Invade GER"
        assert data["phases"][1]["name"] == "F1901M"
        assert data["phases"][1]["messages"][0]["content"] == "Oh really?"

        # Check JSON serializability
        json_data = json.dumps(data)
        reloaded_data = json.loads(json_data)
        assert data == reloaded_data
