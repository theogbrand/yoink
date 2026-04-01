---
name: decompose
description: "Phase 1: Dependency decomposition. Only invoke when explicitly requested by the user or by the diy-decomp orchestrator."
argument-hint: "--package PACKAGE_NAME"
hooks:
  SubagentStart:
    - hooks:
        - type: command
          command: "echo \"[$(date -u +%Y-%m-%dT%H:%M:%SZ)] START $(echo $CLAUDE_HOOK_EVENT | jq -c '{tool: .tool_name, input: .tool_input}')\" >> .claude/decompose-subagent.log"
  SubagentStop:
    - hooks:
        - type: command
          command: "echo \"[$(date -u +%Y-%m-%dT%H:%M:%SZ)] STOP  $(echo $CLAUDE_HOOK_EVENT | jq -c '{tool: .tool_name, output: .tool_output}')\" >> .claude/decompose-subagent.log"
---

# Decompose

> **Do not invoke this skill unless explicitly requested.** It is called by `/diy-decomp` or run standalone by the user.

**Prerequisite:** `/test-curate` must have been completed first.

Seed the decomposition queue with the target package:

```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/decomp.py enqueue <PACKAGE>
```

Then run the decomposition loop below until the queue is empty.

---

## Decomposition Loop

**Begin loop.** Repeat until the queue is empty.

### 1. Dequeue

```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/decomp.py dequeue
```

- If **queue is empty** then **stop, decomposition complete**.

### 2. Evaluate

Use the **decomp-evaluator** agent to evaluate whether the dequeued library should be kept or decomposed.

Pass it the library name and the diy package name (e.g., `diy_litellm`).

- If **Keep** then **go back to step 1**.
- If **Decompose** then **continue to step 3** with the evaluation output.

### 3. Implement & Validate

Use the **decomp-implementer** agent to implement the replacement.

Pass it the library name, the diy package name, and the full evaluation output from step 2.

### 4. Enqueue new dependencies

Using the "New imports" from the implementer's report, enqueue external libraries that `diy_<PACKAGE>/` now depends on:

```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/decomp.py enqueue <lib1> <lib2> ...
```

Only enqueue what `diy_<PACKAGE>/` actually imports -- not the full dependency tree of the original library. Use `uv run python ${CLAUDE_SKILL_DIR}/scripts/decomp.py deps <library>` to see a library's pip dependencies as reference.

**Loop back to step 1.**
