#!/bin/bash

# Subagent Start Hook
# Logs subagent start events to .claude/yoink-subagent.log

set -euo pipefail

# Read hook input from stdin
HOOK_INPUT=$(cat)

LOG_FILE=".claude/yoink-subagent.log"

echo "$HOOK_INPUT" | jq -c '{ts: now | todate, event: "START", agent_type, agent_id}' >> "$LOG_FILE"

exit 0
