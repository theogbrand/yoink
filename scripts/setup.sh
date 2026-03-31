#!/bin/bash

# Decomp-Only Setup Script
# Scaffolds the project (clone repo, install package, copy plugin files)
# without creating a loop state file.

set -euo pipefail

# Parse arguments
PROMPT_PARTS=()
REPO_URL=""
PACKAGE_NAME=""

while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help)
      cat << 'HELP_EOF'
Decomp Only - Test curation + dependency decomposition (no loop)

USAGE:
  /decomp-only [PROMPT...] [OPTIONS]

ARGUMENTS:
  PROMPT...    Task description (can be multiple words without quotes)

OPTIONS:
  --url <GITHUB_URL>       GitHub repo URL to clone
  --package <PACKAGE_NAME> Package name (derived from URL if omitted)
  -h, --help               Show this help message

EXAMPLES:
  /decomp-only Decompose litellm --url https://github.com/BerriAI/litellm
  /decomp-only --url https://github.com/org/repo --package mypackage Evaluate deps
HELP_EOF
      exit 0
      ;;
    --url)
      if [[ -z "${2:-}" ]]; then
        echo "❌ Error: --url requires a GitHub repo URL" >&2
        exit 1
      fi
      REPO_URL="$2"
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
    *)
      PROMPT_PARTS+=("$1")
      shift
      ;;
  esac
done

PROMPT="${PROMPT_PARTS[*]}"

if [[ -z "$PROMPT" ]]; then
  echo "❌ Error: No prompt provided" >&2
  echo "" >&2
  echo "   Examples:" >&2
  echo "     /decomp-only Decompose litellm --url https://github.com/BerriAI/litellm" >&2
  echo "     /decomp-only --url https://github.com/org/repo Evaluate deps" >&2
  echo "" >&2
  echo "   For all options: /decomp-only --help" >&2
  exit 1
fi

if [[ -z "$REPO_URL" ]]; then
  echo "❌ Error: --url is required for decomp-only" >&2
  exit 1
fi

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
LOCAL_PLUGIN_DIR=".claude/plugins/slash-diy"

# Derive package name from URL if not explicitly provided
if [[ -z "$PACKAGE_NAME" ]]; then
  PACKAGE_NAME="$(basename "$REPO_URL" .git)"
  PACKAGE_NAME="${PACKAGE_NAME%/}"
fi

echo ""
echo "━━━ Step 1/4: Copying plugin files ━━━"
mkdir -p "$LOCAL_PLUGIN_DIR"
for f in prepare.py run_tests.py rewrite_imports.py __init__.py pyproject.toml; do
  cp "$PLUGIN_ROOT/$f" "$LOCAL_PLUGIN_DIR/"
  echo "  → $LOCAL_PLUGIN_DIR/$f"
done

echo ""
echo "━━━ Step 2/4: Scaffolding project root ━━━"
if [[ ! -f "pyproject.toml" ]]; then
  cp "$LOCAL_PLUGIN_DIR/pyproject.toml" .
  echo "  → ./pyproject.toml (created)"
else
  echo "  → ./pyproject.toml (already exists, skipped)"
fi
DIY_PKG="diy_${PACKAGE_NAME//-/_}"
if [[ ! -d "$DIY_PKG" ]]; then
  mkdir -p "$DIY_PKG/tests/generated" "$DIY_PKG/tests/discovered"
  cp "$LOCAL_PLUGIN_DIR/__init__.py" "$DIY_PKG/__init__.py"
  echo "  → ./$DIY_PKG/__init__.py (created as package)"
  echo "  → ./$DIY_PKG/tests/{generated,discovered}/ (created)"
else
  echo "  → ./$DIY_PKG/ (already exists, skipped)"
fi

echo ""
echo "━━━ Step 3/4: Cloning repo & copying reference to .slash_diy/ ━━━"
echo "  URL: $REPO_URL"
uv run "$LOCAL_PLUGIN_DIR/prepare.py" --url "$REPO_URL"
if [[ $? -ne 0 ]]; then
  echo "❌ prepare.py failed" >&2
  exit 1
fi

echo ""
echo "━━━ Step 4/4: Installing real library for test validation ━━━"
echo "  Package: $PACKAGE_NAME"
uv pip install "$PACKAGE_NAME"
if [[ $? -ne 0 ]]; then
  echo "❌ Failed to install $PACKAGE_NAME" >&2
  exit 1
fi
echo "  ✓ Installed $PACKAGE_NAME"

echo ""
cat <<EOF
✅ Project scaffolded for decomp-only!

Package: $PACKAGE_NAME
Repository: $REPO_URL

Task: $PROMPT
EOF
