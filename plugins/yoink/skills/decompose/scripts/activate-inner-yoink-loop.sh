#!/bin/bash

# Yoink Loop Activation Script
# Seeds .claude/inner-yoink-loop.local.md with YAML frontmatter and a
# state body table containing placeholder values. The decompose skill
# (step 4: Generate State Body) fills in the placeholders afterward.

set -euo pipefail

# Parse arguments
MAX_ITERATIONS=0

while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help)
      cat << 'HELP_EOF'
Yoink Loop - Interactive self-referential development loop

USAGE:
  /inner-yoink-loop [OPTIONS]

OPTIONS:
  --max-iterations <n>           Maximum iterations before auto-stop (default: unlimited)
  -h, --help                     Show this help message

DESCRIPTION:
  Seeds a Yoink loop state file with YAML frontmatter and placeholder
  values. The decompose skill's "Generate State Body" step fills in
  the actual values from .claude/decomp_context.md afterward.

  The stop hook prevents exit and feeds your output back as input
  until completion or iteration limit.

  To signal completion, output: <promise>DONE</promise>

STOPPING:
  Only by reaching --max-iterations or detecting <promise>DONE</promise>
  No manual stop - yoink runs infinitely by default!

MONITORING:
  # View current iteration:
  grep '^iteration:' .claude/inner-yoink-loop.local.md

  # View full state:
  head -10 .claude/inner-yoink-loop.local.md
HELP_EOF
      exit 0
      ;;
    --max-iterations)
      if [[ -z "${2:-}" ]]; then
        echo "❌ Error: --max-iterations requires a number argument" >&2
        exit 1
      fi
      if ! [[ "$2" =~ ^[0-9]+$ ]]; then
        echo "❌ Error: --max-iterations must be a positive integer or 0, got: $2" >&2
        exit 1
      fi
      MAX_ITERATIONS="$2"
      shift 2
      ;;
    *)
      echo "❌ Error: Unknown option: $1" >&2
      echo "   Run with --help for usage" >&2
      exit 1
      ;;
  esac
done

ITER_LIMIT="$MAX_ITERATIONS"
if [[ "$ITER_LIMIT" -eq 0 ]]; then
  ITER_LIMIT=30
fi

# Create state file with frontmatter and placeholder table
mkdir -p .claude

cat > .claude/inner-yoink-loop.local.md <<EOF
---
active: true
iteration: 1
max_iterations: $MAX_ITERATIONS
completion_promise: "DONE"
started_at: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
---

| Field | Value |
|---|---|
| top_package | PLACEHOLDER |
| sub_package | PLACEHOLDER |
| category | PLACEHOLDER |
| strategy | PLACEHOLDER |
| functions_to_replace | PLACEHOLDER |
| reference_material | PLACEHOLDER |
| acceptable_sub_dependencies | PLACEHOLDER |
| max_iterations | $ITER_LIMIT |
EOF

echo "🔄 State file seeded: .claude/inner-yoink-loop.local.md"
echo "  Max iterations: $(if [[ $MAX_ITERATIONS -gt 0 ]]; then echo "$MAX_ITERATIONS"; else echo "unlimited"; fi)"
echo "  Placeholders must be filled by the decompose skill (step 4)."
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "CRITICAL - Yoink Loop Completion Promise"
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
