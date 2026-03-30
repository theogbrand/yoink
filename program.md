# DIY Clone — Autonomous Loop Instructions

## Goal

Iteratively build `library.py` to pass the test suite extracted from the target
library. You ONLY modify `library.py`. Everything else is fixed.

## Directory Structure

```
./                                    # Target project root (your CWD)
├── library.py                        # ONLY file you edit
├── pyproject.toml                    # Project deps
├── tests/                            # Extracted test suite (DO NOT MODIFY)
├── reference/                        # Original source code (read-only reference)
├── results.tsv                       # Experiment log (untracked)
├── run.log                           # Latest test output (untracked)
└── .claude/plugins/slash-diy/        # Plugin tools (DO NOT MODIFY)
    ├── prepare.py
    ├── run_tests.py
    └── program.md                    # (this file)
```

## Setup

1. Verify environment:
   ```bash
   ls tests/ reference/ library.py .claude/plugins/slash-diy/run_tests.py
   ```

2. Create experiment branch:
   ```bash
   git checkout -b diy/<tag>
   ```

3. Initialize results tracking:
   ```bash
   echo -e "commit\tscore\tpassed\tfailed\ttotal\tdescription" > results.tsv
   ```

4. Run baseline:
   ```bash
   uv run .claude/plugins/slash-diy/run_tests.py > run.log 2>&1
   grep "^score:" run.log
   ```

## Constraints

- **ONLY edit `library.py`** — never modify `tests/`, `.claude/plugins/`, or `reference/`
- Study `reference/` for the original implementation — it's your primary resource
- 300-second timeout per test run
- Cannot install new packages beyond what's in `pyproject.toml`

## The Loop

```
FOREVER:
1. Read current library.py and results.tsv
2. Study failing tests: uv run pytest tests/ -x --tb=short 2>&1
3. Identify the next group of tests to fix
4. Modify library.py to pass more tests
5. git add library.py && git commit -m "expN: description"
6. uv run .claude/plugins/slash-diy/run_tests.py > run.log 2>&1
7. grep "^score:\|^passed:\|^failed:" run.log
8. If score IMPROVED → keep commit, record in results.tsv
9. If score SAME or WORSE → git reset --hard HEAD~1
10. Repeat
```

## Strategy

### Phase 1: Stubs & Imports
- Read test files to understand what's imported from the library
- Create stub functions/classes that satisfy import requirements
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

- Run `uv run pytest tests/ -x --tb=short` to stop at first failure — fix one thing at a time
- Read the failing test carefully before looking at the reference implementation
- Many tests share underlying functions — fixing one often fixes many
- Keep library.py organized: group related functionality together
- If a test requires external API calls or credentials, skip it — focus on pure logic
- The recursive decomposition philosophy applies: start high-level, decompose layer by layer
