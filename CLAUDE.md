# AI Diplomacy Development Guide

## Commands
- Run game: `python lm_game.py --max_year 1910 --summary_model "gpt-4o-mini" --num_negotiation_rounds 3`
- Run tests: `pytest -v diplomacy/tests/` or `pytest -v -k test_name`
- Run specific test: `pytest -v diplomacy/tests/path_to_test.py::test_function`
- Lint: `pylint diplomacy/path/to/file.py`
- Full test suite: `./diplomacy/run_tests.sh`

## Code Style
- Use Python type hints for function parameters and return values
- Follow PEP 8 naming: snake_case for functions/variables, UPPER_CASE for constants
- Organize imports: standard library, third-party, local modules
- Error handling: Use specific exceptions with informative messages
- Docstrings: Use multi-line docstrings with parameter descriptions
- Keep functions focused on a single responsibility
- Models/LLM clients inherit from BaseModelClient and implement required methods
- When possible, use concurrent operations (see concurrent.futures in lm_game.py)

## Environment
Python 3.5+ required. Use virtual environment with requirements.txt.