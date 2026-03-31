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

3. **Implement & Validate** — Spawn a subagent using the Agent tool with this task:

   ```
   Implement or replace <LIBRARY> in diy_<PACKAGE>/ based on this evaluation:
   <PASTE EVALUATION OUTPUT FROM STEP 2>

   Context:
   - If this is the first item (the target package itself): build the initial implementation
     using whatever libraries the decomposition strategy identifies as the next layer down.
   - If this is a sub-dependency from a previous pass: replace its usage in diy_<PACKAGE>/
     with the next-layer-down alternative.
   - One level only: decompose to the immediate next layer down (e.g., orchestration layer →
     underlying SDKs, API wrapper → raw HTTP). Do NOT skip levels.
   - Use the reference material identified by the evaluation (API docs for wrappers, library
     source for orchestration layers).
   - ONLY edit files within diy_<PACKAGE>/.

   Validation loop:
   1. Read current diy_<PACKAGE>/ source files
   2. Study failing tests: uv run pytest diy_<PACKAGE>/tests/generated/ -x --tb=short 2>&1
   3. Implement changes in diy_<PACKAGE>/
   4. Run the test suite: uv run .claude/plugins/slash-diy/run_tests.py
   5. Repeat until all tests pass

   When done, commit the working implementation:
     git add diy_<PACKAGE>/ && git commit -m "decomp: <description of what was implemented/replaced>"

   Then report back:
   - **What was done:** <summary of changes>
   - **New imports:** <list of external libraries that diy_<PACKAGE>/ now imports as a result>
   ```

4. **Enqueue new dependencies** — Using the "New imports" from the implementation subagent, enqueue external libraries that `diy_<PACKAGE>/` now depends on:
   ```bash
   uv run python scripts/decomp.py enqueue <lib1> <lib2> ...
   ```
   Only enqueue what `diy_<PACKAGE>/` actually imports — not the full dependency tree of the original library. Use `uv run python scripts/decomp.py deps <library>` to see a library's pip dependencies as reference.

5. **Repeat** — Go back to step 1.
