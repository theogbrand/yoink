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

## The Loop

```
FOREVER:
1. Read failing tests:
     uv run pytest diy_{top_package}/tests/ -x --tb=short 2>&1
2. Study the failing test to understand what diy_{sub_package}/ must provide
3. Study reference implementation in {reference_material}
4. Modify files in diy_{sub_package}/ ONLY
5. Commit:
     git add diy_{sub_package}/ && git commit -m "inner-N: description"
6. Run full suite:
     uv run run_tests.py > run.log 2>&1
     grep "^score:\|^passed:\|^failed:" run.log
7. If score IMPROVED → keep commit, append to results.tsv
8. If score SAME or WORSE → git reset --hard HEAD~1
9. If score == 1.000000 → EXIT (all Level 0 tests pass)
10. Repeat
```

## Constraints

- **ONLY edit files within `diy_{sub_package}/`**
- Never modify `diy_{top_package}/`, test files, or `.slash_diy/`
- 300-second timeout per test run
- Cannot install new packages beyond what's in `pyproject.toml`
- Study the reference implementation before writing code

## Recording Results

After each experiment, append to `results.tsv`:

```bash
echo -e "$(git rev-parse --short HEAD)\t${score}\t${passed}\t${failed}\t${total}\tdescription" >> results.tsv
```

## Tips

- Run `pytest -x --tb=short` to stop at first failure — fix one thing at a time
- Read the failing test carefully before looking at the reference
- Many tests share underlying functions — fixing one often fixes many
- Keep `diy_{sub_package}/` organized: one submodule per logical area
