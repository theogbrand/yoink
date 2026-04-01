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

## Decomp MVP

### /diy-decomp

Curate tests from a target package, then decompose its dependencies into a local, dependency-free replacement. Runs in two phases: test curation (Phase 0) followed by dependency decomposition (Phase 1).

**Example Usage:**
```bash
mkdir ../litellm-lite
cp ./examples/litellm-sample.md ../litellm-lite/
cd ../litellm-lite
claude --plugin-dir ../slash-diy
```

```bash
/diy-decomp "I want to replace the usage of litellm in @litellm-sample.md with my own implementation. make it minimal so that it only implements what we need as a replacement and not to be as robust for all other cases in the original library. although minimal it still has to be secure and verified via testing" --url "https://github.com/BerriAI/litellm"
```

**Usage:**
```bash
/diy-decomp "<prompt>" --url "<github_url>" [--package "<package_name>"]
```

**Options:**
- `--url <github_url>` - GitHub repository URL to clone and decompose (required)
- `--package <package_name>` - Override the package name (defaults to the repo name from the URL)

The individual phases of `/diy-decomp` are also available as separate commands, useful if a run fails midway and you need to resume from a specific phase:

### /setup

Scaffold the project: clone the target repo, copy plugin files, and install the real library for test validation.

**Usage:**
```bash
/setup --url "https://github.com/BerriAI/litellm"
```

**Options:**
- `--url <github_url>` - GitHub repository URL to clone (required)
- `--package <package_name>` - Override the package name (defaults to the repo name from the URL)

### /test-curate

Phase 0: Generate and discover tests, then validate them against the real library. Requires `/setup` to have been run first.

**Usage:**
```bash
/test-curate "I want to replace the usage of litellm in @sample.md with my own implementation" --package litellm
```

**Options:**
- `--package <package_name>` - The target package name (required)

### /decompose

Phase 1: Dependency decomposition. Seeds the queue with the target package and iteratively decomposes each dependency. Requires `/test-curate` to have been completed first.

**Usage:**
```bash
/decompose --package litellm
```

**Options:**
- `--package <package_name>` - The target package name (required)

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

### Orchestration Linter

After editing command or agent files, run the linter to validate conventions and regenerate the flow visualization:

```bash
uv run python scripts/orchestration-linter.py --write
```

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the full list of conventions enforced.
