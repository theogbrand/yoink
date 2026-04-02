# Contributing

## Code Quality

### Python

```bash
uv run ruff check --fix  # Linting with auto-fix
uv run ruff format       # Code formatting
uv run ty check          # Type checking
```

### Orchestration Linter

Skill files in `skills/*/SKILL.md` and agent files in `agents/` must follow conventions enforced by the orchestration linter. Run it after editing any skill or agent file:

```bash
uv run python scripts/orchestration-linter.py           # lint + print flow
uv run python scripts/orchestration-linter.py --write    # lint + update ORCHESTRATION_FLOW.md
```

Run without flags to see the full list of rules (OL001–OL017) and the current orchestration flow. `ORCHESTRATION_FLOW.md` is auto-generated and should not be edited manually — always regenerate it with `--write` after making changes.

## Code Style & Philosophy

### Typing & Pattern Matching

- Prefer **explicit types** over raw dicts -- make invalid states unrepresentable where practical
- Prefer **typed variants over string literals** when the set of valid values is known
- Use **exhaustive pattern matching** (`match` in Python) so the type checker can verify all cases are handled
- Structure types to enable exhaustive matching when handling variants
- Prefer **shared internal functions over factory patterns** when extracting common logic from hooks or functions -- keep each export explicitly defined for better IDE navigation and readability

### Self-Documenting Code

- **Verbose naming**: Variable and function naming should read like documentation
- **Strategic comments**: Only for non-obvious logic or architectural decisions; avoid restating what code shows
