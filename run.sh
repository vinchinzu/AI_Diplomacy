#!/bin/bash

# note the summaries aren't actually used so the model doesn't matter here
# Defaulting all models to ollama/gemma3:4b as requested.
MODEL_NAME="gemma3:latest"
python3 lm_game.py \
    --max_year 1905 \
    --num_negotiation_rounds 1 \
    --models "$MODEL_NAME, $MODEL_NAME, $MODEL_NAME, $MODEL_NAME, $MODEL_NAME, $MODEL_NAME, $MODEL_NAME"
