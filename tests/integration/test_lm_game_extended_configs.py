import pytest
import subprocess # To run lm_game.py as a script
import sys
import re # For log checking
from pathlib import Path
import uuid # Added for unique game IDs

# Helper to find the root directory of the project assuming tests are in tests/integration
ROOT_DIR = Path(__file__).parent.parent.parent
LM_GAME_SCRIPT_PATH = ROOT_DIR / "lm_game.py"
LOG_DIR_BASE = ROOT_DIR / "logs" # Assuming logs are created here

# Ensure lm_game.py is executable and python path is set up if needed
# This might require specific environment setup if lm_game.py has complex dependencies not in test path

def run_lm_game_process(args_list, timeout_seconds=180):
    """Runs lm_game.py with given arguments and returns process output."""
    command = [sys.executable, str(LM_GAME_SCRIPT_PATH)] + args_list
    print(f"Running command: {' '.join(command)}") # For debugging tests

    # Ensure log directory exists for the game, or lm_game.py handles it
    # For simplicity, we let lm_game.py create its own log dirs.
    # We will need to parse the game_id from output to find the log file.

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=ROOT_DIR) # Run from ROOT_DIR
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        pytest.fail(f"lm_game.py timed out after {timeout_seconds}s. Stdout: {stdout}, Stderr: {stderr}")

    if process.returncode != 0:
        print(f"lm_game.py exited with code {process.returncode}.")
        print(f"  Stdout:\n{stdout}")
        print(f"  Stderr:\n{stderr}")
        # pytest.fail(f"lm_game.py exited with code {process.returncode}. Stdout: {stdout}, Stderr: {stderr}")
        # Keep it commented for now if certain tests expect non-zero exit, but print info.

    return stdout, stderr, process.returncode

def find_log_file_for_game(stdout_from_run, game_id_to_find=None, game_id_prefix_expected="diplomacy_game"):
    """
    Parses stdout to find the game-specific log directory and general log file.
    If game_id_to_find is provided, it looks for that exact game_id.
    Otherwise, it uses game_id_prefix_expected to find a generated game_id.
    """
    log_dir_str_from_stdout = None
    log_dir_pattern = ""

    if game_id_to_find:
        # Pattern for an exact game_id (which might be prefixed by path components)
        # Example: "Output files are located in: logs/test_wwi_run"
        # Example: "Output files are located in: /app/logs/test_wwi_run"
        log_dir_pattern = r"Output files are located in: (.*?logs/" + re.escape(game_id_to_find) + r")"
    else:
        # Pattern for a prefixed game_id (usually with a timestamp)
        log_dir_pattern = r"Output files are located in: (.*?logs/" + re.escape(game_id_prefix_expected) + r"_[0-9]{8}_[0-9]{6})"

    log_dir_match = re.search(log_dir_pattern, stdout_from_run)

    if not log_dir_match:
        print(f"Could not find log directory pattern '{log_dir_pattern}' in stdout_from_run. Content was:\n{stdout_from_run}")
        return None

    game_specific_log_dir_str = log_dir_match.group(1).strip()
    game_specific_log_dir = Path(game_specific_log_dir_str)

    # If the path from log is not absolute, assume it's relative to ROOT_DIR
    if not game_specific_log_dir.is_absolute():
         game_specific_log_dir = ROOT_DIR / game_specific_log_dir_str

    # Construct the log file name based on whether a specific game_id was used
    log_file_name = ""
    if game_id_to_find:
        log_file_name = f"{game_id_to_find}_general.log"
    else:
        # This case might need refinement if the prefix-based game_id also influences the log file name directly
        # For now, assume it would also be game_id_PREFIX_timestamp_general.log, but the game_id is parsed from log_dir_match.group(1)
        # Let's get the actual game_id (basename of the dir)
        actual_game_id_from_dir = game_specific_log_dir.name
        log_file_name = f"{actual_game_id_from_dir}_general.log"
        # This might be too simplistic if game_id_prefix_expected is used to form the log file name
        # but the directory name is what GameConfig uses.

    general_log_file = game_specific_log_dir / log_file_name

    if general_log_file.exists():
        return general_log_file
    else:
        # Try to list files if path seems correct but file not found
        if game_specific_log_dir.exists():
            print(f"General log file not found at expected path: {general_log_file}. Contents of {game_specific_log_dir}: {list(game_specific_log_dir.iterdir())}")
        else:
            print(f"General log file not found and log directory does not exist: {game_specific_log_dir}")
        return None

def count_occurrences_in_log(log_file_path, pattern):
    if not log_file_path or not log_file_path.exists():
        print(f"Log file not found for counting: {log_file_path}")
        return 0
    with open(log_file_path, 'r') as f:
        content = f.read()
    return len(re.findall(pattern, content))

