# slash-diy

A plugin to clone dependencies you don't trust. No more supply chain attacks.

## What is slash-diy?

They say don't reinvent the wheel. But what if you could just "yoink" the exact
functionality you need out of a library, strip away everything you don't, and
own the result? That's slash-diy, letting you reinvent the wheel by keeping the
good bits and rebuilding on your own terms to reduce external dependencies.

### How does it work?

slash-diy decomposes third-party functionality into local replacements. Point it
at a package, describe what you need, and it will curate tests from the original
library, iteratively decompose dependencies, and implement each in a ralph loop
until you have a local implementation.

Instead of importing a 50k-line SDK for three function calls, yoink those three
functions into your own codebase. Verified against the original's own test
expectations, but free from the dependency chain that came with it.

## Quick Start

```bash
mkdir ../litellm-lite
cp ./examples/litellm-sample.md ../litellm-lite/
cd ../litellm-lite
claude --plugin-dir ../slash-diy
```

```bash
/diy-decomp "I want to replace the usage of litellm in @litellm-sample.md with my own implementation. make it minimal so that it only implements what we need as a replacement and not to be as robust for all other cases in the original library. although minimal it still has to be secure and verified via testing" --url "https://github.com/BerriAI/litellm"
```

## Skills

### /diy-decomp

Curate tests from a target package, then decompose its dependencies into a local, dependency-free replacement. Runs in two phases: test curation (Phase 0) followed by dependency decomposition (Phase 1).

**Usage:**
```bash
/diy-decomp "<prompt>" --url "<github_url>" [--package "<package_name>"] [--skip-discovery]
```

**Options:**
- `--url <github_url>` - GitHub repository URL to clone and decompose (required)
- `--package <package_name>` - Override the package name (defaults to the repo name from the URL)
- `--skip-discovery` - Skip the test discovery step (test generation still works without discovered tests)

The individual phases of `/diy-decomp` are also available as separate skills, useful if a run fails midway and you need to resume from a specific phase:

### /setup

Scaffold the project: clone the target repo and install the real library for test validation.

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

## When to use this?

**What is this good for?**
- Replacing small-to-medium utility packages with zero-dependency local code
- Packages with unclear maintenance or security posture
- Reducing supply chain attack surface
- Cases where you only need a subset of a package's features

**What is this not good for?**
- Large, complex frameworks (React, Express, etc.)
- Packages with deep platform-specific bindings
- Cryptographic implementations (use audited libraries)

## How to use this in development or contribute?

```bash
claude --plugin-dir .
```

Step 3 of decomposition/decomposition-orchestrator.md uses the inner ralph loop below.

## Testing Inner Ralph Loop

The inner ralph loop builds a `diy_<sub_package>/` replacement for a sub-dependency, gated by the top-level (Level 0) test suite. It is self-contained and can be tested independently from the full diy-loop.

### Prerequisites

You need a project that has already completed Phase 0 (curated test suite exists and passes against the real library). For example, `lite-llm-lite/` with `diy_litellm/tests/` already set up.

### 1. Create a decomposition context

The context can be **JSON** or **markdown** (the orchestrator's evaluate step outputs markdown directly).

**JSON format** — save as `decomp_context.json`:

```json
{
  "category": "Utilities / Data Structures & Algorithms",
  "strategy": "Extract and inline specific functions used by diy_litellm",
  "functions_to_replace": ["BaseMetadata", "GroupedMetadata", "Gt", "Ge", "Lt", "Le"],
  "reference_material": ".slash_diy/reference/annotated_types/",
  "acceptable_sub_dependencies": ["typing_extensions"]
}
```

**Markdown format** — save evaluation output as `decomp_context.md`:

Example for `openai`: refer to examples/decomp_context_openai.md

Example for `pydantic`: refer to examples/decomp_context_pydantic.md

### 2. Generate the prompt

```bash
uv run inner_ralph.py generate-prompt \
  --context decomp_context.md \
  --top-package litellm \
  --sub-package openai \
  --max-iterations 30
```

The `--context` flag accepts either JSON or markdown — format is auto-detected. This outputs a complete, self-contained prompt that includes pre-flight steps (baseline verification, import rewriting, scaffolding) and the iterative loop instructions.

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
### Orchestration Linter

After editing skill or agent files, run the linter to validate conventions and regenerate the flow visualization:

```bash
uv run python scripts/orchestration-linter.py --write
```

See [CONTRIBUTING.md](./CONTRIBUTING.md) for more.
