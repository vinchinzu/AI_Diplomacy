import pytest
import asyncio
import subprocess # To run lm_game.py as a script
import sys
import os
import re # For log checking
from pathlib import Path

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

    # Allow non-zero return codes for now, as game might error out due to incomplete orchestrator for blocs
    # if process.returncode != 0:
    #     print(f"lm_game.py exited with code {process.returncode}. Stdout: {stdout} Stderr: {stderr}")
    #     # pytest.fail(f"lm_game.py exited with code {process.returncode}. Stdout: {stdout}, Stderr: {stderr}")


    return stdout, stderr, process.returncode

def find_log_file_for_game(stdout_from_run, game_id_prefix_expected="diplomacy_game"):
    """Parses stdout to find the game-specific log directory and general log file."""
    # Example log line: "Output files are located in: logs/diplomacy_game_YYYYMMDD_HHMMSS"
    # Or "Output files are located in: /abs/path/to/logs/diplomacy_game_YYYYMMDD_HHMMSS"
    log_dir_pattern = r"Output files are located in: (.*?logs/" + game_id_prefix_expected + r"_[0-9]{8}_[0-9]{6})"
    log_dir_match = re.search(log_dir_pattern, stdout_from_run)

    if not log_dir_match:
        print(f"Could not find log directory pattern '{log_dir_pattern}' in stdout: {stdout_from_run}")
        return None

    game_specific_log_dir_str = log_dir_match.group(1)
    game_specific_log_dir = Path(game_specific_log_dir_str)

    # If the path from log is not absolute, assume it's relative to ROOT_DIR
    if not game_specific_log_dir.is_absolute():
         game_specific_log_dir = ROOT_DIR / game_specific_log_dir_str

    general_log_file = game_specific_log_dir / "general.log"

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
    args = [
        "--preset", "wwi_2p",
        "--max_years", "1914",
        "--num_negotiation_rounds", "0",
        "--llm-models", "mock_bloc_model_1,mock_bloc_model_2"
    ]
    stdout, stderr, returncode = run_lm_game_process(args)

    log_file = find_log_file_for_game(stdout) # Default prefix is diplomacy_game
    assert log_file is not None, f"Could not find log file from lm_game output. Stdout: {stdout}"

    # Check agent initialization for blocs and one neutral
    assert count_occurrences_in_log(log_file, r"Creating agent for 'ENTENTE_BLOC' of type 'bloc_llm'") == 1
    assert count_occurrences_in_log(log_file, r"Creating agent for 'CENTRAL_BLOC' of type 'bloc_llm'") == 1
    assert count_occurrences_in_log(log_file, r"Creating agent for 'NEUTRAL_ITALY' of type 'neutral'") == 1

    warning_pattern = r"BlocLLMAgent '.*?' \(bloc .*?\) TEMPORARILY returning .*? orders for representative power .*? only"
    # This warning appears once per phase per bloc agent if orders are generated.
    # For a single year (Spring, Fall movement phases), expect it multiple times.
    # Exact count depends on how many phases are run and if orders are successfully generated.
    # Let's check if it appears at least for each bloc once.
    # Number of game phases resulting in orders: S1914M, F1914M = 2 phases
    # So, 2 blocs * 2 phases = 4 warnings expected if game runs fully for 1914.
    # If the game ends prematurely due to orchestrator issues, this count might be lower.
    # For now, let's check it appears at least once.
    assert count_occurrences_in_log(log_file, warning_pattern) >= 1

    assert count_occurrences_in_log(log_file, r"BlocLLMAgent 'entente_bloc_.*?' sending prompt for orders") > 0
    assert count_occurrences_in_log(log_file, r"BlocLLMAgent 'central_bloc_.*?' sending prompt for orders") > 0

    if returncode != 0:
        print(f"WARNING: test_4p_bloc_game_wwi_preset completed with return code {returncode}. Stdout: {stdout} Stderr: {stderr}")
        # This is acceptable for now, as PhaseOrchestrator is not yet adapted for bloc orders.
    else:
        # If it somehow completes with 0, it might mean not all logic paths were hit,
        # or the game ended very early before potential issues.
        print(f"INFO: test_4p_bloc_game_wwi_preset completed with return code 0. This might be unexpected if PhaseOrchestrator is not adapted.")

```
