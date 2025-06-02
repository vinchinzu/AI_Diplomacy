import subprocess
import sys


def run_wwi_2p_test():
    """Runs the WWI two-player scenario integration test."""
    print("🔎 Integration test: WWI 2-player scenario (Entente vs Central Powers)…")

    # In a real test environment, you might want to check/pull models here too,
    # or ensure they are pre-pulled by a setup script.
    # For simplicity, we assume models are available or will be handled by lm_game.py if it includes such checks.

    command = [
        sys.executable,  # Path to current python interpreter
        "lm_game.py",
        "--preset",
        "wwi_2p",
        "--players",
        "llm,llm",  # Two LLM agents controlling the blocs
        "--llm-models",
        "gemma3:4b,gemma3:4b",  # Both blocs use gemma3:4b
        "--log_level",
        "INFO",  # Example: Set a log level
        # You might want to add other arguments like --game_id_prefix for test runs
        # e.g., "--game_id_prefix", "test_wwi_2p_"
    ]

    print(f"Running command: {' '.join(command)}")

    try:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )

        # Stream output
        output_lines = []
        if process.stdout:
            for line in iter(process.stdout.readline, ""):
                print(line, end="")
                output_lines.append(line)

        process.wait()

        output_str = "".join(output_lines)
        has_errors = "ERROR" in output_str

        if process.returncode == 0 and not has_errors:
            print("✅ WWI 2-player test completed successfully.")
        else:
            print(
                f"❌ WWI 2-player test failed. Return code: {process.returncode}. Check output for ERROR messages."
            )
            # Output was already streamed

    except FileNotFoundError:
        print(
            "Error: lm_game.py not found. Make sure it's in the same directory or in PYTHONPATH."
        )
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred while running the test: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_wwi_2p_test()
