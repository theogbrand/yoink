# slash-diy

A plugin to clone packages from SDKs you don't quite trust.

## What is slash-diy?

slash-diy uses a continuous self-referential loop to iteratively recreate the functionality of third-party packages you'd rather not depend on. Point it at a package, describe what you need, and let it loop until it's built a local, dependency-free replacement.

The underlying engine is a **stop hook loop**: Claude receives the same prompt repeatedly, sees its own previous work in files, and iteratively improves until the task is complete.

## Quick Start

```bash
/diy-loop "Clone the retry logic from axios-retry. Support exponential backoff, max retries, and custom retry conditions. Output <promise>COMPLETE</promise> when all tests pass." --completion-promise "COMPLETE" --max-iterations 30
```

Claude will:
- Study the target package's behavior
- Implement a local replacement iteratively
- Write and run tests
- Fix failures based on test output
- Iterate until requirements are met
- Output the completion promise when done

## Commands

### /diy-loop

Start a DIY loop in your current session.

**Set up required permissions:**
```bash
chmod +x ./scripts/setup-diy-loop.sh
```

**Example Usage:**
```bash
/diy-loop 'Your job is to port assistant-ui-react monorepo (for react) to assistant-ui-vue (for vue) and maintain the repository.\n\nYou have access to the current assistant-ui-react repository as well as the assistant-ui-vue repository.\n\nMake a commit and push your changes after every single file edit.\n\nUse the assistant-ui-vue/.agent/ directory as a scratchpad for your work. Store long term plans and todo lists there.\n\nThe original project was mostly tested by manually running the code. When porting, you will need to write end to end and unit tests for the project. But make sure to spend most of your time on the actual porting, not on the testing. A good heuristic is to spend 80% of your time on the actual porting, and 20% on the testing.' --completion-promise 'TASK COMPLETE'  --max-iterations 30
```

**Usage:**
```bash
/diy-loop "<prompt>" --max-iterations <n> --completion-promise "<text>"
```

**Options:**
- `--max-iterations <n>` - Stop after N iterations (default: unlimited) -> TODO: change this to a compute budget like $5 instead, iterations is too abstract
- `--completion-promise <text>` - Phrase that signals completion

### /cancel-diy

Cancel the active loop.

```bash
/cancel-diy
```

## Prompt Writing Tips

### Clear completion criteria

```markdown
Clone the date formatting utilities from dayjs.
Support: format(), fromNow(), diff(), isValid().

When complete:
- All four functions working with matching behavior
- Edge cases covered (invalid dates, timezones)
- Tests passing
- Output: <promise>COMPLETE</promise>
```

### Incremental goals

```markdown
Phase 1: Basic format() with common tokens (YYYY, MM, DD, HH, mm, ss)
Phase 2: Relative time (fromNow, toNow)
Phase 3: Duration diff between dates

Output <promise>COMPLETE</promise> when all phases done.
```

### Self-correction via TDD

```markdown
Reimplement the retry middleware from got:
1. Write failing tests matching got's retry behavior
2. Implement the retry logic
3. Run tests
4. If any fail, debug and fix
5. Repeat until all green
6. Output: <promise>COMPLETE</promise>
```

### Escape hatches

Always use `--max-iterations` to prevent infinite loops:

```bash
/diy-loop "Clone lodash.debounce" --max-iterations 20
```

**Note**: `--completion-promise` uses exact string matching. Always rely on `--max-iterations` as your primary safety mechanism.

## When to Use

**Good for:**
- Replacing small-to-medium utility packages with zero-dependency local code
- Packages with unclear maintenance or security posture
- Reducing supply chain attack surface
- Cases where you only need a subset of a package's features

**Not good for:**
- Large, complex frameworks (React, Express, etc.)
- Packages with deep platform-specific bindings
- Cryptographic implementations (use audited libraries)
- Tasks with unclear success criteria

## For Development

```bash
claude --plugin-dir .
```
