# Decomposition Orchestrator

**Purpose:** Drive the queue through decomposition evaluation.

**Steps:**

1. **Dequeue** — `python scripts/decomp.py dequeue`
   - If queue is empty: decomposition complete, stop
   - Otherwise: continue to step 2

2. **Evaluate** — Follow `dependency-decomposition-workflow.md`

3. **Record decision:**
   - **Keep:** nothing (library is retained)
   - **Decompose:** `python scripts/decomp.py enqueue <library>` (discovers subdeps)

4. **Repeat** — Go back to step 1
