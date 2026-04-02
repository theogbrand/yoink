#!/bin/bash

# DIY Loop Setup Script
# Creates state file for in-session DIY loop

set -euo pipefail

# Parse arguments
MAX_ITERATIONS=0
PACKAGE_NAME=""
CONTEXT_FILE=""
SUB_PACKAGE_NAME=""

# Parse options
while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help)
      cat << 'HELP_EOF'
DIY Loop - Interactive self-referential development loop

USAGE:
  /inner-diy-loop [OPTIONS]

OPTIONS:
  --context <file>               Decomp context file (from decomp-evaluator output)
  --package <name>               Top-level package name
  --sub-package <name>           Sub-package to build
  --max-iterations <n>           Maximum iterations before auto-stop (default: unlimited)
  -h, --help                     Show this help message

DESCRIPTION:
  Starts a DIY loop in your CURRENT session. The stop hook prevents
  exit and feeds your output back as input until completion or iteration limit.

  To signal completion, output: <promise>DONE</promise>

EXAMPLES:
  /inner-diy-loop --context decomp_context.md --package requests --sub-package urllib3 --max-iterations 10

STOPPING:
  Only by reaching --max-iterations or detecting <promise>DONE</promise>
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
      echo "❌ Error: Unknown option: $1" >&2
      echo "   Run with --help for usage" >&2
      exit 1
      ;;
  esac
done

# Validate required args
if [[ -z "$CONTEXT_FILE" ]]; then
  echo "❌ Error: --context is required" >&2
  echo "   Run with --help for usage" >&2
  exit 1
fi
if [[ -z "$PACKAGE_NAME" ]]; then
  echo "❌ Error: --package is required" >&2
  echo "   Run with --help for usage" >&2
  exit 1
fi
if [[ -z "$SUB_PACKAGE_NAME" ]]; then
  echo "❌ Error: --sub-package is required" >&2
  echo "   Run with --help for usage" >&2
  exit 1
fi

# Generate prompt from decomp context via inner_ralph.py
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

if [[ ! -f "$CONTEXT_FILE" ]]; then
  echo "❌ Error: Context file not found: $CONTEXT_FILE" >&2
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

# Create state file for stop hook (markdown with YAML frontmatter)
mkdir -p .claude

cat > .claude/inner-diy-loop.local.md <<EOF
---
active: true
iteration: 1
max_iterations: $MAX_ITERATIONS
completion_promise: "DONE"
started_at: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
---

$PROMPT
EOF

# Output setup message
cat <<EOF
🔄 DIY loop activated in this session!

Iteration: 1
Max iterations: $(if [[ $MAX_ITERATIONS -gt 0 ]]; then echo $MAX_ITERATIONS; else echo "unlimited"; fi)
Completion promise: DONE (ONLY output when TRUE - do not lie!)

The stop hook is now active. When you try to exit, the SAME PROMPT will be
fed back to you. You'll see your previous work in files, creating a
self-referential loop where you iteratively improve on the same task.

To monitor: head -10 .claude/inner-diy-loop.local.md

⚠️  WARNING: This loop cannot be stopped manually! It will run infinitely
    unless you set --max-iterations or the completion promise is met.

🔄
EOF

echo ""
echo "$PROMPT"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "CRITICAL - DIY Loop Completion Promise"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "To complete this loop, output this EXACT text:"
echo "  <promise>DONE</promise>"
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
