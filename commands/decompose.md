---
description: "Phase 1: Dependency decomposition"
argument-hint: "--package PACKAGE_NAME"
---

# Decompose

**Prerequisite:** `/test-curate` must have been completed first.

Seed the decomposition queue with the target package:

```bash
uv run python scripts/decomp.py enqueue <PACKAGE>
```

Then read and follow `${CLAUDE_PLUGIN_ROOT}/docs/decomposition/decomposition-orchestrator.md` until the queue is empty.
