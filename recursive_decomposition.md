# Recursive Dependency Decomposition Workflow

When building functionality that depends on external APIs or third-party logic,
decompose dependencies recursively from highest to lowest level:

1. **Start with the highest-level dependency that solves the problem.** Official
   SDKs, battle-tested libraries (e.g., litellm, langchain, passport,
   sqlalchemy), well-maintained community packages. These encode correct
   behavior, handle edge cases, and are continuously updated. Keep your wrapper
   code thin.

2. **Write contract tests against the current layer.** Assert on inputs/outputs
   and behavior, not implementation details. These tests define what "correct"
   means and survive all future decomposition.

3. **Evaluate whether to decompose further.** If the dependency is too heavy,
   pulls in too much, or you only need a slice of it — go to step 4. If not,
   stop here.

4. **Replace with the next layer down.** Swap in a narrower dependency, inline
   specific functionality, or drop to a lower-level library. Use the previous
   layer's source code as your reference implementation (more reliable than
   docs). Rerun the contract tests. Green means you preserved behavior.

5. **Go back to step 3.** Repeat until you've reached the right level of
   abstraction for your needs.

## Stop at primitives

The recursion bottoms out at foundational libraries that are battle-tested,
stable, and not worth reimplementing unless you have a strong, specific reason
(binary size, platform constraints, zero-dep requirement):

- **Python:** httpx, pydantic, click, pathlib, asyncio
- **TypeScript:** zod, fetch/undici, commander, path
- **Rust:** serde, tokio, reqwest, clap

Reimplementing these costs more than it saves and introduces bugs the originals
solved years ago.

## Testing across layers

- **Contract tests** (behavior/IO) are written once at the top and reused at
  every level of decomposition.
- **Implementation tests** (wire format, headers, URLs) are added as a secondary
  layer only after decomposition stabilizes.
- If contract tests break during decomposition, the replacement is wrong — fix
  the replacement, not the test.
