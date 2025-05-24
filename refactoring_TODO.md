# Refactoring TODOs

## Documentation Updates (Blocked by Tooling)

The following documentation updates were prepared but could not be saved due to tool errors. They need to be applied once the tooling issues are resolved.

**Target Files:**
*   `README.md`
*   `docs/LOCAL_NETWORK_OLLAMA_SETUP.md`

**Summary of Changes:**

*   **Integration of `llm` Library**:
    *   Reflect that the project now uses Simon Willison's `llm` library.
    *   Update installation instructions: `pip install llm` and necessary plugins (`llm-openai`, `llm-ollama`, `llm-llama-cpp`, etc.).
    *   Change API key management instructions to use `llm keys set <SERVICE_NAME> <KEY>`.
*   **Model Specification**:
    *   Command-line arguments (`--models`, `--model_id`) now expect `llm`-compatible model IDs (e.g., "gpt-4o", "ollama/llama3").
*   **Endpoint Configuration**:
    *   Explain that `llm` plugins handle their own endpoint configurations (e.g., for Ollama, llama.cpp).
    *   Mention `OPENAI_API_BASE_URL` for the OpenAI-compatible `llama.cpp` server setup.
*   **Removal of Old Client System**: Note the removal of `ai_diplomacy/clients.py`.
*   **`docs/LOCAL_NETWORK_OLLAMA_SETUP.md` Specifics**:
    *   Update all sections to align with the `llm` library usage for connecting to local Ollama and llama.cpp servers.
    *   Ensure examples for `lm_game.py` and `network_lm_agent.py` are correct.
```
