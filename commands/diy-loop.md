---
description: "Start Ralph Wiggum loop in current session"
argument-hint: "PROMPT [--url GITHUB_URL] [--max-iterations N] [--completion-promise TEXT]"
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/scripts/setup-diy-loop.sh:*)"]
hide-from-slash-command-tool: "true"
---

# DIY Loop Command

Execute the setup script to initialize the DIY loop:

```!
"${CLAUDE_PLUGIN_ROOT}/scripts/setup-diy-loop.sh" $ARGUMENTS
```

IMPORTANT: After the setup script runs, you MUST print its full output to the user verbatim so they can see the setup progress (steps 1-4, file copies, clone status, etc.). Do not skip or summarize — show the complete output.

Then work on the task. When you try to exit, the DIY loop will feed the SAME PROMPT back to you for the next iteration. You'll see your previous work in files and git history, allowing you to iterate and improve.

CRITICAL RULE: If a completion promise is set, you may ONLY output it when the statement is completely and unequivocally TRUE. Do not output false promises to escape the loop, even if you think you're stuck or should exit for other reasons. The loop is designed to continue until genuine completion.
