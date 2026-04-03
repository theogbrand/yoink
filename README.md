# YOINK

YOINK (**Y**ou **O**nly **I**mplement **N**ative **K**nowledge) is an AI agent that removes complex dependencies by reimplementing only what you need.

YOINK is currently built as a Claude Code plugin that decomposes third-party
dependencies into internal replacements. Instead of importing a 50k-line SDK
for three function calls, point yoink at the package, describe what you need,
and it reimplements only the functionality you actually use, verified against
the expectations of the original library's tests.

They say "don't reinvent the wheel" but what if you could?

### Why now?

AI agents are getting good enough to own code end-to-end, and with supply chain
attacks accelerating, fewer dependencies means less attack surface.

> Classical software engineering would have you believe that dependencies are
> good (we're building pyramids from bricks), but imo this has to be
> re-evaluated, and it's why I've been so growingly averse to them, preferring
> to use LLMs to "yoink" functionality when it's simple enough and possible. -
> [Andrej Karpathy](https://x.com/karpathy/status/2036487306585268612)

OpenAI's [harness engineering](https://openai.com/index/harness-engineering/)
article echoed this: agents reason better from reimplemented functionality they
have full visibility into, over opaque third-party libraries.

> In some cases, it was cheaper to have the agent reimplement subsets of
> functionality than to work around opaque upstream behavior from public
> libraries. For example, rather than pulling in a generic p-limit-style
> package, we implemented our own map-with-concurrency helper: it’s tightly
> integrated with our OpenTelemetry instrumentation, has 100% test coverage, and
> behaves exactly the way our runtime expects. - Ryan Lopopolo (OpenAI)

We are making this capability accessible to anyone.

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

yoink runs three skills sequentially:

1. **`/setup`** clones the target repo and scaffolds a local replacement package.
2. **`/curate-tests`** studies the reference implementation and generates new tests, verified against the expectations of the original test suite.
3. **`/decompose`** determines dependencies to keep or decompose, based on a set of principles we defined, such as "keeping foundational primitives regardless of how narrow they are used".

The `/yoink` command runs all three in sequence.

### /yoink

Curate tests from a target package, then decompose its dependencies into a
local, dependency-free replacement. Runs in three phases: setup (Phase 1), test
curation (Phase 2), and dependency decomposition (Phase 3).

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

### /curate-tests

Phase 2: Generate and discover tests, then validate them against the real library. Requires `/setup` to have been run first.

**Usage:**
```bash
/curate-tests "I want to replace the usage of litellm in @sample.md with my own implementation" --package litellm
```

**Options:**
- `--package <package_name>` - The target package name (required)

### /decompose

Phase 3: Dependency decomposition. Seeds the queue with the target package and iteratively decomposes each dependency. Requires `/curate-tests` to have been completed first.

**Usage:**
```bash
/decompose --package litellm
```

**Options:**
- `--package <package_name>` - The target package name (required)

## When to use this?

**What is this good for?**
- Replacing small-to-medium utility packages with internal replacements
- Packages with unclear maintenance or security posture
- Reducing supply chain attack surface
- Cases where you only need a subset of a package's features

**What is this not good for?**
- Large, complex frameworks (Django, Flask, etc.)
- Packages with deep platform-specific bindings
- Cryptographic implementations (use audited libraries)

## Limitations

- YOINK currently only supports re-implementing Python packages, but we plan to support JavaScript packages next.

## How to use this in development or contribute?

```bash
claude --plugin-dir .
```

### Orchestration Linter

After editing skill or agent files, run the linter to validate conventions and
regenerate the flow visualization in
[ORCHESTRATION_FLOW.md](./ORCHESTRATION_FLOW.md):

```bash
uv run python scripts/orchestration-linter.py --write
```

See [CONTRIBUTING.md](./CONTRIBUTING.md) for more.
