#!/bin/bash

# note the summaries aren't actually used so the model doesn't matter here
# Defaulting all models to ollama/gemma3:4b as requested.
MODEL_NAME="gpt-4o"
export MODEL_NAME
#MODEL_NAME="gemma3:latest"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
OLLAMA_HOST="http://127.0.0.1:$OLLAMA_PORT"
OLLAMA_BASE_URL="http://127.0.0.1:$OLLAMA_PORT"

# Only check Ollama if the model name suggests it's an Ollama model
if [[ "$MODEL_NAME" == ollama/* ]]; then
  # Check if Ollama is running
  if ! curl --silent --fail "$OLLAMA_HOST/api/tags" > /dev/null; then
    echo "Ollama server is not running on $OLLAMA_HOST."
    echo "Start it with: OLLAMA_PORT=$OLLAMA_PORT ollama serve"
    exit 1
  fi

  # Extract the tag from the MODEL_NAME (e.g., "llama3" from "ollama/llama3")
  OLLAMA_MODEL_TAG="${MODEL_NAME#ollama/}"
  # Check if the model (without version tag) is available
  if ! curl --silent "$OLLAMA_HOST/api/tags" | jq -e --arg name "${OLLAMA_MODEL_TAG%%:*}:latest" '.models[] | select(.name == $name)' > /dev/null;
  then # Also check for the exact tag if it includes one
    if ! curl --silent "$OLLAMA_HOST/api/tags" | jq -e --arg name "$OLLAMA_MODEL_TAG" '.models[] | select(.name == $name)' > /dev/null;
    then
      echo "Model $MODEL_NAME (tag: $OLLAMA_MODEL_TAG) not found in Ollama. Pulling it now..."
      ollama pull "${OLLAMA_MODEL_TAG}" || { echo "Failed to pull model $MODEL_NAME"; exit 1; }
    fi
  fi
else
  echo "Skipping Ollama check for non-Ollama model: $MODEL_NAME"
fi

# Export OLLAMA_HOST for the Python code
export OLLAMA_HOST
export OLLAMA_BASE_URL
export OLLAMA_PORT

# Parse command line arguments
COMMAND=${1:-"full"}

case $COMMAND in
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
    FULL_GAME_MODELS_LIST="gpt-4o,ollama/llama3,gpt-4o-mini,ollama/mistral,gpt-3.5-turbo,ollama/gemma3:4b,ollama/phi3"

    python3 lm_game.py \
         --max_year 1905 \
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
