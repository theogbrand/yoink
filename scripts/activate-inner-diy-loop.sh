#!/bin/bash

# DIY Loop Setup Script
# Creates state file for in-session DIY loop

set -euo pipefail

# Parse arguments
PROMPT_PARTS=()
MAX_ITERATIONS=0
COMPLETION_PROMISE="DONE"
PACKAGE_NAME=""
CONTEXT_FILE=""
SUB_PACKAGE_NAME=""

# Parse options and positional arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help)
      cat << 'HELP_EOF'
DIY Loop - Interactive self-referential development loop

USAGE:
  /inner-diy-loop [PROMPT...] [OPTIONS]

ARGUMENTS:
  PROMPT...    Initial prompt to start the loop (can be multiple words without quotes)

OPTIONS:
  --context <file>               Decomp context file (from decomp-evaluator output)
  --package <name>               Top-level package name (required with --context)
  --sub-package <name>           Sub-package to build (required with --context)
  --max-iterations <n>           Maximum iterations before auto-stop (default: unlimited)
  --completion-promise '<text>'  Promise phrase (USE QUOTES for multi-word)
  -h, --help                     Show this help message

DESCRIPTION:
  Starts a DIY loop in your CURRENT session. The stop hook prevents
  exit and feeds your output back as input until completion or iteration limit.

  To signal completion, you must output: <promise>YOUR_PHRASE</promise>

  Use this for:
  - Interactive iteration where you want to see progress
  - Tasks requiring self-correction and refinement
  - Learning how DIY works

EXAMPLES:
  /inner-diy-loop Build a todo API --completion-promise 'DONE' --max-iterations 20
  /inner-diy-loop --max-iterations 10 Fix the auth bug
  /inner-diy-loop Refactor cache layer  (runs forever)
  /inner-diy-loop --completion-promise 'TASK COMPLETE' Create a REST API

STOPPING:
  Only by reaching --max-iterations or detecting --completion-promise
  No manual stop - DIY runs infinitely by default!

MONITORING:
  # View current iteration:
  grep '^iteration:' .claude/inner-diy-loop.local.md

  # View full state:
  head -10 .claude/inner-diy-loop.local.md
HELP_EOF
      exit 0
      ;;
    --max-iterations)
      if [[ -z "${2:-}" ]]; then
        echo "❌ Error: --max-iterations requires a number argument" >&2
        echo "" >&2
        echo "   Valid examples:" >&2
        echo "     --max-iterations 10" >&2
        echo "     --max-iterations 50" >&2
        echo "     --max-iterations 0  (unlimited)" >&2
        echo "" >&2
        echo "   You provided: --max-iterations (with no number)" >&2
        exit 1
      fi
      if ! [[ "$2" =~ ^[0-9]+$ ]]; then
        echo "❌ Error: --max-iterations must be a positive integer or 0, got: $2" >&2
        echo "" >&2
        echo "   Valid examples:" >&2
        echo "     --max-iterations 10" >&2
        echo "     --max-iterations 50" >&2
        echo "     --max-iterations 0  (unlimited)" >&2
        echo "" >&2
        echo "   Invalid: decimals (10.5), negative numbers (-5), text" >&2
        exit 1
      fi
      MAX_ITERATIONS="$2"
      shift 2
      ;;
    --package)
      if [[ -z "${2:-}" ]]; then
        echo "❌ Error: --package requires a package name" >&2
        exit 1
      fi
      PACKAGE_NAME="$2"
      shift 2
      ;;
    --context)
      if [[ -z "${2:-}" ]]; then
        echo "❌ Error: --context requires a file path" >&2
        exit 1
      fi
      CONTEXT_FILE="$2"
      shift 2
      ;;
    --sub-package)
      if [[ -z "${2:-}" ]]; then
        echo "❌ Error: --sub-package requires a package name" >&2
        exit 1
      fi
      SUB_PACKAGE_NAME="$2"
      shift 2
      ;;
    *)
      # Non-option argument - collect all as prompt parts
      PROMPT_PARTS+=("$1")
      shift
      ;;
  esac
done

# Join all prompt parts with spaces
PROMPT="${PROMPT_PARTS[*]:-}"

