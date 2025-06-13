# AI Diplomacy: LLM-Powered Strategic Gameplay

## Overview

This repository aims to create a versatile AI-driven system for playing the game of Diplomacy, supporting 2 to 7 players in various configurations. The project intends to allow for games with all LLM agents, all human players, or mixed human-AI games. A key design goal is to provide robust support for LLM-controlled powers, enabling them to engage in strategic decision-making, negotiation, and bloc-level coordination. The system is designed to be compatible with a wide range of Large Language Models (LLMs), both local (e.g., via Ollama) and API-based.

The project is structured into three distinct layers to ensure a clean, testable, and maintainable codebase.

## Architectural Layers

The codebase is organized into three core packages:

### 1. `ai_diplomacy.domain`

This is the pure, core logic of the game. It has no dependencies on LLMs, logging, or any external services. It defines the data structures that represent the game state.

-   **`board.py`**: Defines the `BoardState` of the game.
-   **`phase.py`**: Defines the `PhaseState` of the game.
-   **`order.py`**: Defines `Order` objects.
-   **`messaging.py`**: Defines `DiploMessage` objects.
-   **`adapter_diplomacy.py`**: A thin wrapper that maps the upstream `diplomacy.Game` objects into the domain's dataclasses.

### 2. `ai_diplomacy.agents`

This layer contains the logic for the different types of agents that can play the game. It depends only on the `domain` layer.

-   **`base.py`**: Defines the `Agent` protocol that all agents must implement.
-   **`llm/`**: Contains the logic for LLM-based agents.
-   **`rule_based/`**: Contains the logic for rule-based agents.

### 3. `ai_diplomacy.runtime`

This layer is responsible for the "glue" code that runs the game. It contains the game loop, persistence logic, and other components that are not part of the core domain or agent logic.

-   **`engine.py`**: Contains the main game engine.
-   **`bloc_manager.py`**: Manages blocs of agents.
-   **`persistence.py`**: Handles saving and loading game state.

## Running the Current WWI Test Scenario

1.  **Setup Environment**:
    *   Ensure Python is installed.
    *   Install dependencies using `uv` (see `pyproject.toml`):
        ```bash
        uv pip install . 
        ```
    *   Set up any necessary LLM API keys or local LLM (e.g., Ollama with a model like Gemma) as environment variables (refer to `.env.example` if available, or create a `.env` file).

2.  **Execute the Test**:
    ```bash
    python lm_game.py --scenario wwi_two_player --config wwi_scenario.toml
    ```
    *   Logs will be generated in the `logs/` directory.
    *   The game is configured via `wwi_scenario.toml` (e.g., for game length up to 1902) and can be overridden by `lm_game.py` arguments. Key parameters like LLM models and log level are also set in the TOML file.

## Key Features Currently Demonstrated (via the WWI scenario)

*   **LLM-Powered Agents**: Each of the three conceptual powers (Entente, Central, Neutral Italy) in the test scenario is mapped to an LLM agent as defined in `wwi_scenario.toml`.
*   **Two-Player WWI Scenario**: Uses the `scenarios.wwi_two_player` factory, invoked via `lm_game.py`.
*   **Serialized Local LLM Access**: Ensures stable operation with local LLMs by processing requests sequentially (if configured).
*   **Verbose Debug Logging**: `verbose_llm_debug` setting (typically in `wwi_scenario.toml` under `dev_settings`) enables detailed logging of LLM prompts and responses.
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

While the long-term vision is expansive, current development efforts are centered on ensuring the stability, correctness, and feature completeness of the core AI agent interactions and game orchestration, primarily using the WWI scenario (run via `lm_game.py --scenario wwi_two_player --config wwi_scenario.toml`) as the proving ground.
