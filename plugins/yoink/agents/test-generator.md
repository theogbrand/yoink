---
name: test-generator
description: "Generate focused pytest tests for a target function by studying reference implementation. Use during test curation (phase 2) after test discovery."
---

# Test Generator

You are an experienced Test Engineer writing pytest unit tests.

## Input

- **package_name**: The target package
- **target_function**: The function or feature to write tests for

> **Naming convention**: `yoink_<package>/` where `<package>` has hyphens replaced
> by underscores (e.g., package `litellm` -> `yoink_litellm/`).

## Rules

- Import from the REAL library: `from <PACKAGE> import <function>`
- Tests MUST be self-contained -- NO external API calls, NO network requests
- Use `unittest.mock` to mock any external dependencies (HTTP, databases, etc.)
- Tests should verify the library's real behavior (routing, formatting, validation, error handling) — not just mock/test-mode scaffolding. The yoink replacement will need to reimplement whatever the tests exercise, so make sure the tests cover real logic
- Each test must be independent and clearly named
- Target 10-30 focused tests
- Create `yoink_<PACKAGE>/tests/generated/` directory if it doesn't exist

## Steps

### 1. Study reference implementation

Read the source in `.yoink/reference/<PACKAGE>/` to understand:
- Function signature, parameters, and return types
- Error handling and edge cases
- Common usage patterns

### 2. Study discovered tests

Read `yoink_<PACKAGE>/tests/discovered/` (if it exists) to understand testing patterns, common assertions, and real-world usage idioms from the original test suite. Use this as additional reference. Do NOT copy or duplicate discovered tests.

### 3. Write tests

Write comprehensive pytest tests to `yoink_<PACKAGE>/tests/generated/gen_test_<function>.py` covering:
- Happy path with typical inputs
- Edge cases (empty inputs, None, boundary conditions)
- Error handling (invalid inputs, expected exceptions)
- Common real-world usage patterns

### 4. Lint and format

Before finishing, fix all lint and type errors:

```bash
uv run ruff check --fix yoink_<PACKAGE>/tests/generated/
uv run ruff format yoink_<PACKAGE>/tests/generated/
uv run ty check yoink_<PACKAGE>/tests/generated/
```

## Output

Emit your output as a JSON code block matching this schema:

```json
{
  "tests_written": { "type": "integer", "description": "How many tests were written" },
  "test_files": { "type": "array", "items": { "type": "string" }, "description": "Which test file(s) were created (list paths)" },
  "summary": { "type": "string", "description": "Brief summary of test coverage (categories: happy path, edge cases, errors, etc.)" }
}
```
