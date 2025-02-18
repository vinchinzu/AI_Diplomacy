#!/bin/bash

# note the summaries aren't actually used so the model doesn't matter here
python lm_game.py \
    --max_year 1910 \
    --summary_model "gpt-4o-mini" \
    --num_negotiation_rounds 3