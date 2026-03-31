---
description: "Curate tests then decompose dependencies"
argument-hint: "PROMPT [--url GITHUB_URL] [--package PACKAGE_NAME]"
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh:*)"]
---

# Decomp Only

Execute the setup script to scaffold the project:

```!
"${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh" $ARGUMENTS
```

IMPORTANT: After the setup script runs, print its full output to the user verbatim.

First, read `${CLAUDE_PLUGIN_ROOT}/docs/STRUCTURE.md` to understand the documentation layout. Then follow these two phases in order.

---

## Phase 0: Test Curation

**You MUST complete this phase before proceeding to Phase 1.**

Read and follow the instructions in `${CLAUDE_PLUGIN_ROOT}/docs/phase-0-test-curation.md`.

---

## Phase 1: Dependency Decomposition

After Phase 0 is complete, seed the queue with the target package itself — this is the first thing to be implemented and decomposed:

```bash
uv run python scripts/decomp.py enqueue <PACKAGE>
```

Then read and follow `${CLAUDE_PLUGIN_ROOT}/docs/decomposition/decomposition-orchestrator.md` until the queue is empty.
