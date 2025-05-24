# Local Network and Ollama/llama.cpp LLM Setup Guide

This guide provides instructions for setting up and running the AI Diplomacy project with local Large Language Models (LLMs) using Ollama or a llama.cpp server, both for single-player (`lm_game.py`) and multi-player network games (`network_lm_agent.py` with a central game server).

## Prerequisites

Before you begin, ensure you have the following installed:
*   **Python 3.8+**: The project is developed with Python.
*   **Git**: For cloning the repository.
*   **pip**: For installing Python packages.
*   **A C++ compiler**: Required for `llama-cpp-python` if you install it with hardware acceleration (e.g., via `CMAKE_ARGS`).
*   **(Optional but Recommended) A Conda/Miniconda or Python Virtual Environment**: To manage project dependencies in an isolated environment.

## Project Installation

1.  **Clone the Repository**:
    ```bash
    git clone <repository_url> # Replace <repository_url> with the actual URL
    cd ai-diplomacy # Or your project's root directory name
    ```

2.  **Create and Activate a Virtual Environment (Recommended)**:
    *   Using Conda:
        ```bash
        conda create -n ai_diplomacy python=3.9
        conda activate ai_diplomacy
        ```
    *   Using Python's `venv`:
        ```bash
        python -m venv venv
        source venv/bin/activate # On Windows: venv\Scripts\activate
        ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    This will install `diplomacy`, `openai`, `anthropic`, `google-generativeai`, `httpx`, `python-dotenv`, `llama-cpp-python` (if not already installed, or you can install a specific version/build later), and other necessary packages.

## Part 1: Single-Player with Local LLMs (`lm_game.py`)

This section covers running a single AI agent in a local game against itself or built-in DipNet agents, using either Ollama or a llama.cpp server.

### 1.1 Setting up and Running with Ollama

Ollama allows you to run open-source LLMs locally with ease.

1.  **Install Ollama**:
    *   Download and install Ollama from [ollama.com](https://ollama.com/).
    *   Follow the instructions for your operating system.

2.  **Pull a Model**:
    *   Open your terminal and pull a model. For example, Llama 3 8B Instruct:
        ```bash
        ollama pull llama3
        ```
    *   You can find other models on the [Ollama library](https://ollama.com/library).

3.  **Ensure Ollama Server is Running**:
    *   Typically, Ollama runs in the background after installation. You can check its status or start it if necessary (refer to Ollama documentation).
    *   By default, Ollama serves models at `http://localhost:11434`.

4.  **Configure Environment Variables**:
    *   Create a `.env` file in the project's root directory (e.g., where `lm_game.py` is located).
    *   For Ollama, the `OLLAMA_BASE_URL` is usually `http://localhost:11434`. If your Ollama server runs on a different address, set it accordingly.
        ```env
        # .env file
        OLLAMA_BASE_URL="http://localhost:11434"
        # OPENAI_API_KEY="sk-dummy" # Not strictly needed for Ollama but good for consistency
        ```
        *Note: The `OllamaClient` in the project defaults to `http://localhost:11434` if `OLLAMA_BASE_URL` is not set.*

5.  **Run `lm_game.py` with an Ollama Model**:
    *   Use the `ollama/` prefix for your model ID.
    *   Example:
        ```bash
        python lm_game.py --power_name FRANCE --model_id "ollama/llama3" --num_players 1 
        ```
    *   This command runs a game where France is controlled by the `ollama/llama3` model. The other powers will likely be controlled by default DipNet agents if `num_players 1` means one LLM player. Adjust `--num_players` and other arguments as needed.

### 1.2 Setting up and Running with a llama.cpp Server

llama.cpp is a C/C++ port of LLaMA for efficient inference. You can run it as an OpenAI-compatible server.

