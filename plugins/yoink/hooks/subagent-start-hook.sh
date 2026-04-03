#!/bin/bash

# Subagent Start Hook
# Logs subagent start events and injects uv context

set -euo pipefail

# Read hook input from stdin
HOOK_INPUT=$(cat)

LOG_FILE=".claude/yoink-subagent.log"

echo "$HOOK_INPUT" | jq -c '{ts: now | todate, event: "START", agent_type, agent_id}' >> "$LOG_FILE"

# Inject context for subagents to use uv run python
cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "SubagentStart",
    "additionalContext": "Always use `uv run python` instead of `python` directly. This ensures the correct virtual environment and dependencies are used."
  }
}
EOF

exit 0
