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

## Library taxonomy

Before decomposing, understand what kind of dependency you're looking at. Libraries
fall into distinct categories, and each category decomposes differently:

- **API wrappers / SDK bindings** — Thin clients that map 1:1 to a remote API
  (e.g., `openai`, `stripe`, `boto3`, `octokit`). These encode auth, endpoint
  URLs, request/response shapes, and retry logic. Decomposing means dropping to
  raw HTTP calls against the same API. The primary reference when reimplementing
  is the **API documentation** — the wire protocol is the contract. Test against
  request/response shapes, auth flows, and error codes.
- **UX/orchestration layers** — Libraries that simplify or unify other SDKs
  (e.g., `litellm`, `langchain`, `passport`, `sqlalchemy`). These add
  convenience, provider abstraction, or workflow orchestration on top of lower
  layers. Decomposing means swapping in the underlying SDK they wrap. The primary
  reference is the **library's source code** — read how it calls the layer below
  and what transformations it applies. Test against the transformed outputs and
  behavioral guarantees the library provides.
- **Utilities / data structures & algorithms** — Self-contained logic with no
  network dependency (e.g., `lodash`, `zod`, `pydantic`, `serde`, `date-fns`).
  These solve well-defined computational problems. Decomposing means inlining the
  specific functions you use. The primary reference is the **library's source
  code and test suite** — these reveal the edge cases (empty inputs, unicode,
  overflow, off-by-one) that the library already handles. Test against logical
  correctness and edge case coverage.
- **Frameworks** — Opinionated runtime scaffolding that owns the control flow
  (e.g., `express`, `next.js`, `axum`, `django`). Decomposing a framework is
  rarely worth it — you're usually better off working within it or replacing it
  wholesale.

The category determines both where to look when reimplementing (API docs vs.
source code vs. test suites) and what your contract tests should assert on (wire
format vs. transformed outputs vs. logical edge cases).

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
