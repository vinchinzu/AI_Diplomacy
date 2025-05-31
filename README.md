# AI Diplomacy: LLM-Powered Strategic Gameplay

## Overview

This repository aims to create a versatile AI-driven system for playing the game of Diplomacy, supporting 2 to 7 players in various configurations. The project intends to allow for games with all LLM agents, all human players, or mixed human-AI games. A key design goal is to provide robust support for LLM-controlled powers, enabling them to engage in strategic decision-making, negotiation, and bloc-level coordination. The system is designed to be compatible with a wide range of Large Language Models (LLMs), both local (e.g., via Ollama) and API-based.

The current development focus and primary testbed is a WWI two-player scenario, detailed in `run_wwi_test.py`, which serves to refine core mechanics and agent capabilities.

## Core Components (as demonstrated in the WWI testbed)

*   **`run_wwi_test.py`**: The main script for executing the WWI two-player scenario. It configures the game, initializes agents, and runs the game loop.
*   **`scenarios.py`**: Defines game scenarios, including `wwi_two_player`.
*   **`ai_diplomacy/`**: Directory containing the core AI logic:
    *   **`agents/llm_agent.py`**: Implements the `LLMAgent` that uses an LLM for decision-making.
    *   **`orchestrators/`**: Manages game phases (movement, retreat, build) and negotiation.
        *   `phase_orchestrator.py`: Main orchestrator for the game loop.
        *   `movement.py`, `build.py`, `retreat.py`, `negotiation.py`: Strategies for specific phases.
    *   **`services/`**: Supporting services.
        *   `llm_coordinator.py`: Handles communication with LLMs (via the `llm` library), including serial access for local models.
        *   `game_config.py`: Manages game configuration.
        *   `logging_setup.py`: Configures logging.
    *   **`constants.py`**: Defines project-wide constants.
    *   **`game_history.py`**: Tracks game events and messages.

## Running the Current WWI Test Scenario

1.  **Setup Environment**:
    *   Ensure Python is installed.
    *   Install dependencies using `uv` (see `pyproject.toml`):
        ```bash
        uv pip install . 
        # Or, if you have specific dependencies for this test:
        # uv pip install -r requirements_test.txt 
        ```
        (Adjust based on your actual dependency management with `uv` and `pyproject.toml`)
    *   Set up any necessary LLM API keys or local LLM (e.g., Ollama with a model like Gemma) as environment variables (refer to `.env.example` if available, or create a `.env` file).

2.  **Execute the Test**:
    ```bash
    python run_wwi_test.py
    ```
    *   Logs will be generated in the `logs/` directory.
    *   The script is configured to run a short game (e.g., up to 1902) for testing purposes. Key parameters like LLM models, log level, and game length are set within `run_wwi_test.py`.

## Key Features Currently Demonstrated (via `run_wwi_test.py`)

*   **LLM-Powered Agents**: Each of the three conceptual powers (Entente, Central, Neutral Italy) in the test scenario is mapped to an LLM agent.
*   **Two-Player WWI Scenario**: Uses the `scenarios.wwi_two_player` factory.
*   **Serialized Local LLM Access**: Ensures stable operation with local LLMs by processing requests sequentially.
*   **Verbose Debug Logging**: `verbose_llm_debug` flag in `run_wwi_test.py` and agent configurations enables detailed logging of LLM prompts and responses.
*   **Error Handling**: The script and core components include mechanisms to catch and log errors, and in critical cases, halt execution.

## Intended Capabilities & Future Vision

The broader vision for this project includes:

*   **Flexible Player Configurations**: Support for standard 7-player games, as well as smaller variants (2-6 players).
*   **Human-AI Hybrid Games**: Allow human players to participate alongside or against LLM agents.
*   **Human Override**: Provide an interface or mechanism for human players to review and override orders proposed by LLM agents they are supervising or collaborating with.
*   **Advanced Bloc Management**: Enable sophisticated coordination and distinct strategies for groups of powers (blocs) controlled by either AI or human players.
*   **Universal LLM Support**: Leverage the `llm` library and its plugin architecture to ensure compatibility with a wide array of current and future LLMs, whether accessed via APIs or run locally.

## Known Issues & Future Work

Refer to `ISSUES.md` for a list of known bugs, implemented features being refined, and planned enhancements. This includes items like implementing a true non-LLM neutral agent for Italy and exploring more complex bloc-level coordinated moves.

## Development Focus

While the long-term vision is expansive, current development efforts are centered on ensuring the stability, correctness, and feature completeness of the core AI agent interactions and game orchestration, primarily using the `run_wwi_test.py` scenario as the proving ground.
