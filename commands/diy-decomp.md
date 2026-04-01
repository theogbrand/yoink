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

Use the **decomp-implementer** agent. Pass it the library name, diy package name, and evaluation output.

### 4. Enqueue

```bash
uv run python ${CLAUDE_PLUGIN_ROOT}/scripts/decomp.py enqueue <new imports from implementer>
```

**Loop back to step 1.**
