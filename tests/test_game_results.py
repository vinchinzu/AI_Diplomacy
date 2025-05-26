import json
import os
from unittest.mock import MagicMock, mock_open, patch

from ai_diplomacy.game_results import GameResultsProcessor
from ai_diplomacy.game_history import GameHistory, Phase, Message # For creating mock GameHistory
from ai_diplomacy.game_config import GameConfig # For mock GameConfig
# from diplomacy import Game # For type hinting mock_game if needed, but MagicMock is often sufficient

def test_save_game_state_writes_history_json():
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
    phase1.orders_by_power["ITALY"] = ["F ROM - NAP"] # Directly populating for simplicity
    phase1.results_by_power["ITALY"] = [["SUCCESSFUL"]]


    # Mock GameConfig
    # We need a GameConfig that provides paths.
    # Let's mock the args that GameConfig constructor expects.
    mock_cli_args = MagicMock()
    mock_cli_args.log_to_file = True
    mock_cli_args.game_id = "test_game_123"
    mock_cli_args.game_id_prefix = "test_prefix" # GameConfig uses this if game_id is None
    mock_cli_args.log_dir = "dummy_base_log_dir" # GameConfig will create subdirs here
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
    mock_cli_args.models_config_file = "models.toml" # So it doesn't try to load a real one and fail tests

    # Patch os.path.exists for models.toml to avoid trying to load it
    with patch('os.path.exists', return_value=False):
        mock_game_config = GameConfig(mock_cli_args)
    
    # Ensure results_dir is set correctly for the test
    expected_results_dir = os.path.join(mock_game_config.game_id_specific_log_dir, "results")
    mock_game_config.results_dir = expected_results_dir # Override if necessary, though GameConfig should set it

    # Mock diplomacy.Game object
    mock_game_instance = MagicMock()
    # Set attributes on mock_game_instance that save_game_state might access
    # For saving game state JSON (to_saved_game_format part)
    mock_game_instance.is_game_done = True 
    # Mock to_saved_game_format if it's complex or from external lib not easily mocked
    # For this test, we are focusing on the history part.
    # We can make to_saved_game_format return a simple string.

    # 2. Patch builtins.open and os.makedirs
    with patch("builtins.open", new_callable=mock_open) as mock_file_open, \
         patch("os.makedirs") as mock_makedirs: # os.makedirs is called by GameConfig and GameResultsProcessor

        # Instantiate GameResultsProcessor
        results_processor = GameResultsProcessor(mock_game_config)
        
        # Mock to_saved_game_format specifically for the call within save_game_state
        with patch("ai_diplomacy.game_results.to_saved_game_format", return_value='{"mock_game_state": "data"}') as mock_to_saved_format:

            # 3. Call save_game_state
            results_processor.save_game_state(mock_game_instance, mock_game_history)

            # 4. Assert os.makedirs was called (by GameConfig and potentially by save_game_state)
            # GameConfig creates results_dir if log_to_file is True
            mock_makedirs.assert_any_call(expected_results_dir, exist_ok=True)

            # 5. Assert open was called for the history JSON file
            # Expected path: os.path.join(mock_game_config.results_dir, f"{mock_game_config.game_id}_game_history.json")
            expected_history_filepath = os.path.join(expected_results_dir, f"{mock_game_config.game_id}_game_history.json")
            
            # Check if open was called for the history file
            # It's also called for the final_state.json, so we look for the specific call
            found_history_file_call = False
            final_state_filepath = os.path.join(expected_results_dir, f"{mock_game_config.game_id}_final_state.json")

            for call_args in mock_file_open.call_args_list:
                if call_args[0][0] == expected_history_filepath:
                    assert call_args[0][1] == "w" # Mode 'w'
                    assert call_args[1]['encoding'] == "utf-8"
                    found_history_file_call = True
                    break
            assert found_history_file_call, f"History file {expected_history_filepath} was not opened."

            # 6. Assert json.dump or write content for the history file
            # Find the write call associated with the history file
            # This assumes json.dump uses the write method of the file handle from open()
            
            # Get the file handle that was used for the history file
            history_file_handle_write_calls = None
            for call in mock_file_open.call_args_list:
                if call[0][0] == expected_history_filepath:
                    # The mock_open().write calls are on the instance returned by mock_file_open()
                    # when it was called for the history file.
                    # We need to find which mock_file_open() instance corresponds to the history file.
                    # This is tricky if multiple files are opened.
                    # A simpler way is to check the content passed to json.dump if we patch json.dump
                    break # Found the open call, now need its handle's write calls.
            
            # Instead of inspecting mock_file_open's write calls directly (which can be complex
            # if multiple files are opened), we can patch json.dump for more direct assertion.
            
            # Re-run with json.dump patched
            with patch("json.dump") as mock_json_dump:
                # Re-call the function under test now that json.dump is patched
                # Need to reset mock_file_open if it's stateful across calls
                mock_file_open.reset_mock() 
                
                # We need a fresh GameResultsProcessor or ensure state is clean if it's stateful
                # results_processor = GameResultsProcessor(mock_game_config) # Re-instantiate if needed
                
                with patch("ai_diplomacy.game_results.to_saved_game_format", return_value='{"mock_game_state": "data"}'):
                    results_processor.save_game_state(mock_game_instance, mock_game_history)

                # Find the call to json.dump that wrote the history data
                history_dump_call_args = None
                for call in mock_json_dump.call_args_list:
                    # The first argument to json.dump is the data, the second is the file handle
                    # We expect the data to be the dictionary from game_history.to_dict()
                    dumped_data = call[0][0]
                    if "phases" in dumped_data and dumped_data["phases"][0]["name"] == "S1901M":
                        history_dump_call_args = call
                        break
                
                assert history_dump_call_args is not None, "json.dump was not called with history data."
                
                written_data_dict = history_dump_call_args[0][0]
                
                # Assert content based on mock_game_history.to_dict()
                expected_history_dict = mock_game_history.to_dict()
                assert written_data_dict == expected_history_dict
                assert "phases" in written_data_dict
                assert len(written_data_dict["phases"]) == 1
                assert written_data_dict["phases"][0]["name"] == "S1901M"
                assert written_data_dict["phases"][0]["plans"]["FRANCE"] == "Test Plan S1901M"
                assert written_data_dict["phases"][0]["messages"][0]["content"] == "Test Message S1901M"
                assert written_data_dict["phases"][0]["orders_by_power"]["ITALY"] == ["F ROM - NAP"]

    # Test when log_to_file is False
    # @patch("os.makedirs") # No need to patch if it shouldn't be called
    @patch("builtins.open", new_callable=mock_open)
    def test_save_game_state_log_to_file_false(mock_file_open_disabled):
        mock_cli_args = MagicMock()
        mock_cli_args.log_to_file = False # Key change for this test
        mock_cli_args.game_id = "test_game_no_log"
        # Fill other necessary args for GameConfig constructor
        mock_cli_args.game_id_prefix = "test_prefix"
        mock_cli_args.log_dir = "dummy_base_log_dir"
        mock_cli_args.power_name = None; mock_cli_args.model_id = None; mock_cli_args.num_players = 7
        mock_cli_args.log_level = "INFO"; mock_cli_args.perform_planning_phase = False
        mock_cli_args.num_negotiation_rounds = 1; mock_cli_args.negotiation_style = "simultaneous"
        mock_cli_args.fixed_models = None; mock_cli_args.randomize_fixed_models = False
        mock_cli_args.exclude_powers = None; mock_cli_args.max_years = None
        mock_cli_args.dev_mode = False; mock_cli_args.verbose_llm_debug = False
        mock_cli_args.max_diary_tokens = 6500; mock_cli_args.models_config_file = "models.toml"

        with patch('os.path.exists', return_value=False): # For models.toml
            mock_game_config_no_log = GameConfig(mock_cli_args)

        mock_game_instance_no_log = MagicMock()
        mock_game_history_no_log = GameHistory() # Empty history is fine

        results_processor_no_log = GameResultsProcessor(mock_game_config_no_log)
        results_processor_no_log.save_game_state(mock_game_instance_no_log, mock_game_history_no_log)

        mock_file_open_disabled.assert_not_called() # open should not be called
        # os.makedirs might still be called by GameConfig if log_to_file=True,
        # but GameResultsProcessor.save_game_state should not proceed to file operations.
        # GameConfig's makedirs is conditional on self.log_to_file for game_id_specific_log_dir
        # so if log_to_file is false from the start, even GameConfig might not call it for that.
        # This specific test is for save_game_state's behavior.

    # Test for GameHistory having a to_dict method (positive check)
    def test_game_history_has_to_dict_method():
        gh = GameHistory()
        assert hasattr(gh, 'to_dict')
        assert callable(gh.to_dict)

    # Test for GameHistory to_dict with multiple phases and complex data
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
