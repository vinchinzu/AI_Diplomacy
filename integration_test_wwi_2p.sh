#!/bin/bash

echo "🔎 Integration test: WWI 2-player scenario (Entente vs Central Powers)…"

python lm_game.py --game_config_file wwi_test.toml
