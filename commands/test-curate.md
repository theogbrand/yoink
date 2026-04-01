---
description: "Phase 0: Generate and discover tests, validate against real library"
argument-hint: "PROMPT --package PACKAGE_NAME"
disable-model-invocation: true
---

# Test Curate

**Prerequisite:** `/setup` must have been run first (reference dir and real library must exist).

Parse your prompt to identify:
- **Package name**: from the `Package:` line or `--package` argument
- **Target function/feature**: from the `Task:` line or prompt body

> **Naming convention**: `diy_<package>/` where `<package>` has hyphens replaced
> by underscores (e.g., package `litellm` -> `diy_litellm/`).

---

### 1. Discover relevant tests

Use the **test-discoverer** agent to search for relevant tests from the original library's test suite.

Pass it the package name and target function.

**Wait for this agent to complete before proceeding to step 2.**

### 2. Generate focused tests

Use the **test-generator** agent to write original pytest tests for the target function.

Pass it the package name and target function.

### 3. Validate tests against the real library

Run the generated tests against the pip-installed real library:

```bash
uv run pytest diy_<PACKAGE>/tests/generated/ -v --tb=short 2>&1
```

**Prune failures:**
- For each failing test file, decide: is this a bad test or an env issue?
- Delete test files that fail due to missing API keys, network issues, or
  dependencies on the full library that we can't satisfy
- Re-run until all remaining tests pass
- If **zero tests survive** then **abort** -- output an error explaining the situation.

Print a summary:
```
Test validation results:
  Generated: X/Y passed (removed: list of removed files)
  Total surviving tests: N
```

### 4. Rewrite imports

After validation passes, rewrite imports in generated tests so they target `diy_<package>/`:

```bash
uv run ${CLAUDE_PLUGIN_ROOT}/rewrite_imports.py --package <PACKAGE>
```

### 5. Sanity check

Run the test suite against the empty `diy_<package>/` to confirm tests fail:

```bash
uv run ${CLAUDE_PLUGIN_ROOT}/run_tests.py > run.log 2>&1
grep "^score:" run.log
```

Score should be ~0.0 (tests should fail against empty `diy_<package>/`). If score > 0,
something is wrong -- investigate before proceeding.
