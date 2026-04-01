# Decomposition Orchestrator

**Purpose:** Drive the queue through decomposition evaluation, implementation, and validation.

Each item in the queue is a library name. The goal is to decompose one abstraction layer at a time.

## Steps

1. **Dequeue** — `uv run python scripts/decomp.py dequeue`
   - If queue is empty: decomposition complete, stop.
   - Otherwise: continue to step 2.

2. **Evaluate** — Spawn a subagent using the Agent tool with this task:

   ```
   Evaluate whether <LIBRARY> should be kept or decomposed from diy_<PACKAGE>/.

   First, read and follow ${CLAUDE_PLUGIN_ROOT}/docs/decomposition/dependency-decomposition-workflow.md.
   It will direct you to the evaluation policy and decomposition strategies docs as needed.

   Then inspect diy_<PACKAGE>/ to understand how <LIBRARY> is actually used — which files
   import it, which functions/classes are called, and how deeply integrated it is.

   Return your verdict in this format:

   **Decision:** Keep | Decompose
   **Reasoning:** <concise explanation>

   If decomposing, also provide:
   **Category:** <API wrapper | orchestration layer | utility | framework>
   **Strategy:** <how to decompose — what to replace it with>
   **Functions to replace:** <specific functions/classes from this library that diy_<PACKAGE>/ uses>
   **Reference material:** <where to look when implementing — API docs URL, library source path, etc.>
   **Acceptable sub-dependencies:** <what kinds of lower-level deps are OK to introduce>
   ```

   - **Keep** → go back to step 1.
   - **Decompose** → continue to step 3 with the evaluation output.

3. **Implement & Validate (Inner Ralph Loop)** — Save the evaluation output and run an inner ralph loop:

   a. Save the evaluation output from step 2 to a file:
   ```bash
   cat > decomp_context.md << 'EVAL'
   <PASTE EVALUATION OUTPUT FROM STEP 2>
   EVAL
   ```

   b. Generate the inner ralph prompt:
   ```bash
   uv run inner_ralph.py generate-prompt \
     --context decomp_context.md \
     --top-package <PACKAGE> \
     --sub-package <LIBRARY> \
     --max-iterations 30
   ```

   c. Spawn a subagent using the Agent tool with the generated prompt from step (b) as the task.

   The inner ralph loop will:
   - Verify baseline tests pass with the real library
   - Rewrite imports to point at the DIY replacement
   - Iteratively build `diy_<LIBRARY>/` until all Level 0 tests pass
   - Commit each improvement and revert regressions

   d. After the subagent finishes, discover new external imports:
   ```bash
   grep -rh "^from \|^import " diy_<PACKAGE>/ --include="*.py" | sort -u
   ```

4. **Enqueue new dependencies** — Using the new imports discovered in step 3d, enqueue external libraries that `diy_<PACKAGE>/` now depends on:
   ```bash
   uv run python scripts/decomp.py enqueue <lib1> <lib2> ...
   ```
   Only enqueue what `diy_<PACKAGE>/` actually imports — not the full dependency tree of the original library. Use `uv run python scripts/decomp.py deps <library>` to see a library's pip dependencies as reference.

5. **Repeat** — Go back to step 1.
