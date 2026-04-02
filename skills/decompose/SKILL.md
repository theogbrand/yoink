---
name: decompose
description: "Phase 1: Dependency decomposition. Only invoke when explicitly requested by the user or by the diy-decomp orchestrator."
argument-hint: "--package PACKAGE_NAME"
---

# Decompose

> **Do not invoke this skill unless explicitly requested.** It is called by `/diy-decomp` or run standalone by the user.

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

- If **queue is empty** then **stop, decomposition complete**.

### 2. Evaluate

Use the **decomp-evaluator** agent to evaluate whether the dequeued library should be kept or decomposed.

Pass it the library name and the diy package name (e.g., `diy_litellm`).

- If **Keep** then **go back to step 1**.
- If **Decompose** then **continue to step 3** with the evaluation output.

### 3. Implement & Validate

a. Save the **decomp-evaluator** output from step 2 to `.claude/decomp_context.md`. The file must
contain the evaluator's full Decompose decision (Decision, Reasoning, Category, Strategy,
Functions to replace, Reference material, Acceptable sub-dependencies).

b. Pre-flight Checks

Complete these steps IN ORDER before entering the loop.

#### 1. Verify baseline

Run Level 0 tests with the REAL `{sub_package}` still installed:

```bash
uv run pytest diy_{top_package}/tests/ -v --tb=short 2>&1
```

**All tests MUST pass.** If any fail, STOP — the baseline is broken and must be fixed before proceeding.

#### 2. Rewrite imports

Swap `{sub_package}` imports in `diy_{top_package}/` source code to point at `diy_{sub_package}`:

```bash
uv run inner_ralph.py rewrite-sub-imports --sub-package {sub_package} --target-dir diy_{top_package}
```

#### 3. Scaffold the sub-package

```bash
mkdir -p diy_{sub_package}
touch diy_{sub_package}/__init__.py
```

#### 4. Initialize tracking

```bash
echo -e "commit\tscore\tpassed\tfailed\ttotal\tdescription" > results.tsv
uv run run_tests.py > run.log 2>&1
grep "^score:\|^passed:\|^failed:\|^total:" run.log
```

Record baseline (score should be ~0 after the import swap).

c. Execute this setup script to initialize the prompt for the **decomp-implementer** agent:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/activate-inner-diy-loop.sh" \
    --context decomp_context.md \
    --package <PACKAGE> \
    --sub-package <LIBRARY> \
    --max-iterations 10 \
```

d. Use the **decomp-implementer** agent to implement the sub-package.

You MUST only move to step 4 when you have recieved the COMPLETION PROMISE (<promise>DONE</promise>) from the **decomp-implementer** agent. If a **decomp-implementer** agent exits but does not return you the completion promise (<promise>DONE</promise>), spin up a new **decomp-implementer** agent to continue the task.

If the **decomp-implementer** agent returns the completion promise `<promise>MAX ITERATIONS REACHED</promise>`, stop the loop and report back to the user that the maximum number of iterations has been reached.

### 4. Enqueue new dependencies

Using the "New imports" from the implementer's report, enqueue external libraries that `diy_<PACKAGE>/` now depends on:

```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/decomp.py enqueue <lib1> <lib2> ...
```

Only enqueue what `diy_<PACKAGE>/` actually imports -- not the full dependency tree of the original library. Use `uv run python ${CLAUDE_SKILL_DIR}/scripts/decomp.py deps <library>` to see a library's pip dependencies as reference.

**Loop back to step 1.**
