---
name: decomp-implementer
description: "Implement or replace a dependency in the yoink package directory based on a decomposition evaluation. Use during dependency decomposition (phase 3) after evaluation."
---

# Decomposition Implementer — Build yoink_{sub_package}/

Read `.claude/inner-yoink-loop.local.md` for your runtime input variables. Your goal is to build `yoink_{sub_package}/` — a from-scratch replacement for `{sub_package}`. Success means the `yoink_{top_package}/` test suite passes entirely against your implementation.

## Input

Read from `.claude/inner-yoink-loop.local.md` (JSON code block after YAML frontmatter):

> **Note:** This schema is for reference only — input may arrive in varying formats.

```json
{
  "top_package": { "type": "string", "description": "The top-level package being decomposed" },
  "sub_package": { "type": "string", "description": "The sub-package to build a replacement for" },
  "category": { "type": "string", "enum": ["API wrapper", "orchestration layer", "utility", "framework"], "description": "Classification of the library" },
  "strategy": { "type": "string", "description": "What to replace it with and how" },
  "functions_to_replace": { "type": "array", "items": { "type": "string" }, "description": "Specific functions/classes used by yoink_{top_package}/" },
  "reference_material": { "type": "string", "description": "API docs URL or library source path" },
  "acceptable_sub_dependencies": { "type": "array", "items": { "type": "string" }, "description": "What lower-level deps are OK to introduce" },
  "max_iterations": { "type": "integer", "description": "Maximum loop iterations before auto-stop" }
}
```

## Rules

- **Implement real functionality.** Your replacement must do what the original library actually does — make real HTTP calls, parse real responses, handle real errors. Do not implement stubs, mock helpers, or test-mode-only logic. If the tests use mocks, look past the mocks to understand what real behavior is being tested
- **One level only:** decompose to the immediate next layer down (e.g., orchestration layer -> underlying SDKs, API wrapper -> raw HTTP). Do NOT skip levels
- Use your input variables to guide your implementation
- **ONLY edit files within `yoink_{sub_package}/`**
- Never modify `yoink_{top_package}/`, test files, or `.yoink/`
- **Allowed imports:** stdlib and the acceptable sub-dependencies from your input. Do not import anything else

## Steps

Repeat steps 1–3 until all tests pass or you hit the max iteration limit.

### 1. Plan

- List `.claude/decomp-implementer-loop/{sub_package}-iteration-*-run.log` and find the highest existing N. You are now on iteration N+1 — use that number as `<N>` for this cycle's log files.
- Read current `yoink_{sub_package}/` source files
- Study the failing tests to understand what's needed:
  ```
  uv run ${CLAUDE_PLUGIN_ROOT}/scripts/run_tests.py --project-dir . 2>&1
  ```

### 2. Implement

- Modify files in `yoink_{sub_package}/` **ONLY**.
- Focus on the specific failures identified in step 1.
- Fix all lint and type errors and warnings:
  ```
  uv run ruff check --fix yoink_{sub_package}/
  uv run ruff format yoink_{sub_package}/
  uv run ty check yoink_{sub_package}/
  ```

### 3. Validate

Run the test suite and check score:

```
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/run_tests.py --project-dir . > .claude/decomp-implementer-loop/{sub_package}-iteration-<N>-run.log 2>&1
grep "^score:" .claude/decomp-implementer-loop/{sub_package}-iteration-<N>-run.log | tee -a .claude/decomp-implementer-loop/{sub_package}-scores.log
```

- If **score == 1.000000** then **keep commit, then emit `<promise>DONE</promise>`**.
- If **iteration-\<N\> == max_iterations** then **emit `<promise>MAX_ITERATIONS_REACHED</promise>`**.

---

**CRITICAL: After committing your final passing state, you MUST emit a completion signal. Do NOT exit the loop silently.**

- `<promise>DONE</promise>` — emit **only** when all tests pass completely and unequivocally. Do not output false promises to escape the loop, even if you feel stuck or think you should exit for other reasons. The loop is designed to continue until genuine completion.
- `<promise>MAX_ITERATIONS_REACHED</promise>` — emit if you hit the max iteration limit without full test passage.

## Output

Emit your output as a JSON code block matching this schema:

```json
{
  "completion_promise": { "type": "string", "enum": ["DONE", "MAX_ITERATIONS_REACHED"], "description": "Whether the implementation completed successfully or hit the iteration limit" },
  "what_was_done": { "type": "string", "description": "Summary of changes made" },
  "new_imports": { "type": "array", "items": { "type": "string" }, "description": "External libraries that yoink_{sub_package}/ now imports" }
}
```
