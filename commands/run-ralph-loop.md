---
description: "Run an inner ralph loop to build a diy replacement for a sub-dependency"
argument-hint: "--context CONTEXT_FILE --top-package PACKAGE --sub-package LIBRARY [--max-iterations N]"
---

# Run Ralph Loop

**Prerequisite:** `/test-curate` must have been completed first (curated test suite exists and passes against the real library). A decomposition context file (JSON or markdown evaluation output) must exist — see `examples/` for format.

1. Generate the inner ralph loop prompt:

```bash
uv run inner_ralph.py generate-prompt $ARGUMENTS
```

2. Spawn a subagent using the Agent tool with the generated prompt as the task. The agent will:
   - Verify baseline tests pass with the real sub-package
   - Rewrite imports to point at the DIY replacement
   - Iteratively build `diy_<sub_package>/` until all Level 0 tests pass
   - Commit each improvement and revert regressions
   - Exit when score == 1.0 or max iterations reached
