# Inner Ralph Loop — Build diy_{sub_package}/

You are building `diy_{sub_package}/` so that the Level 0 test suite for `diy_{top_package}/` passes without the real `{sub_package}` library.

## Context

| Field | Value |
|---|---|
| Top-level package | `{top_package}` |
| Sub-package to build | `{sub_package}` |
| Category | {category} |
| Decomposition strategy | {strategy} |
| Functions to replace | {functions_to_replace} |
| Reference material | `{reference_material}` |
| Acceptable sub-dependencies | {acceptable_sub_dependencies} |
| Max iterations | {max_iterations} |

## Reconnaissance (do this ONCE before entering the loop)

1. Run ALL tests (no `-x`) to see the full failure surface:
     uv run pytest diy_{top_package}/tests/ -v --tb=line 2>&1
2. List every import the top package expects from the sub-package:
     grep -rh "from diy_{sub_package}" diy_{top_package}/ --include="*.py" | sort -u
3. From the above, identify the **required API surface** — the classes, functions, and constants that `diy_{sub_package}/` must export.
4. Plan an implementation order: shared foundations first (base classes, core types), then leaf functions. Fixing a foundation often unblocks many tests at once.

## The Loop

```
FOREVER:
1. Read failing tests:
     uv run pytest diy_{top_package}/tests/ -x --tb=short 2>&1
2. Study the failing test to understand what diy_{sub_package}/ must provide
3. Study reference implementation in {reference_material}
4. Modify files in diy_{sub_package}/ ONLY
5. Commit (record HEAD before so you can safely revert):
     BEFORE=$(git rev-parse HEAD)
     git add diy_{sub_package}/ && git commit -m "inner-N: description"
   If nothing was committed (no changes), go back to step 2.
6. Run full suite:
     uv run run_tests.py > run.log 2>&1
     grep "^score:\|^passed:\|^failed:" run.log
7. If score IMPROVED → keep commit, append to results.tsv
8. If score SAME or WORSE → revert ONLY if HEAD changed:
     [[ "$(git rev-parse HEAD)" != "$BEFORE" ]] && git reset --hard HEAD~1
9. If score == 1.000000 → EXIT (all Level 0 tests pass)
10. Repeat
```

## Constraints

- **ONLY edit files within `diy_{sub_package}/`**
- Never modify `diy_{top_package}/`, test files, or `.slash_diy/`
- 300-second timeout per test run
- Cannot install new packages beyond what's in `pyproject.toml`
- **Allowed imports:** stdlib and the acceptable sub-dependencies listed above. Do not import anything else
- Study the reference implementation before writing code

## Recording Results

After each experiment, append to `results.tsv`:

```bash
echo -e "$(git rev-parse --short HEAD)\t${score}\t${passed}\t${failed}\t${total}\tdescription" >> results.tsv
```

## Tips

- Read the failing test carefully before looking at the reference
- Many tests share underlying functions — fixing one often fixes many
- Keep `diy_{sub_package}/` organized: one submodule per logical area

## Plateau Detection

If score hasn't improved in 3 consecutive iterations:

1. Run all tests WITHOUT `-x` to see every remaining failure
2. Read `results.tsv` to confirm the stall pattern
3. Step back and ask: are the remaining failures hitting a shared root cause?
4. Consider a different approach — restructure `diy_{sub_package}/`, revisit an assumption from recon, or study a different part of the reference
