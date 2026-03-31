---
description: "Scaffold project: clone repo, copy plugin files, install real library"
argument-hint: "--url GITHUB_URL [--package PACKAGE_NAME]"
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh:*)"]
---

# Setup

Execute the setup script to scaffold the project:

```!
"${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh" $ARGUMENTS
```

IMPORTANT: After the setup script runs, print its full output to the user verbatim.
