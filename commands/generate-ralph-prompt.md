---
description: "Generate an inner ralph loop prompt from a decomposition context"
argument-hint: "--context CONTEXT_FILE --top-package PACKAGE --sub-package LIBRARY [--max-iterations N]"
---

# Generate Ralph Prompt

**Prerequisite:** `/test-curate` must have been completed first (curated test suite exists and passes against the real library). A decomposition context file (JSON or markdown evaluation output) must exist — see `examples/` for format.

Generate the inner ralph loop prompt:

```bash
uv run inner_ralph.py generate-prompt $ARGUMENTS
```

This outputs a complete, self-contained prompt that includes pre-flight steps (baseline verification, import rewriting, scaffolding) and the iterative loop instructions. The `--context` flag accepts JSON or markdown — format is auto-detected.

Print the generated prompt to the user.
