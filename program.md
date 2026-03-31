# DIY Clone — Autonomous Loop Instructions

## Goal

Curate a focused test suite for the target function, validate it against the
real library, then iteratively build `diy_<package>/` to pass those tests.
You ONLY modify files within `diy_<package>/`. Everything else is fixed.

> **Naming convention**: The working directory is `diy_<package>/` where
> `<package>` is the Package name from your prompt with hyphens replaced by
> underscores (e.g., package `litellm` → `diy_litellm/`).

## Directory Structure

```
./                                    # Target project root (your CWD)
├── diy_<package>/                    # ONLY directory you edit (Python package)
│   ├── __init__.py                   # Main module — add submodules as needed
│   ├── *.py                          # Create submodules to match target structure
│   └── tests/                        # Curated test suite (created in Phase 0)
│       ├── generated/                # Tests written by subagent (used for validation)
│       └── discovered/               # Tests from original repo (reference only)
├── pyproject.toml                    # Project deps
├── .slash_diy/                       # Hidden dir for reference material
│   └── reference/                    # Read-only reference material
│       ├── <package>/                # Original source code
│       └── tests/                    # Original test suite (raw, unmodified)
├── results.tsv                       # Experiment log (untracked)
├── run.log                           # Latest test output (untracked)
└── .claude/plugins/slash-diy/        # Plugin tools (DO NOT MODIFY)
    ├── prepare.py
    ├── run_tests.py
    ├── rewrite_imports.py
    └── program.md                    # (this file)
```

## Phase 0: Test Curation

**You MUST complete this phase before touching diy_<package>/.**

Refer to and follow the instructions in `docs/phase-0-test-curation.md`.

---

## Setup (after Phase 0)

1. Create experiment branch:
   ```bash
   git checkout -b diy/<tag>
   ```

2. Initialize results tracking:
   ```bash
   echo -e "commit\tscore\tpassed\tfailed\ttotal\tdescription" > results.tsv
   ```

3. Record baseline (should be score ~0):
   ```bash
   echo -e "$(git rev-parse --short HEAD)\t0.0\t0\t${total}\t${total}\tbaseline" >> results.tsv
   ```

## Constraints

- **ONLY edit files within `diy_<package>/`** — never modify `.slash_diy/`, `.claude/plugins/`, or test files after Phase 0
- `diy_<package>/` is a Python package — add submodules (e.g., `diy_<package>/utils.py`) as needed to match the target library's structure
- Study `.slash_diy/reference/` for the original implementation — it's your primary resource
- 300-second timeout per test run
- Cannot install new packages beyond what's in `pyproject.toml`

## The Loop

```
FOREVER:
1. Read current diy_<package>/ source files and results.tsv
2. Study failing tests: uv run pytest diy_<package>/tests/generated/ -x --tb=short 2>&1
3. Identify the next group of tests to fix
4. Modify source files in diy_<package>/ to pass more tests
5. git add diy_<package>/ && git commit -m "expN: description"
6. uv run .claude/plugins/slash-diy/run_tests.py > run.log 2>&1
7. grep "^score:\|^passed:\|^failed:" run.log
8. If score IMPROVED → keep commit, record in results.tsv
9. If score SAME or WORSE → git reset --hard HEAD~1
10. Repeat
```

## Strategy

### Phase 1: Stubs & Imports
- Read test files to understand what's imported from the library
- Create stub functions/classes in `diy_<package>/__init__.py` (and submodules as needed) that satisfy import requirements
- Mirror the target library's module structure: if tests import `from diy_<package>.foo import X`, create `diy_<package>/foo.py`
- Goal: move from ImportError to actual test failures

### Phase 2: Core Functionality
- Fix tests in dependency order (foundational functions first)
- Study the reference implementation for each function
- Implement the minimum code to pass each test

### Phase 3: Edge Cases & Polish
- Handle edge cases revealed by remaining failures
- Match the original library's error handling behavior
- Grind to 100% pass rate

## Recording Results

After each experiment, append to results.tsv (untracked):
```bash
echo -e "$(git rev-parse --short HEAD)\t${score}\t${passed}\t${failed}\t${total}\tdescription" >> results.tsv
```

## Tips

- Run `uv run pytest diy_<package>/tests/generated/ -x --tb=short` to stop at first failure — fix one thing at a time
- Read the failing test carefully before looking at the reference implementation
- Many tests share underlying functions — fixing one often fixes many
- Keep diy_<package>/ organized: one submodule per logical area, re-export from __init__.py
- The recursive decomposition philosophy applies: start high-level, decompose layer by layer
