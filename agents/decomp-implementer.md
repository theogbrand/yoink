---
name: decomp-implementer
description: "Implement or replace a dependency in diy_<package>/ based on a decomposition evaluation. Use during dependency decomposition (phase 1) after evaluation."
tools: Read, Grep, Glob, Bash, Write, Edit
---

# Decomposition Implementer

Read the file `.claude/inner-diy-loop.local.md` and follow its instructions.

## Input

None

## Output

- **completion_promise**: `DONE` or `MAX_ITERATIONS_REACHED`
- **what_was_done**: Summary of changes
- **new_imports**: List of external libraries that diy_<package>/ now imports as a result
