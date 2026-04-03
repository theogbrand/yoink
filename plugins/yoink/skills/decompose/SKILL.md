---
name: decompose
description: "Phase 1: Dependency decomposition. Only invoke when explicitly requested by the user or by the yoink orchestrator."
argument-hint: "--package PACKAGE_NAME"
---

# Decompose

> **Do not invoke this skill unless explicitly requested.** It is called by `/yoink` or run standalone by the user.

**Prerequisite:** `/test-curate` must have been completed first.

Seed the decomposition queue with the target package:

```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/decomp.py enqueue <PACKAGE>
```

Then run the decomposition loop below until the queue is empty.

---

## Decomposition Loop

**Begin loop.** Repeat until the queue is empty.

### 1. Dequeue

```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/decomp.py dequeue
```

- If **queue is empty** then **decomposition complete, remove the real library and stop**.
  ```bash
  uv remove <PACKAGE>
  ```

### 2. Evaluate

Use the **decomp-evaluator** agent to evaluate whether the dequeued library should be kept or decomposed.

Pass it the library name and the yoink package name (e.g., `yoink_litellm`).

- If **Keep** then **go back to step 1**.
- If **Decompose** then **continue to step 3** with the evaluation output.

### 3. Prepare the sub-package for the implementer agent

Complete these steps IN ORDER before entering the loop.

#### a. Verify baseline

Run the top-level generated tests with the REAL `{sub_package}` still installed:

```bash
uv run pytest yoink_{top_package}/tests/generated/ -v --tb=short 2>&1
```

**All tests MUST pass.** If any fail, STOP — the baseline is broken and must be fixed before proceeding.

#### b. Rewrite imports

Swap `{sub_package}` imports in `yoink_{top_package}/` source code to point at `yoink_{sub_package}`:

```bash
uv run inner_ralph.py rewrite-sub-imports --sub-package {sub_package} --target-dir yoink_{top_package}
```

#### c. Scaffold the sub-package

```bash
mkdir -p yoink_{sub_package}
touch yoink_{sub_package}/__init__.py
```

#### d. Seed & populate state body

Seed the state file with placeholder values:

```bash
"${CLAUDE_SKILL_DIR}/scripts/activate-inner-yoink-loop.sh" --max-iterations 10
```

#### e. Read `.claude/decomp_context.md` and fill in the `PLACEHOLDER` values in `.claude/inner-yoink-loop.local.md`:

| Field | Where to get the value |
|---|---|
| top_package | `{top_package}` |
| sub_package | `{sub_package}` |
| category | from decomp_context |
| strategy | from decomp_context |
| functions_to_replace | comma-separated list from decomp_context, or `none identified` |
| reference_material | from decomp_context, default: `.yoink/reference/{sub_package}/` |
| acceptable_sub_dependencies | comma-separated list from decomp_context, or `none` |

### 4. Implement & Validate

Use the **decomp-implementer** agent to implement the sub-package.

You MUST only move to step 4 when you have received **completion_promise** = `DONE` from the **decomp-implementer** agent. If a **decomp-implementer** agent exits without returning `DONE`, spin up a new **decomp-implementer** agent to continue the task.

If the **decomp-implementer** agent returns **completion_promise** = `MAX_ITERATIONS_REACHED`, stop the loop and report back to the user that the maximum number of iterations has been reached.

### 5. Enqueue new dependencies

Using **new_imports** from the implementer's output, enqueue external libraries that `yoink_<PACKAGE>/` now depends on:

```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/decomp.py enqueue <lib1> <lib2> ...
```

Only enqueue what `yoink_<PACKAGE>/` actually imports -- not the full dependency tree of the original library. Use `uv run python ${CLAUDE_SKILL_DIR}/scripts/decomp.py deps <library>` to see a library's pip dependencies as reference.

**Loop back to step 1.**
