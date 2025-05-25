#!/bin/bash

# note the summaries aren't actually used so the model doesn't matter here
# Defaulting all models to ollama/gemma3:4b as requested.
MODEL_NAME="gemma3:latest"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
OLLAMA_HOST="http://127.0.0.1:$OLLAMA_PORT"

# Check if Ollama is running
if ! curl --silent --fail "$OLLAMA_HOST/api/tags" > /dev/null; then
  echo "Ollama server is not running on $OLLAMA_HOST."
  echo "Start it with: OLLAMA_PORT=$OLLAMA_PORT ollama serve"
  exit 1
fi

# Check if the model is available
if ! curl --silent "$OLLAMA_HOST/api/tags" | grep -q "${MODEL_NAME%%:*}"; then
  echo "Model $MODEL_NAME not found in Ollama. Pulling it now..."
  ollama pull "${MODEL_NAME%%:*}" || { echo "Failed to pull model $MODEL_NAME"; exit 1; }
fi

# Export OLLAMA_HOST for the Python code
export OLLAMA_HOST

#add a test query
#works
#curl "$OLLAMA_HOST/api/generate" -d '{"model": "gemma3:latest", "prompt": "Hello, world!"}'

python3 lm_game.py \
     --max_year 1905 \
     --num_negotiation_rounds 1 \
     --fixed_models "$MODEL_NAME,$MODEL_NAME,$MODEL_NAME,$MODEL_NAME,$MODEL_NAME,$MODEL_NAME,$MODEL_NAME"