1.  **Install `llama-cpp-python` with Server Option**:
    *   If `llama-cpp-python` was installed without server capabilities or you need a specific build (e.g., with GPU acceleration), you might need to reinstall it.
    *   For a basic CPU build that includes the server:
        ```bash
        pip uninstall llama-cpp-python
        pip install llama-cpp-python[server]
        ```
    *   For builds with hardware acceleration (e.g., cuBLAS for NVIDIA GPUs):
        ```bash
        # Example for NVIDIA GPUs
        CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip uninstall llama-cpp-python
        CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip install llama-cpp-python[server] --force-reinstall --upgrade --no-cache-dir
        ```
        Refer to the [llama-cpp-python documentation](https://github.com/abetlen/llama-cpp-python) for detailed installation instructions for different hardware.

2.  **Download a GGUF Model File**:
    *   You'll need a model in GGUF format. You can find these on Hugging Face (e.g., search for "llama3 GGUF").
    *   Download the GGUF file to a known location (e.g., `models/`).

3.  **Start the llama.cpp Server**:
    *   Open your terminal and run the server, pointing to your GGUF model file.
    *   The server command might look like this:
        ```bash
        python -m llama_cpp.server --model "/path/to/your/model.gguf" --host 0.0.0.0 --port 8080 --n_ctx 4096
        ```
        *   Replace `/path/to/your/model.gguf` with the actual path to your model.
        *   `--host 0.0.0.0` makes it accessible from other machines on your network (useful for Part 2).
        *   `--port 8080` is a common port; you can change it.
        *   `--n_ctx 4096` sets the context size; adjust as needed for your model and hardware.
    *   The server provides an OpenAI-compatible API endpoint, typically at `http://localhost:8080/v1`.

4.  **Configure Environment Variables**:
    *   Edit or create your `.env` file in the project root.
    *   Set `OPENAI_API_BASE_URL` to your llama.cpp server's API endpoint.
    *   `OPENAI_API_KEY` is often not required by llama.cpp server but the client library might expect it. A dummy key like "sk-dummy" usually works.
        ```env
        # .env file
        OPENAI_API_BASE_URL="http://localhost:8080/v1"
        OPENAI_API_KEY="sk-dummy" 
        # OLLAMA_BASE_URL="http://localhost:11434" # Can be kept if you switch between them
        ```

5.  **Run `lm_game.py` with a llama.cpp Model**:
    *   Use the `llama-cpp/` or `llamacpp/` prefix for your model ID. The part after the prefix can be arbitrary but helps identify the model (e.g., "llama-cpp/my-llama3-gguf"). The actual model served is determined by the server's `--model` argument.
    *   Example:
        ```bash
        python lm_game.py --power_name AUSTRIA --model_id "llama-cpp/Llama3-8B-Instruct-GGUF" --num_players 1
        ```

## Part 2: Multi-Player on Local Network

This section explains how to set up a game where multiple AI agents, each potentially running on a different machine on your local network, play against each other. Each agent uses its own local LLM (Ollama or llama.cpp).

1.  **Start the Central Diplomacy Game Server**:
    *   On one machine (can be one of the player machines or a separate one), start the central Diplomacy game server. This server manages the game state and communication.
    *   Ensure the `diplomacy` package is installed (it should be from `requirements.txt`).
    *   Run the server:
        ```bash
        python -m diplomacy.server.run --host 0.0.0.0 --port 8432
        ```
        *   `--host 0.0.0.0` allows other machines on your network to connect.
        *   `--port 8432` is the default port. You can change it if needed.
        *   Note the IP address of this server machine on your local network (e.g., by using `ipconfig` on Windows or `ifconfig`/`ip addr` on Linux/macOS). Let's say it's `192.168.1.100`.

2.  **For Each AI Player (on their respective machines or separate processes):**

    *   **Set up Local LLM**:
        *   Ensure either Ollama is running with the desired model OR a llama.cpp server is running with its model, as described in Part 1.
        *   The LLM server can run on the same machine as the `network_lm_agent.py` script or on a different machine accessible via the network (e.g., if you have a dedicated LLM server machine).

    *   **Configure Environment Variables (`.env` file for each agent instance)**:
        *   If using **Ollama**:
            ```env
            OLLAMA_BASE_URL="http://localhost:11434" # Or the address of the Ollama server if remote
            ```
        *   If using **llama.cpp server**:
            ```env
            OPENAI_API_BASE_URL="http://localhost:8080/v1" # Or the address of the llama.cpp server
            OPENAI_API_KEY="sk-dummy"
            ```
        *   *Ensure these variables are set in the environment where each `network_lm_agent.py` will run.*

    *   **Run `network_lm_agent.py`**:
        *   Open a new terminal for each agent.
        *   Navigate to the project directory.
        *   Activate the virtual environment.
        *   Run the agent script, configuring it to connect to the central game server and its local LLM.

        *   **Example for an agent playing as FRANCE, using a local Ollama `llama3` model, connecting to the central server at `192.168.1.100:8432` for game `my_network_game`**:
            ```bash
            python network_lm_agent.py \
                --host 192.168.1.100 \
                --port 8432 \
                --game_id "my_network_game" \
                --power_name FRANCE \
                --model_id "ollama/llama3" \
                --log_dir "./logs/network_agent_FRANCE_my_network_game" 
            ```

        *   **Example for an agent playing as GERMANY, using a local llama.cpp server (model specified by server, client uses placeholder ID), connecting to `192.168.1.100:8432` for game `my_network_game`**:
            ```bash
            # Ensure llama.cpp server is running and OPENAI_API_BASE_URL is set in .env
            python network_lm_agent.py \
                --host 192.168.1.100 \
                --port 8432 \
                --game_id "my_network_game" \
                --power_name GERMANY \
                --model_id "llama-cpp/LocalModel1" \
                --log_dir "./logs/network_agent_GERMANY_my_network_game"
            ```
        *   **Important**:
            *   Replace `192.168.1.100` with the actual IP of your central game server.
            *   `--game_id` must be the same for all agents joining the same game.
            *   `--power_name` must be unique for each agent in the game.
            *   `--model_id` should match the configuration for the agent's chosen LLM (Ollama or llama.cpp).
            *   `--log_dir` helps keep logs organized for each agent.
            *   You can add `--perform_planning_phase` or adjust `--num_negotiation_rounds` as needed.

    *   Repeat this for all 7 powers (or fewer if some are human-controlled or not participating).

## Part 3: Creating a Game on the Server

The `diplomacy.server.run` script automatically creates a game if one with the specified `game_id` doesn't exist when the first player tries to join. So, typically, no separate game creation step is needed. The first `network_lm_agent.py` instance that connects with a new `game_id` will prompt its creation.

If you need more control over game creation (e.g., specific variants, deadlines), you would typically interact with the server's control interface if available, or use a separate client designed for game administration. For this project's scope, automatic creation upon joining is sufficient.

## Part 4: Model Naming and Configuration Recap

*   **Ollama Models**:
    *   Use prefix `ollama/`. Examples: `ollama/llama3`, `ollama/mistral`.
    *   `OLLAMA_BASE_URL` in `.env` (defaults to `http://localhost:11434`).
*   **Llama.cpp Server Models**:
    *   Use prefix `llama-cpp/` or `llamacpp/`. Examples: `llama-cpp/MyLocalLLaMA3`, `llamacpp/Vicuna-GGUF`.
    *   The name after the prefix is for client-side identification; the actual GGUF model is configured when starting the `llama_cpp.server`.
    *   `OPENAI_API_BASE_URL` in `.env` (e.g., `http://localhost:8080/v1`).
    *   `OPENAI_API_KEY` in `.env` (e.g., `sk-dummy`).
*   **Official OpenAI Models**:
    *   Examples: `gpt-4o`, `gpt-3.5-turbo`.
    *   Requires `OPENAI_API_KEY` for the official OpenAI API.
    *   If `OPENAI_API_BASE_URL` is set, it will target that custom endpoint instead of the official OpenAI API.
*   **Other Clients (Claude, Gemini, OpenRouter, DeepSeek)**:
    *   Refer to `ai_diplomacy/clients.py` for model ID patterns (e.g., `claude-3-opus-20240229`, `gemini-1.5-flash`, `openrouter/mistralai/mistral-7b-instruct`).
    *   Require their respective API keys (e.g., `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `DEEPSEEK_API_KEY`) to be set in the `.env` file.

## Part 5: Performance and Advanced Configuration

### Serializing Local LLM Requests

If you are running local LLM instances (such as Ollama or a llama.cpp server) on a machine with limited resources (e.g., low RAM or a less powerful GPU/CPU), you might encounter errors, timeouts, or instability if multiple AI agents (or multiple internal processes within an agent) attempt to contact these local LLM APIs simultaneously. Each request can consume a significant amount of memory and processing power.

To mitigate this and manage resource usage, you can configure the system to process requests to these local LLM services serially (one at a time). This feature uses a unified locking mechanism to ensure that only one request is sent to any of the configured local LLM types at any given moment, with subsequent requests waiting for the current one to complete.

**How to enable serial requests for local LLMs:**

Set the `SERIALIZE_LOCAL_LLMS` environment variable to `true`. For example, in your terminal:

```bash
export SERIALIZE_LOCAL_LLMS=true
```
Or add it to your `.env` file:
```env
SERIALIZE_LOCAL_LLMS=true
```

**Behavior:**

*   When `SERIALIZE_LOCAL_LLMS` is set to `true`, all API calls destined for models identified by specific prefixes (e.g., `ollama/` for Ollama models, `llamacpp/` or `llama-cpp/` for llama.cpp server models) will be queued and processed one by one using a single, shared lock.
*   The system identifies these local models if their model ID string starts with one of the configured prefixes (case-insensitive). Currently, these prefixes include `ollama/` and `llamacpp/` (or `llama-cpp/`).
*   If this environment variable is not set, or if it's set to any value other than `true` (e.g., `false`), requests to these local LLM services will be made concurrently, which is the default behavior.
*   This setting only affects models identified by the specified local prefixes. Requests to other LLM providers (e.g., official OpenAI API, Anthropic, Gemini) will remain concurrent regardless of this setting.

**When to use:**

Consider enabling this option if you observe:
*   Errors related to your local LLM instances (Ollama, llama.cpp server) when under load from multiple agents or simultaneous requests.
*   High memory usage leading to system instability or crashes of your local LLM services.
*   Timeouts when communicating with these local LLMs during periods of heavy use.

Enabling serial requests for local LLMs can significantly improve stability in resource-constrained environments by preventing multiple local services from being overwhelmed simultaneously. However, it might reduce overall throughput if your local setup could have handled some level of concurrent requests to different local services (e.g., one call to Ollama and one to a llama.cpp server). Since it's a unified lock, if one local LLM is being accessed, others (also local) will wait.

## Part 6: Troubleshooting Common Issues

*   **Connection Refused (Game Server or LLM Server)**:
    *   Ensure the server (Diplomacy game server, Ollama, or llama.cpp) is running.
    *   Check that the `--host` and `--port` used for the server match what clients are trying to connect to.
    *   For network play, ensure the server is bound to `0.0.0.0` or a specific network IP, not just `localhost`.
    *   Check firewall rules on the server machine and client machines to ensure they allow traffic on the required ports (e.g., 8432 for game server, 11434 for Ollama, 8080 for llama.cpp server).
*   **Authentication Failed (Game Server)**:
    *   The `network_lm_agent.py` uses a default username/password scheme. Ensure the server expects this or adjust accordingly. (Current server default allows any username/password).
*   **Model Not Found (Ollama or llama.cpp)**:
    *   **Ollama**: Ensure you've pulled the model (`ollama pull model_name`) and it's listed in `ollama list`. Check that `OLLAMA_BASE_URL` is correct.
    *   **Llama.cpp**: Ensure the `--model` path in the `llama_cpp.server` command is correct. The `model_id` in the client (`llama-cpp/...`) is mostly for client logic; the server dictates the actual model.
*   **HTTP Errors from LLM Server (e.g., 4xx, 5xx)**:
    *   Check the LLM server logs for more details.
    *   Ensure the API endpoint (`OLLAMA_BASE_URL` or `OPENAI_API_BASE_URL`) is correct (e.g., `/v1` is often needed for OpenAI-compatible servers).
    *   The model might be overloaded, or the request might be malformed.
*   **`No module named 'llama_cpp.server'`**:
    *   You may have installed `llama-cpp-python` without the `[server]` extra. Reinstall with `pip install llama-cpp-python[server]`.
*   **Slow LLM Responses**:
    *   Local LLMs can be resource-intensive. Check CPU/GPU usage on the LLM server machine.
    *   Consider using smaller models or models with quantization if performance is an issue.
    *   Ensure sufficient RAM and VRAM (if using GPU).
*   **Dependency Issues**:
    *   Always use a virtual environment.
    *   Ensure all packages in `requirements.txt` are installed correctly. If you encounter issues with a specific package, try installing it individually or checking its documentation for troubleshooting steps.
*   **Log Files**:
    *   Check the general logs (`*_general.log`) and LLM interaction logs (`*_llm_interactions.csv`) for both `lm_game.py` and `network_lm_agent.py` runs. They are located in the specified `--log_dir` or default log directories. These logs often provide clues about what went wrong.

This guide should help you get started with running AI Diplomacy agents using local LLMs. Happy strategizing!
```
