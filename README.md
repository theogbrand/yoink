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

### /decomp-only

Curate tests from a target package, then decompose its dependencies into a local, dependency-free replacement. Runs in two phases: test curation (Phase 0) followed by dependency decomposition (Phase 1).

**Example Usage:**
```bash
/decomp-only "I want to replace the usage of litellm in @litellm-sample.md with my own implementation. make it minimal so that it only implements what we need as a replacement and not to be as robust for all other cases in the original library. although minimal it still has to be secure and verified via testing" --url "https://github.com/BerriAI/litellm"
```

**Usage:**
```bash
/decomp-only "<prompt>" --url "<github_url>" [--package "<package_name>"]
```

**Options:**
- `--url <github_url>` - GitHub repository URL to clone and decompose (required)
- `--package <package_name>` - Override the package name (defaults to the repo name from the URL)

The individual phases of `/decomp-only` are also available as separate commands, useful if a run fails midway and you need to resume from a specific phase:

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

Take over from step 3 of decomposition/decomposition-orchestrator.md

## Testing Inner Ralph Loop

The inner ralph loop builds a `diy_<sub_package>/` replacement for a sub-dependency, gated by the top-level (Level 0) test suite. It is self-contained and can be tested independently from the full diy-loop.

### Prerequisites

You need a project that has already completed Phase 0 (curated test suite exists and passes against the real library). For example, `lite-llm-lite/` with `diy_litellm/tests/` already set up.

### 1. Create a decomposition context

Save as `decomp_context.json`:

```json
{
  "category": "Utilities / Data Structures & Algorithms",
  "strategy": "Extract and inline specific functions used by diy_litellm",
  "functions_to_replace": ["BaseMetadata", "GroupedMetadata", "Gt", "Ge", "Lt", "Le"],
  "reference_material": ".slash_diy/reference/annotated_types/",
  "acceptable_sub_dependencies": ["typing_extensions"]
}
```

Example Output from Orchestrator:
For now, Orchestrator outputs in Markdown:

where decomp-queue.json has {
  "pending": ["openai"]
}:
```markdown
Decision: Decompose
Reasoning: openai is a vendor SDK. The core usage is
limited to instantiating a client and calling
chat.completions.create(), both of which are
straightforward to replace using httpx. The exception
coupling adds complexity but is manageable.
Category: API wrapper
Strategy: Replace with raw HTTP calls using httpx:
1. Create a lightweight client that takes api_key,
base_url, timeout and calls {base_url}/chat/completions
via httpx.post()
2. Remove inheritance from openai exception classes —
define independent exceptions
3. Replace openai._models.BaseModel usage in
types/utils.py with pydantic BaseModel
4. Replace openai.types.completion_usage.* imports with
custom equivalents
Functions to replace:
- openai.OpenAI() constructor
- client.chat.completions.create() and with_raw_response
variant
- All openai exception base classes
- openai._models.BaseModel (alias for OpenAIObject)
- openai.types.completion_usage.CompletionTokensDetails,
CompletionUsage, PromptTokensDetails
Acceptable sub-dependencies: httpx (for HTTP calls),
pydantic (already used)
```

where decomp_context.json has {
  "pending": ["pydantic"]
}:
```markdown
Decision: Decompose
Reasoning: Pydantic is used only as simple data containers
  with no validation. ~15 model classes use only BaseModel,
  Field, PrivateAttr, model_dump(), and model_config. No
validators are used.
Category: Utility
Strategy: Replace pydantic BaseModel with plain Python
classes. Use __init__ for field declarations, custom
model_dump() methods for serialization.
Functions to replace:
- BaseModel → plain Python classes
- Field(default=None) → regular init parameters with
defaults
- PrivateAttr() → Direct assignment in __init__
- model_dump() → custom serialization method
- model_config with extra='allow' → __setattr__
permissiveness or **kwargs in __init__
Acceptable sub-dependencies: None. Standard library only.
```

### 2. Generate the prompt

```bash
uv run inner_ralph.py generate-prompt \
  --context decomp_context.json \
  --top-package litellm \
  --sub-package annotated-types \
  --max-iterations 30
```

This outputs a complete, self-contained prompt that includes pre-flight steps (baseline verification, import rewriting, scaffolding) and the iterative loop instructions.

### 3. Run it

Feed the generated prompt to a Claude agent. The agent will:

1. **Pre-flight**: Verify Level 0 tests pass with the real sub-package, rewrite imports in `diy_<top_pkg>/` source to point at `diy_<sub_pkg>`, scaffold the sub-package directory
2. **Loop**: Iteratively build `diy_<sub_pkg>/` by studying failing tests, reading reference code, and committing changes (reverting on regression)
3. **Exit**: When all Level 0 tests pass (score == 1.0) or max iterations reached

### Utilities

**Rewrite sub-package imports** (used during pre-flight):

```bash
uv run inner_ralph.py rewrite-sub-imports \
  --sub-package annotated-types \
  --target-dir diy_litellm
```

Rewrites `from annotated_types` / `import annotated_types` to `diy_annotated_types` in source files only (skips `tests/` directory).