# If --context provided, generate prompt from decomp context via inner_ralph.py
if [[ -n "$CONTEXT_FILE" ]]; then
  PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

  if [[ ! -f "$CONTEXT_FILE" ]]; then
    echo "❌ Error: Context file not found: $CONTEXT_FILE" >&2
    exit 1
  fi
  if [[ -z "$PACKAGE_NAME" ]] || [[ -z "$SUB_PACKAGE_NAME" ]]; then
    echo "❌ Error: --context requires --package and --sub-package" >&2
    exit 1
  fi

  ITER_LIMIT="$MAX_ITERATIONS"
  if [[ "$ITER_LIMIT" -eq 0 ]]; then
    ITER_LIMIT=30
  fi

  PROMPT=$(uv run python "$PLUGIN_ROOT/inner_ralph.py" generate-prompt \
    --context "$CONTEXT_FILE" \
    --top-package "$PACKAGE_NAME" \
    --sub-package "$SUB_PACKAGE_NAME" \
    --max-iterations "$ITER_LIMIT")

  if [[ $? -ne 0 ]] || [[ -z "$PROMPT" ]]; then
    echo "❌ Error: Failed to generate prompt from context" >&2
    exit 1
  fi
  echo "━━━ Generated prompt from decomp context ━━━"
  echo "  Top package: $PACKAGE_NAME"
  echo "  Sub package: $SUB_PACKAGE_NAME"
  echo "  Context file: $CONTEXT_FILE"
  echo "  Max iterations: $ITER_LIMIT"
  echo ""
fi

# Validate prompt is non-empty
if [[ -z "$PROMPT" ]]; then
  echo "❌ Error: No prompt provided" >&2
  echo "" >&2
  echo "   DIY needs a task description to work on." >&2
  echo "" >&2
  echo "   Examples:" >&2
  echo "     /inner-diy-loop Build a REST API for todos" >&2
  echo "     /inner-diy-loop Fix the auth bug --max-iterations 20" >&2
  echo "     /inner-diy-loop --completion-promise 'DONE' Refactor code" >&2
  echo "" >&2
  echo "   For all options: /inner-diy-loop --help" >&2
  exit 1
fi

# Create state file for stop hook (markdown with YAML frontmatter)
mkdir -p .claude

# Quote completion promise for YAML if it contains special chars or is not null
if [[ -n "$COMPLETION_PROMISE" ]] && [[ "$COMPLETION_PROMISE" != "null" ]]; then
  COMPLETION_PROMISE_YAML="\"$COMPLETION_PROMISE\""
else
  COMPLETION_PROMISE_YAML="null"
fi

cat > .claude/inner-diy-loop.local.md <<EOF
---
active: true
iteration: 1
max_iterations: $MAX_ITERATIONS
completion_promise: $COMPLETION_PROMISE_YAML
started_at: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
---

$PROMPT
EOF

# Output setup message
cat <<EOF
🔄 DIY loop activated in this session!

Iteration: 1
Max iterations: $(if [[ $MAX_ITERATIONS -gt 0 ]]; then echo $MAX_ITERATIONS; else echo "unlimited"; fi)
Completion promise: $(if [[ "$COMPLETION_PROMISE" != "null" ]]; then echo "${COMPLETION_PROMISE//\"/} (ONLY output when TRUE - do not lie!)"; else echo "none (runs forever)"; fi)

The stop hook is now active. When you try to exit, the SAME PROMPT will be
fed back to you. You'll see your previous work in files, creating a
self-referential loop where you iteratively improve on the same task.

To monitor: head -10 .claude/inner-diy-loop.local.md

⚠️  WARNING: This loop cannot be stopped manually! It will run infinitely
    unless you set --max-iterations or --completion-promise.

🔄
EOF

# Output the initial prompt if provided
if [[ -n "$PROMPT" ]]; then
  echo ""
  echo "$PROMPT"
fi

# Display completion promise requirements if set
if [[ "$COMPLETION_PROMISE" != "null" ]]; then
  echo ""
  echo "═══════════════════════════════════════════════════════════"
  echo "CRITICAL - DIY Loop Completion Promise"
  echo "═══════════════════════════════════════════════════════════"
  echo ""
  echo "To complete this loop, output this EXACT text:"
  echo "  <promise>$COMPLETION_PROMISE</promise>"
  echo ""
  echo "STRICT REQUIREMENTS (DO NOT VIOLATE):"
  echo "  ✓ Use <promise> XML tags EXACTLY as shown above"
  echo "  ✓ The statement MUST be completely and unequivocally TRUE"
  echo "  ✓ Do NOT output false statements to exit the loop"
  echo "  ✓ Do NOT lie even if you think you should exit"
  echo ""
  echo "IMPORTANT - Do not circumvent the loop:"
  echo "  Even if you believe you're stuck, the task is impossible,"
  echo "  or you've been running too long - you MUST NOT output a"
  echo "  false promise statement. The loop is designed to continue"
  echo "  until the promise is GENUINELY TRUE. Trust the process."
  echo ""
  echo "  If the loop should stop, the promise statement will become"
  echo "  true naturally. Do not force it by lying."
  echo "═══════════════════════════════════════════════════════════"
fi
