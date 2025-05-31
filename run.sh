#!/bin/bash

# note the summaries aren't actually used so the model doesn't matter here
# Defaulting all models to ollama/gemma3:4b as requested.
MODEL_NAME="gpt-4o"
export MODEL_NAME
#MODEL_NAME="gemma3:latest"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
OLLAMA_HOST="http://127.0.0.1:$OLLAMA_PORT"
OLLAMA_BASE_URL="http://127.0.0.1:$OLLAMA_PORT"

# Export OLLAMA_HOST for the Python code
export OLLAMA_HOST
export OLLAMA_BASE_URL
export OLLAMA_PORT

# Function to check and pull Ollama models
check_and_pull_ollama_model() {
  local model_to_check="$1"
  
  # Handle both ollama/ prefixed models and direct model names
  if [[ "$model_to_check" == ollama/* ]]; then
    echo "Checking Ollama model: $model_to_check"
    OLLAMA_MODEL_TAG="${model_to_check#ollama/}"
  elif [[ "$model_to_check" == *:* ]] || [[ "$model_to_check" =~ ^(llama|gemma|mistral|qwen|deepseek) ]]; then
    echo "Checking Ollama model: $model_to_check"
    OLLAMA_MODEL_TAG="$model_to_check"
  else
    echo "Skipping Ollama check for non-Ollama model: $model_to_check"
    return 0
  fi
  
  # Check if Ollama is running
  if ! curl --silent --fail "$OLLAMA_HOST/api/tags" > /dev/null; then
    echo "Ollama server is not running on $OLLAMA_HOST."
    echo "Please start it, e.g., with: OLLAMA_PORT=$OLLAMA_PORT ollama serve"
    exit 1 # Exit if server not running, as no ollama operations will succeed
  fi

  # Check if the model (potentially with a version tag) is available
  # First, try the exact tag
  if ! curl --silent "$OLLAMA_HOST/api/tags" | jq -e --arg name "$OLLAMA_MODEL_TAG" '.models[] | select(.name == $name)' > /dev/null; then
    # If exact tag not found, and it has a version, try with ':latest' for the base model name
    # This handles cases where e.g. "llama3" is requested but only "llama3:latest" exists or vice-versa
    BASE_MODEL_NAME="${OLLAMA_MODEL_TAG%%:*}"
    if [[ "$OLLAMA_MODEL_TAG" == *:* ]] && \
       ! curl --silent "$OLLAMA_HOST/api/tags" | jq -e --arg name "${BASE_MODEL_NAME}:latest" '.models[] | select(.name == $name)' > /dev/null; then
      echo "Model $model_to_check (tag: $OLLAMA_MODEL_TAG) not found in Ollama. Pulling it now..."
      ollama pull "${OLLAMA_MODEL_TAG}" || { echo "Failed to pull model $model_to_check"; exit 1; }
      echo "Model $model_to_check pulled successfully."
    elif [[ "$OLLAMA_MODEL_TAG" != *:* ]] && \
         ! curl --silent "$OLLAMA_HOST/api/tags" | jq -e --arg name "${OLLAMA_MODEL_TAG}:latest" '.models[] | select(.name == $name)' > /dev/null; then
      # This case is for when no version tag is specified, and :latest isn't found (though previous check might have caught it)
      # It's a bit redundant but ensures we try pulling if the simple name isn't there (ollama pull often defaults to :latest)
      echo "Model $model_to_check (tag: $OLLAMA_MODEL_TAG, trying as :latest) not found in Ollama. Pulling it now..."
      ollama pull "${OLLAMA_MODEL_TAG}" || { echo "Failed to pull model $model_to_check"; exit 1; }
      echo "Model $model_to_check pulled successfully."
    else
      echo "Model $model_to_check (tag: $OLLAMA_MODEL_TAG or ${BASE_MODEL_NAME}:latest) found locally."
    fi
  else
    echo "Model $model_to_check (tag: $OLLAMA_MODEL_TAG) found locally."
  fi
}

# Initial check for the primary MODEL_NAME
check_and_pull_ollama_model "$MODEL_NAME"

# Parse command line arguments
COMMAND=${1:-"full"}

case $COMMAND in
  "integration-2p")
    echo "🔎 Integration test: 2‑player quick (no negotiation)…"
    check_and_pull_ollama_model "gemma3:4b"
    python3 lm_game.py --preset 2p_quick
    ;;
  "integration-3p")
    echo "🔎 Integration test: 3‑player with negotiation…"
    check_and_pull_ollama_model "gemma3:4b"
    python3 lm_game.py --preset 3p_neg
    ;;
  "test-api")
    echo "🧪 Testing first API call..."
    python3 test_first_api_call.py --model "$MODEL_NAME" --test single
    ;;
  "test-sequential")
    echo "🧪 Testing sequential API calls..."
    python3 test_first_api_call.py --model "$MODEL_NAME" --test sequential
    ;;
  "test-concurrent")
    echo "🧪 Testing concurrent API calls..."
    python3 test_first_api_call.py --model "$MODEL_NAME" --test concurrent
    ;;
  "test-all")
    echo "🧪 Running all API tests..."
    python3 test_first_api_call.py --model "$MODEL_NAME" --test all
    ;;
  "test-round")
    echo "🧪 Testing single round with game framework..."
    python3 lm_game_test.py --model_id "$MODEL_NAME" --test_type single_round --test_powers "FRANCE"
    ;;
  "test-order")
    echo "🧪 Testing order generation only..."
    python3 lm_game_test.py --model_id "$MODEL_NAME" --test_type order_generation --test_powers "FRANCE"
    ;;
  "test-game-sequential")
    echo "🧪 Testing sequential calls with game framework..."
    python3 lm_game_test.py --model_id "$MODEL_NAME" --test_type sequential_calls --test_powers "FRANCE" --num_sequential 3
    ;;
  "test-game-concurrent")
    echo "🧪 Testing concurrent calls with game framework..."
    python3 lm_game_test.py --model_id "$MODEL_NAME" --test_type concurrent_calls --test_powers "FRANCE,GERMANY" --max_concurrent 2
    ;;
  "full")
    echo "🎮 Running full game..."
    #add a test query
    #works
    #curl "$OLLAMA_HOST/api/generate" -d '{"model": "gemma3:latest", "prompt": "Hello, world!"}'
    # llm -m gemma3:latest "Hello, world!"

    # Define a mixed list of models for the 7 powers for the full game.
    # Ensure these models are accessible (Ollama models pulled, API keys set for API models).
    # Austria, England, France, Germany, Italy, Russia, Turkey
    FULL_GAME_MODELS_LIST="gpt-4o-mini,gemma3:4b,gpt-4o-mini,gemma3:4b,gemma3:4b,gemma3:4b,gemma3:4b"

    # Iterate through the FULL_GAME_MODELS_LIST and check/pull each model
    echo "Checking all models for the full game..."
    IFS=',' read -ra MODELS_ARRAY <<< "$FULL_GAME_MODELS_LIST"
    for model_in_list in "${MODELS_ARRAY[@]}"; do
      check_and_pull_ollama_model "$model_in_list"
    done
    echo "All models for the full game checked."

    python3 lm_game.py \
         --max_years 1902 \
         --num_negotiation_rounds 1 \
         --fixed_models "$FULL_GAME_MODELS_LIST"
    ;;
  "help")
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  test-api           - Test first API call (simple)"
    echo "  test-sequential    - Test sequential API calls (simple)"
    echo "  test-concurrent    - Test concurrent API calls (simple)"
    echo "  test-all          - Run all simple API tests"
    echo "  test-round        - Test single round with game framework"
    echo "  test-order        - Test order generation only"
    echo "  test-game-sequential - Test sequential calls with game framework"
    echo "  test-game-concurrent - Test concurrent calls with game framework"
    echo "  full              - Run full game (default)"
    echo "  help              - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 test-api       # Quick test of first API call"
    echo "  $0 test-round     # Test first round with full game setup"
    echo "  $0 full           # Run complete game"
    ;;
  *)
    echo "Unknown command: $COMMAND"
    echo "Use '$0 help' to see available commands"
    exit 1
    ;;
esac
