#!/usr/bin/env bash
gitingest . -i run.sh -i lm_game.py -i pytest.ini -i pyproject.toml -i models.toml -e 'logs/' -i 'tests/' -e '.venv/' -i 'ai_diplomacy/' -e digest.txt -e results -e data -e htmlcov
 -i README.md -e 'ai_diplomacy/prompts/'