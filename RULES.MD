# Development Rules

This document outlines the core development rules for the AI Diplomacy project.

## 1. Architectural Layers

The project is divided into three strict layers. Code cannot reach "backward" into a higher-numbered layer.

1.  **`domain`**: Pure, standalone data classes. No LLMs, no I/O, no complex logic.
2.  **`agents`**: Agent implementations. Depends only on `domain`.
3.  **`runtime`**: Game loop, orchestration, and I/O. Depends on `agents` and `domain`.

This layering ensures that the core game logic (`domain`) is completely isolated and testable, and that agents can be developed and tested without needing the full runtime environment.

## 2. Package Management

-   **ONLY use `uv`**, never `pip` directly.
-   **Installation**: `uv add <package>`
-   **Running tools**: `uv run <tool>`
-   **Upgrading**: `uv add --dev <package> --upgrade-package <package>`
-   **FORBIDDEN**: `uv pip install`, `@latest` syntax.

## 3. Code Quality

-   **Type hints are required** for all new code.
-   Public APIs must have **docstrings**.
-   Functions should be **focused and small**.
-   Follow **existing patterns** exactly.
-   Line length: **88 characters maximum**.

## 4. Testing

-   **Framework**: `uv run --frozen pytest`
-   **Async testing**: Use `anyio`, not `asyncio`.
-   **Coverage**: Test edge cases and errors.
-   New features require **tests**.
-   Bug fixes require **regression tests**.

## 5. Python Best Practices

-   Focus on **modular components** and **single-purpose classes**.
-   Use **strict Python typing** that is `mypy` compatible.
-   Use `pytest` - **do not use mocks**, but rather builders.
-   Avoid using `getattr` and `hasattr` in favor of more readable code.
-   Avoid string comparisons and use **typed enums**.
-   Always use `.venv` and **never `venv`** to keep virtual environments hidden.
-   Make **reusable modules** instead of monolithic code where possible.
-   Do not use `requirements.txt` for Python requirements; instead use `uv add ...` or a `setup.sh` shell script.

## Python Tools

## Code Formatting

1. Ruff
   - Format: `uv run --frozen ruff format .`