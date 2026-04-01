---
description: "Curate tests then decompose dependencies"
argument-hint: "PROMPT [--url GITHUB_URL] [--package PACKAGE_NAME]"
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh:*)"]
disable-model-invocation: true
---

# DIY Decomp

Execute the setup script to scaffold the project:

```!
"${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh" $ARGUMENTS
```

IMPORTANT: After the setup script runs, print its full output to the user verbatim.

Parse your prompt to identify:
- **Package name**: from the `Package:` line or `--package` argument
- **Target function/feature**: from the `Task:` line or prompt body

> **Naming convention**: `diy_<package>/` where `<package>` has hyphens replaced
> by underscores (e.g., package `litellm` -> `diy_litellm/`).

---

## Phase 0: Test Curation

**You MUST complete this phase before proceeding to Phase 1.**

### 1. Discover relevant tests

Use the **test-discoverer** agent. Pass it the package name and target function.

**Wait for this agent to complete before proceeding.**

### 2. Generate focused tests

Use the **test-generator** agent. Pass it the package name and target function.

### 3. Validate tests against the real library

```bash
uv run pytest diy_<PACKAGE>/tests/generated/ -v --tb=short 2>&1
```

Prune failures: delete tests that fail due to missing API keys, network issues, or
dependencies on the full library. Re-run until all remaining tests pass.

- If **zero tests survive** then **abort**.

### 4. Rewrite imports

```bash
uv run ${CLAUDE_PLUGIN_ROOT}/rewrite_imports.py --package <PACKAGE>
```

### 5. Sanity check

```bash
uv run ${CLAUDE_PLUGIN_ROOT}/run_tests.py > run.log 2>&1
grep "^score:" run.log
```

Score should be ~0.0. If score > 0, investigate before proceeding.

---

## Phase 1: Dependency Decomposition

Seed the queue with the target package:

```bash
uv run python ${CLAUDE_PLUGIN_ROOT}/scripts/decomp.py enqueue <PACKAGE>
```

**Begin loop.** Repeat until the queue is empty.

### 1. Dequeue

```bash
uv run python ${CLAUDE_PLUGIN_ROOT}/scripts/decomp.py dequeue
```

- If **queue is empty** then **stop, decomposition complete**.

### 2. Evaluate

Use the **decomp-evaluator** agent. Pass it the library name and diy package name.

- If **Keep** then **go back to step 1**.
- If **Decompose** then **continue to step 3**.

### 3. Implement

a. Save the **decomp-evaluator** output from step 2 to `.claude/decomp_context.md`. The file must
contain the evaluator's full Decompose decision (Decision, Reasoning, Category, Strategy,
Functions to replace, Reference material, Acceptable sub-dependencies).

b. Pre-flight Checks

Complete these steps IN ORDER before entering the loop.

### 1. Verify baseline

Run Level 0 tests with the REAL `{sub_package}` still installed:

```bash
uv run pytest diy_{top_package}/tests/ -v --tb=short 2>&1
```

**All tests MUST pass.** If any fail, STOP — the baseline is broken and must be fixed before proceeding.

### 2. Rewrite imports

Swap `{sub_package}` imports in `diy_{top_package}/` source code to point at `diy_{sub_package}`:

```bash
uv run inner_ralph.py rewrite-sub-imports --sub-package {sub_package} --target-dir diy_{top_package}
```

### 3. Scaffold the sub-package

```bash
mkdir -p diy_{sub_package}
touch diy_{sub_package}/__init__.py
```

### 4. Initialize tracking

```bash
echo -e "commit\tscore\tpassed\tfailed\ttotal\tdescription" > results.tsv
uv run run_tests.py > run.log 2>&1
grep "^score:\|^passed:\|^failed:\|^total:" run.log
```

Record baseline (score should be ~0 after the import swap).

c. Execute the setup script to initialize the inner DIY loop with the decomp context:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/activate-inner-diy-loop.sh" \
    --context decomp_context.md \
    --package <PACKAGE> \
    --sub-package <LIBRARY> \
    --max-iterations 10 \
```

# TODO: add the SubAgent Stop Hook to call inner-diy-loop-stop-hook.sh and tie it to the decomp-implementer agent 
You can only move to step 4 when you have recieved the COMPLETION PROMISE (<promise>DONE</promise>) from the SubAgent. If a subagent determines that the task is done but does not return the completion promise, spin up a new subagent to continue the task.

# TODO: Prompt created in step (b) should contain all the args needed at each subagent loop iteration
<!-- c. Pass the generated prompt from step (b) to the **decomp-implementer** agent to run the inner ralph loop until all Level 0 tests pass or max iterations are reached.

The inner ralph loop will:
- Verify baseline tests pass with the real library
- Rewrite imports to point at the DIY replacement
- Iteratively build `diy_<LIBRARY>/` until all Level 0 tests pass
- Commit each improvement and revert regressions -->

# TODO: rewrite imports from old library to newly written library
d. After the subagent finishes and exits with a completion promise, discover new external imports:
```bash
grep -rh "^from \|^import " diy_<PACKAGE>/ --include="*.py" | sort -u
```

### 4. Enqueue

```bash
uv run python ${CLAUDE_PLUGIN_ROOT}/scripts/decomp.py enqueue <new imports from implementer>
```

**Loop back to step 1.**
