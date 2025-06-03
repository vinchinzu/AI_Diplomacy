import subprocess
import pytest
from pathlib import Path

# Define the root directory of the project
ROOT_DIR = Path(__file__).resolve().parents[2]

@pytest.mark.integration
def test_lm_game_wwi_two_player_spring_1901():
    """
    Runs lm_game.py --scenario wwi_two_player for one Spring season (Spring 1901)
    to exercise orchestrator paths.
    """
    scenario_file = ROOT_DIR / "wwi_scenario.toml"
    command = [
        "python",
        str(ROOT_DIR / "lm_game.py"),
        "--scenario",
        "wwi_two_player",
        "--scenario-file",
        str(scenario_file),
        "--phase-limit",
        "Spring 1901"
    ]

    # It's good practice to capture stdout and stderr, and check the return code.
    process = subprocess.run(command, capture_output=True, text=True, cwd=ROOT_DIR)

    # Assert that the command executed successfully
    assert process.returncode == 0, f"lm_game.py execution failed with error: {process.stderr}"

    # Add more specific assertions based on expected output or side effects if necessary.
    # For now, a successful run (returncode 0) is the primary check.
    # Check if critical orchestrator components were logged or if specific output exists.
    # Example (needs adjustment based on actual game output):
    # assert "Orchestrating Spring 1901 Movement Phase" in process.stdout
    # assert "Orchestrating Spring 1901 Retreat Phase" in process.stdout # If applicable
    # assert "Orchestrating Spring 1901 Build Phase" in process.stdout # If applicable
