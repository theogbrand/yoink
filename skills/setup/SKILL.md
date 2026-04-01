---
name: setup
description: "Scaffold project: clone repo, install real library. Only invoke when explicitly requested by the user or by the diy-decomp orchestrator."
argument-hint: "--url GITHUB_URL [--package PACKAGE_NAME]"
allowed-tools: ["Bash(${CLAUDE_SKILL_DIR}/scripts/setup.sh:*)"]
---

# Setup

> **Do not invoke this skill unless explicitly requested.** It is called by `/diy-decomp` or run standalone by the user.

Execute the setup script to scaffold the project:

```bash
"${CLAUDE_SKILL_DIR}/scripts/setup.sh" $ARGUMENTS
```

IMPORTANT: After the setup script runs, print its full output to the user verbatim.
