# Decomposition Orchestrator

**Purpose:** Drive the queue through decomposition evaluation, implementation, and validation.

Each item in the queue is a library name. The goal is to decompose one abstraction layer at a time.

## Steps

1. **Dequeue** — `uv run python scripts/decomp.py dequeue`
   - If queue is empty: decomposition complete, stop.
   - Otherwise: continue to step 2.

2. **Evaluate** — Follow [dependency-decomposition-workflow.md](dependency-decomposition-workflow.md)
   - **Keep** → go back to step 1.
   - **Decompose** → continue to step 3.

3. **Implement** — Implement or replace the dequeued item in `diy_<package>/`:
   - If this is the first item (the target package itself): build the initial implementation using whatever libraries the decomposition strategy identifies as the next layer down.
   - If this is a sub-dependency from a previous pass: replace its usage in `diy_<package>/` with the next-layer-down alternative.
   - **One level only**: decompose to the immediate next layer down (e.g., orchestration layer → underlying SDKs, API wrapper → raw HTTP). Do NOT skip levels.
   - Use the reference material identified by the evaluation (API docs for wrappers, library source for orchestration layers).

4. **Validate** — Run the test suite to confirm nothing broke:
   ```bash
   uv run .claude/plugins/slash-diy/run_tests.py > run.log 2>&1
   grep "^score:\|^passed:\|^failed:" run.log
   ```
   - Tests must pass at the same level or better than before.
   - If tests fail, fix the implementation before proceeding.
   - Commit the working implementation: `git add diy_<package>/ && git commit -m "decomp: <description of what was implemented/replaced>"`

5. **Enqueue what the new code depends on** — Enqueue the external libraries that `diy_<package>/` now imports as a result of this implementation:
   ```bash
   uv run python scripts/decomp.py enqueue <lib1> <lib2> ...
   ```
   Only enqueue what `diy_<package>/` actually imports — not the full dependency tree of the original library. Use `uv run python scripts/decomp.py deps <library>` to see a library's pip dependencies as reference.

6. **Repeat** — Go back to step 1.
