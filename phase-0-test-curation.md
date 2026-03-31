
## Phase 0: Test Curation

Parse your prompt to identify:
- **Package name**: from the `Package:` line in the prompt
- **Target function/feature**: from the `Task:` line in the prompt

### Step 1: Generate focused tests (Subagent A)

Use the Agent tool to spawn a subagent with this task:

```
You are an experienced Test Engineer writing pytest unit tests.

Target: <FUNCTION from Task line> from the <PACKAGE> library.

Study the reference implementation in .slash_diy/reference/<PACKAGE>/ to understand:
- Function signature, parameters, and return types
- Error handling and edge cases
- Common usage patterns

Write comprehensive pytest tests to diy_<PACKAGE>/tests/generated/test_<function>.py covering:
- Happy path with typical inputs
- Edge cases (empty inputs, None, boundary conditions)
- Error handling (invalid inputs, expected exceptions)
- Common real-world usage patterns

Rules:
- Import from the REAL library: from <PACKAGE> import <function>
- Tests MUST be self-contained — NO external API calls, NO network requests
- Use unittest.mock to mock any external dependencies (HTTP, databases, etc.)
- Each test must be independent and clearly named
- Target 10-30 focused tests
- Create diy_<PACKAGE>/tests/generated/ directory if it doesn't exist
```

### Step 2: Discover relevant tests (Subagent B)

Use the Agent tool to spawn a subagent with this task:

```
You are a test curator. Search .slash_diy/reference/tests/ to find tests relevant to:
<FUNCTION from Task line> from <PACKAGE>.

Strategy:
1. Glob for test file names containing the function name
2. Grep for imports/calls of the target function across all test files
3. Read candidate files to confirm relevance
4. Copy ONLY relevant files to diy_<PACKAGE>/tests/discovered/ (preserve directory structure)

Rules:
- Do NOT rewrite imports — keep them importing from the real library
- Skip tests that require API keys, network access, or complex fixtures
- Skip tests for unrelated features
- If only part of a file is relevant, extract just those test functions
- IMPORTANT: Prefix ALL discovered test filenames with `disc_` (e.g., `test_foo.py` → `disc_test_foo.py`) to avoid name collisions with generated tests
- Cap at ~10-15 most relevant test files
- Create diy_<PACKAGE>/tests/discovered/ directory if it doesn't exist
- If no relevant tests found, that's OK — generated tests are sufficient
```

**Launch both subagents in parallel** using the Agent tool.

### Step 3: Validate tests against the real library

Run the curated tests against the pip-installed real library:

```bash
uv run pytest diy_<PACKAGE>/tests/generated/ diy_<PACKAGE>/tests/discovered/ -v --tb=short 2>&1
```

**Prune failures:**
- For each failing test file, decide: is this a bad test or an env issue?
- Delete test files that fail due to missing API keys, network issues, or
  dependencies on the full library that we can't satisfy
- Re-run until all remaining tests pass
- **If ZERO tests survive, ABORT** — output an error explaining the situation

Print a summary:
```
Test validation results:
  Generated: X/Y passed (removed: list of removed files)
  Discovered: A/B passed (removed: list of removed files)
  Total surviving tests: N
```

### Step 4: Rewrite imports

After validation passes, rewrite imports so tests target `diy_<package>/`:

```bash
uv run .claude/plugins/slash-diy/rewrite_imports.py --package <PACKAGE>
```

### Step 5: Sanity check

Run the test suite against the empty `diy_<package>/` to confirm tests fail:

```bash
uv run .claude/plugins/slash-diy/run_tests.py > run.log 2>&1
grep "^score:" run.log
```

Score should be ~0.0 (tests should fail against empty diy_<package>/). If score > 0,
something is wrong — investigate before proceeding.