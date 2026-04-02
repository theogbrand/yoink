#!/bin/bash

# DIY-Decomp Setup Script
# Scaffolds the project (clone repo, install package)
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
DIY Decomp - Test curation + dependency decomposition (no loop)

USAGE:
  /diy-decomp [PROMPT...] [OPTIONS]

ARGUMENTS:
  PROMPT...    Task description (can be multiple words without quotes)

OPTIONS:
  --url <GITHUB_URL>       GitHub repo URL to clone
  --package <PACKAGE_NAME> Package name (derived from URL if omitted)
  -h, --help               Show this help message

EXAMPLES:
  /diy-decomp Decompose litellm --url https://github.com/BerriAI/litellm
  /diy-decomp --url https://github.com/org/repo --package mypackage Evaluate deps
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
  echo "     /diy-decomp Decompose litellm --url https://github.com/BerriAI/litellm" >&2
  echo "     /diy-decomp --url https://github.com/org/repo Evaluate deps" >&2
  echo "" >&2
  echo "   For all options: /diy-decomp --help" >&2
  exit 1
fi

if [[ -z "$REPO_URL" ]]; then
  echo "❌ Error: --url is required for diy-decomp" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ASSETS_DIR="$(cd "$(dirname "$0")/../assets" && pwd)"

# Derive package name from URL if not explicitly provided
if [[ -z "$PACKAGE_NAME" ]]; then
  PACKAGE_NAME="$(basename "$REPO_URL" .git)"
  PACKAGE_NAME="${PACKAGE_NAME%/}"
fi

echo ""
echo "━━━ Step 1/3: Scaffolding project root ━━━"
if [[ ! -f "pyproject.toml" ]]; then
  cp "$ASSETS_DIR/template-pyproject.toml" pyproject.toml
  echo "  → ./pyproject.toml (created)"
else
  echo "  → ./pyproject.toml (already exists, skipped)"
fi
if [[ ! -f ".gitignore" ]]; then
  cp "$ASSETS_DIR/template-.gitignore" .gitignore
  echo "  → ./.gitignore (created)"
else
  echo "  → ./.gitignore (already exists, skipped)"
fi
DIY_PKG="diy_${PACKAGE_NAME//-/_}"
if [[ ! -d "$DIY_PKG" ]]; then
  mkdir -p "$DIY_PKG/tests/generated" "$DIY_PKG/tests/discovered"
  cp "$ASSETS_DIR/template-__init__.py" "$DIY_PKG/__init__.py"
  echo "  → ./$DIY_PKG/__init__.py (created as package)"
  echo "  → ./$DIY_PKG/tests/{generated,discovered}/ (created)"
else
  echo "  → ./$DIY_PKG/ (already exists, skipped)"
fi

echo ""
echo "━━━ Step 2/3: Cloning repo & copying reference to .slash_diy/ ━━━"
echo "  URL: $REPO_URL"
if ! uv run "$SCRIPT_DIR/prepare.py" --url "$REPO_URL"; then
  echo "❌ prepare.py failed" >&2
  exit 1
fi

echo ""
echo "━━━ Step 3/3: Installing real library for test validation ━━━"
echo "  Package: $PACKAGE_NAME"
if ! uv add "$PACKAGE_NAME"; then
  echo "❌ Failed to install $PACKAGE_NAME" >&2
  exit 1
fi
echo "  ✓ Installed $PACKAGE_NAME"

echo ""
cat <<EOF
✅ Project scaffolded!

Package: $PACKAGE_NAME
Repository: $REPO_URL

Task: $PROMPT
EOF
