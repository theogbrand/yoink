#!/bin/bash

# Subagent Stop Hook
# Logs subagent stop events with input/output to .claude/slash-diy-subagent.log
# Writes decomp-evaluator output to .claude/decomp_context.md

set -euo pipefail

# Read hook input from stdin
HOOK_INPUT=$(cat)

LOG_FILE=".claude/slash-diy-subagent.log"

# Extract the first user message from the transcript as the agent's input prompt
TRANSCRIPT_PATH=$(echo "$HOOK_INPUT" | jq -r '.agent_transcript_path')
AGENT_INPUT=$(head -n1 "$TRANSCRIPT_PATH" | jq -r '.message.content')

echo "$HOOK_INPUT" | jq -c --arg input "$AGENT_INPUT" \
  '{ts: now | todate, event: "STOP", agent_type, agent_id, input: $input, output: .last_assistant_message}' \
  >> "$LOG_FILE"

# If this is the decomp-evaluator agent, write its output to .claude/decomp_context.md
AGENT_TYPE=$(echo "$HOOK_INPUT" | jq -r '.agent_type')
if [[ "$AGENT_TYPE" == "decomp-evaluator" || "$AGENT_TYPE" == *":decomp-evaluator" ]]; then
  mkdir -p .claude
  echo "$HOOK_INPUT" | jq -r '.last_assistant_message' > .claude/decomp_context.md
fi

exit 0
