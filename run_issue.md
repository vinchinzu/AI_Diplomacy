# Ollama Connection Issue in AI Diplomacy Project

## 1. Problem Summary

The Python application (`lm_game.py` launched via `run.sh`) is attempting to connect to an Ollama instance on incorrect ports (e.g., `45455`, `42001`) despite the `run.sh` script setting and exporting the `OLLAMA_HOST` environment variable to use port `11434` (or the value of `$OLLAMA_PORT`).

This results in connection errors, such as:
```
RuntimeError: Async execution failed: POST predict: Post "http://127.0.0.1:42001/completion": EOF (status code: -1)
```
and
```
RuntimeError: Async execution failed: health resp: Get "http://127.0.0.1:45455/health": dial tcp 127.0.0.1:45455: connect: connection refused (status code: -1)
```

## 2. Diagnosis

The root cause is likely that the `llm` Python library (and its `llm-ollama` plugin) has its own configuration settings that are taking precedence over the `OLLAMA_HOST` environment variable. This can occur in two main ways:

*   **Global Plugin Configuration:** The `llm-ollama` plugin might have a specific `ollama_url` (or similar, like `base_url`) set in the `llm` tool's global settings file.
*   **Model Alias Configuration:** The model being used (e.g., `gemma3:latest`) might be defined as an alias within `llm` that includes an overriding `ollama_url` option.

The application uses the `llm` library, which then uses `llm-ollama` to interact with the Ollama server. If `llm` finds a configured URL in its settings, it will use that instead of relying on the `OLLAMA_HOST` environment variable.

## 3. Troubleshooting Steps Attempted

*   Using `llm plugins --unset ollama ollama_url` was attempted, but the command failed with `Error: No such option: --unset`, indicating this command is not available or has a different syntax in the installed version of `llm`.

## 4. Recommended Solution: Manual Configuration Check

The most reliable way to resolve this is to manually inspect and edit the `llm` configuration files.

**A. Locate `llm` Configuration Files:**
   These are typically found in your home directory:
   *   **Settings File:**
        *   `~/.config/llm/settings.json` (Primary location)
        *   `~/.llm/settings.json` (Older location, check if the above doesn't exist)
   *   **Aliases File:**
        *   `~/.config/llm/aliases.json` (Primary location)
        *   `~/.llm/aliases.json` (Older location)

**B. Edit `settings.json`:**
   1.  Open the `settings.json` file.
   2.  Look for a section related to the `llm-ollama` plugin or a global default for `ollama_url`. It might look like:
       ```json
       {
           "plugins": {
               "llm_ollama": {
                   "ollama_url": "http://127.0.0.1:42001" // Or another incorrect port
               }
           },
           // ... other settings ...
       }
       ```
   3.  **Action:** If you find an `ollama_url` key (or similar, like `base_url`) associated with the `ollama` plugin, **delete that specific key-value pair**. If the `llm_ollama` entry only contains this URL, you might consider removing the entire `llm_ollama` block from `plugins`. The goal is to remove any hardcoded URL so the plugin defaults to using the `OLLAMA_HOST` environment variable.

**C. Edit `aliases.json` (If you use an alias for the model):**
   1.  Open the `aliases.json` file.
   2.  If you are using an alias for your model (e.g., `gemma3:latest` might be an alias, or you might have defined one like `my-gemma`), look for its definition:
       ```json
       {
           "gemma3:latest": { // Or your alias name
               "model_id": "ollama/gemma3:latest",
               "options": {
                   "ollama_url": "http://127.0.0.1:42001" // Incorrect port
               }
           }
           // ... other aliases ...
       }
       ```
   3.  **Action:** If you find an `ollama_url` under the `options` for your model alias, **remove that `ollama_url` line**.

**D. Verify `OLLAMA_HOST` in `run.sh`:**
   Ensure your `run.sh` script correctly sets and exports `OLLAMA_HOST` to the desired Ollama address (e.g., `http://127.0.0.1:11434`):
   ```bash
   OLLAMA_PORT="${OLLAMA_PORT:-11434}"
   OLLAMA_HOST="http://127.0.0.1:$OLLAMA_PORT"
   # ...
   export OLLAMA_HOST
   # ...
   # Ensure Ollama server is started on this OLLAMA_PORT
   # e.g., OLLAMA_PORT=$OLLAMA_PORT ollama serve
   ```

**E. Test with `llm` CLI (Optional but Recommended):**
   After making changes to the JSON configuration files:
   1.  Ensure `OLLAMA_HOST` is correctly set in your current terminal session:
       ```bash
       export OLLAMA_HOST="http://127.0.0.1:11434" # Or your configured port
       ```
   2.  Make sure your Ollama server is running and listening on this address and port.
   3.  Try a direct `llm` command:
       ```bash
       llm -m gemma3:latest "Briefly, what is the capital of France?"
       ```
   4.  This helps verify if `llm` itself is now respecting the `OLLAMA_HOST` environment variable.

**F. Run the Application:**
   After confirming/correcting the configurations, try running your `run.sh` script again.

## 5. Secondary Issue Noted (For Later Investigation)

The logs also show errors like:
```
ERROR - [ITALY] Error formatting negotiation diary prompt template: 'content'. Skipping diary entry.
```
This indicates a `KeyError: 'content'` within the application's prompt formatting logic for diary entries. This is a separate issue from the Ollama connection problem and will need to be addressed once the connection is stable. It suggests that the data being used to format a prompt is missing an expected `'content'` field. 