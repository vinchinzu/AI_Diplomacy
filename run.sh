#!/bin/bash

# note the summaries aren't actually used so the model doesn't matter here
python3 lm_game.py \
    --max_year 1905 \
    --num_negotiation_rounds 4 \
    --models "openrouter-google/gemini-2.5-flash-preview, openrouter-google/gemini-2.5-flash-preview, openrouter-google/gemini-2.5-flash-preview, openrouter-google/gemini-2.5-flash-preview, openrouter-google/gemini-2.5-flash-preview, openrouter-google/gemini-2.5-flash-preview, openrouter-google/gemini-2.5-flash-preview"