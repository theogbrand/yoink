# slash-diy

A plugin to clone packages from SDKs you don't quite trust.

## What is slash-diy?

slash-diy decomposes third-party packages into local, dependency-free replacements. Point it at a package, describe what you need, and it will curate tests from the original library, then iteratively decompose each dependency until you have a fully local implementation.

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
/diy-decomp "<prompt>" --url "<github_url>" [--package "<package_name>"]
```

**Options:**
- `--url <github_url>` - GitHub repository URL to clone and decompose (required)
- `--package <package_name>` - Override the package name (defaults to the repo name from the URL)

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

## For Development

```bash
claude --plugin-dir .
```

### Orchestration Linter

After editing skill or agent files, run the linter to validate conventions and regenerate the flow visualization:

```bash
uv run python scripts/orchestration-linter.py --write
```

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the full list of conventions enforced.