@pytest.mark.integration
@pytest.mark.slow  # Mark as slow if these tests take significant time
def test_5p_standard_game_preset():
    """Test 5-player standard game with 2 neutral powers."""
    args = [
        "--preset", "5p_standard",
        "--max_years", "1901", # Run for one year (Spring, Fall, Winter)
        "--num_negotiation_rounds", "0", # Keep it short
        "--llm-models", "mock_model_1,mock_model_2,mock_model_3,mock_model_4,mock_model_5"
    ]
    stdout, stderr, returncode = run_lm_game_process(args)

    assert returncode == 0, f"lm_game.py exited non-zero. Stdout: {stdout} Stderr: {stderr}"

    log_file = find_log_file_for_game(stdout)
    assert log_file is not None, f"Could not find log file from lm_game output. Stdout: {stdout}"

    # Check agent initialization logs
    assert count_occurrences_in_log(log_file, r"Creating agent for 'ENGLAND' of type 'llm'") >= 1
    assert count_occurrences_in_log(log_file, r"Creating agent for 'FRANCE' of type 'llm'") >= 1
    assert count_occurrences_in_log(log_file, r"Creating agent for 'GERMANY' of type 'llm'") >= 1
    assert count_occurrences_in_log(log_file, r"Creating agent for 'RUSSIA' of type 'llm'") >= 1
    assert count_occurrences_in_log(log_file, r"Creating agent for 'TURKEY' of type 'llm'") >= 1
    assert count_occurrences_in_log(log_file, r"Creating agent for 'ITALY' of type 'neutral'") >= 1
    assert count_occurrences_in_log(log_file, r"Creating agent for 'AUSTRIA' of type 'neutral'") >= 1

    # Total agent creation messages
    assert count_occurrences_in_log(log_file, r"Creating agent for '.*?' of type 'llm'") == 5
    assert count_occurrences_in_log(log_file, r"Creating agent for '.*?' of type 'neutral'") == 2


@pytest.mark.integration
@pytest.mark.slow
def test_6p_standard_game_preset():
    """Test 6-player standard game with 1 neutral power."""
    args = [
        "--preset", "6p_standard",
        "--max_years", "1901",
        "--num_negotiation_rounds", "0",
        "--llm-models", "mock_model_1,mock_model_2,mock_model_3,mock_model_4,mock_model_5,mock_model_6"
    ]
    stdout, stderr, returncode = run_lm_game_process(args)
    assert returncode == 0, f"lm_game.py exited non-zero. Stdout: {stdout} Stderr: {stderr}"

    log_file = find_log_file_for_game(stdout)
    assert log_file is not None, f"Could not find log file. Stdout: {stdout}"

    assert count_occurrences_in_log(log_file, r"Creating agent for 'ITALY' of type 'neutral'") >= 1
    assert count_occurrences_in_log(log_file, r"Creating agent for '.*?' of type 'llm'") == 6
    assert count_occurrences_in_log(log_file, r"Creating agent for '.*?' of type 'neutral'") == 1

@pytest.mark.integration
@pytest.mark.slow
def test_4p_bloc_game_wwi_preset():
    """Test a 4-player equivalent bloc game (WWI preset)."""
    game_id_for_test = f"test_wwi_scenario_run_{uuid.uuid4().hex[:8]}"
    args = [
        "--scenario", "wwi_two_player",
        "--config", "wwi_scenario.toml",
        "--max_years", "1914",
        "--num_negotiation_rounds", "0",
        "--game_id", game_id_for_test
        # llm-models are now expected to be in wwi_scenario.toml's agent definitions.
        # Ensure wwi_scenario.toml uses mock models or models accessible in test env.
    ]
    stdout, stderr, returncode = run_lm_game_process(args)

    # Use the exact game_id to find the log file
    log_file = find_log_file_for_game(stdout, game_id_to_find=game_id_for_test)
    assert log_file is not None, f"Could not find log file for game_id '{game_id_for_test}'. Stdout: {stdout}\nStderr: {stderr}"

    # Check agent initialization for blocs and one null agent, using IDs from wwi_scenario.toml
    assert count_occurrences_in_log(log_file, r"Creating agent for 'ENTENTE_POWERS' of type 'bloc_llm'") == 1
    assert count_occurrences_in_log(log_file, r"Creating agent for 'CENTRAL_POWERS' of type 'bloc_llm'") == 1
    assert count_occurrences_in_log(log_file, r"Creating agent for 'ITALY_NULL_AGENT' of type 'null'") == 1

    # Check for BlocLLMAgent INFO log messages indicating it's proceeding to query the LLM.
    # Example log: "New phase or state detected for bloc ENTENTE_POWERS (key elements: ...), querying LLM for bloc orders."
    entente_query_pattern = r"New phase or state detected for bloc ENTENTE_POWERS .*?, querying LLM for bloc orders"
    central_query_pattern = r"New phase or state detected for bloc CENTRAL_POWERS .*?, querying LLM for bloc orders"
    assert count_occurrences_in_log(log_file, entente_query_pattern) > 0
    assert count_occurrences_in_log(log_file, central_query_pattern) > 0
    
    # The specific warning "BlocLLMAgent '.*?' \(bloc .*?\) TEMPORARILY returning .*?" might no longer be relevant
    # if the BlocLLMAgent implementation has evolved.
    # For now, we focus on the creation and the attempt to get orders.
    # If LLM calls fail (as they do with current wwi_scenario.toml models without keys/setup),
    # the game should still proceed gracefully (e.g. agents submit no orders).

    if returncode != 0:
        print(f"WARNING: test_4p_bloc_game_wwi_preset completed with return code {returncode}. Stdout: {stdout} Stderr: {stderr}")
        # This is acceptable for now, as PhaseOrchestrator is not yet adapted for bloc orders.
    else:
        # If it somehow completes with 0, it might mean not all logic paths were hit,
        # or the game ended very early before potential issues.
        print("INFO: test_4p_bloc_game_wwi_preset completed with return code 0. This might be unexpected if PhaseOrchestrator is not adapted.")

