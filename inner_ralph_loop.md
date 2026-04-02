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

Repeat steps 1–4 until all tests pass or you hit the max iteration limit.

```
BEFORE=$(git rev-parse HEAD)
```

### 1. Plan

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
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/run_tests.py > run.log 2>&1
grep "^score:\|^passed:\|^failed:" run.log
```

### 4. Commit or revert

```
git add diy_{sub_package}/
git diff --cached --quiet && { echo "no changes — go back to step 1"; }
git commit -m "decomp-implementer-loop-{sub_package}-iteration-<N>: <description of what was implemented/replaced>"
```

- If score **improved** → keep commit, append to results.tsv, go back to step 1.
- If score **same or worse** → revert and go back to step 1:
  ```
  [[ "$(git rev-parse HEAD)" != "$BEFORE" ]] && git reset --hard "$BEFORE"
  ```
- If `score == 1.000000`, keep commit, then emit `<promise>DONE</promise>`.
- If iteration-<N> == {max_iterations}, emit `<promise>MAX ITERATIONS REACHED</promise>`.

---

**CRITICAL: After committing your final passing state, you MUST emit a completion signal. Do NOT exit the loop silently.**

- `<promise>DONE</promise>` — emit **only** when all tests pass completely and unequivocally. Do not output false promises to escape the loop, even if you feel stuck or think you should exit for other reasons. The loop is designed to continue until genuine completion.
- `<promise>MAX ITERATIONS REACHED</promise>` — emit if you hit the max iteration limit without full test passage.