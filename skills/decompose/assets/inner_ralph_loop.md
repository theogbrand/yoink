# Inner Decomposition Implementer — Build diy_{sub_package}/

Your goal is to build `diy_{sub_package}/` — a from-scratch replacement for `{sub_package}`. Success means the `diy_{top_package}/` test suite passes entirely against your implementation.

## Context

| Field | Value |
|---|---|
| Top-level package | `{top_package}` |
| Sub-package to build | `{sub_package}` |
| Category | {category} |
| Decomposition strategy | {strategy} |
| Functions to replace | {functions_to_replace} |
| Reference material | `{reference_material}` |
| Acceptable sub-dependencies | {acceptable_sub_dependencies} |
| Max iterations | {max_iterations} |

## Rules

- **One level only:** decompose to the immediate next layer down (e.g., orchestration layer -> underlying SDKs, API wrapper -> raw HTTP). Do NOT skip levels
- Use the context material above to guide your implementation
- **ONLY edit files within `diy_{sub_package}/`**
- Never modify `diy_{top_package}/`, test files, or `.slash_diy/`
- **Allowed imports:** stdlib and the acceptable sub-dependencies listed above. Do not import anything else

## Steps

Repeat steps 1–3 until all tests pass or you hit the max iteration limit.

### 1. Plan
- List `.claude/decomp-implementer-loop/{sub_package}-iteration-*-run.log` and find the highest existing N. You are now on iteration N+1 — use that number as `<N>` for this cycle's log files.
- Read current `diy_{sub_package}/` source files
- Study the failing tests to understand what's needed:
  ```
  uv run pytest diy_{top_package}/tests/generated/ -x --tb=short 2>&1
  ```

### 2. Implement

- Modify files in `diy_{sub_package}/` **ONLY**.
- Focus on the specific failures identified in step 1.

### 3. Validate

Run the test suite and check score:

```
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/run_tests.py > .claude/decomp-implementer-loop/{sub_package}-iteration-<N>-run.log 2>&1
grep "^score:" .claude/decomp-implementer-loop/{sub_package}-iteration-<N>-run.log >> .claude/decomp-implementer-loop/{sub_package}-scores.log
grep -E "^(score|passed|failed):" .claude/decomp-implementer-loop/{sub_package}-iteration-<N>-run.log
```

- If `score == 1.000000`, keep commit, then emit `<promise>DONE</promise>`.
- If iteration-<N> == {max_iterations}, emit `<promise>MAX_ITERATIONS_REACHED</promise>`.

---

**CRITICAL: After committing your final passing state, you MUST emit a completion signal. Do NOT exit the loop silently.**

- `<promise>DONE</promise>` — emit **only** when all tests pass completely and unequivocally. Do not output false promises to escape the loop, even if you feel stuck or think you should exit for other reasons. The loop is designed to continue until genuine completion.
- `<promise>MAX_ITERATIONS_REACHED</promise>` — emit if you hit the max iteration limit without full test passage.