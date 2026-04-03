# yoink

A plugin to clone dependencies you don't trust. No more supply chain attacks.

## What is yoink?

They say don't reinvent the wheel. But what if you could just "yoink" the exact
functionality you need out of a library, strip away everything you don't, and
own the result? That's yoink, letting you reinvent the wheel by keeping the
good bits and rebuilding on your own terms to reduce external dependencies.

### How does it work?

yoink decomposes third-party functionality into local replacements. Point it
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
claude --plugin-dir ../yoink/plugins/yoink
```

```bash
/yoink "Replace the usage of litellm in @litellm-sample.md with my own implementation" --url "https://github.com/BerriAI/litellm"
```

## Skills

### /yoink

Curate tests from a target package, then decompose its dependencies into a local, dependency-free replacement. Runs in three phases: setup (Phase 1), test curation (Phase 2), and dependency decomposition (Phase 3).

**Usage:**
```bash
/yoink "<prompt>" --url "<github_url>" [--package "<package_name>"] [--skip-discovery]
```

**Options:**
- `--url <github_url>` - GitHub repository URL to clone and decompose (required)
- `--package <package_name>` - Override the package name (defaults to the repo name from the URL)
- `--skip-discovery` - Skip the test discovery step (test generation still works without discovered tests)

The individual phases of `/yoink` are also available as separate skills, useful if a run fails midway and you need to resume from a specific phase:

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

Phase 2: Generate and discover tests, then validate them against the real library. Requires `/setup` to have been run first.

**Usage:**
```bash
/test-curate "I want to replace the usage of litellm in @sample.md with my own implementation" --package litellm
```

**Options:**
- `--package <package_name>` - The target package name (required)

### /decompose

Phase 3: Dependency decomposition. Seeds the queue with the target package and iteratively decomposes each dependency. Requires `/test-curate` to have been completed first.

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

### Orchestration Linter

After editing skill or agent files, run the linter to validate conventions and regenerate the flow visualization in [ORCHESTRATION_FLOW.md](./ORCHESTRATION_FLOW.md):

```bash
uv run python scripts/orchestration-linter.py --write
```

See [CONTRIBUTING.md](./CONTRIBUTING.md) for more.
