# Library Decomposition Strategies

**Purpose:** Understand how different kinds of libraries decompose, and identify the next layer down for each category.

**How to use:** When evaluating a dependency for decomposition, classify it into one of the four categories below. The category tells you:
- How to decompose it (what strategy to use)
- Where to look for reference material (API docs, source code, etc.)
- What the "next layer down" is (what to replace it with)

**When to use this:** When you've decided a dependency should be decomposed and need guidance on how.

---

## Categories

Libraries fall into distinct categories, and each category decomposes differently:

- **API wrappers / SDK bindings** — Thin clients that map 1:1 to a remote API
  (e.g., `openai`, `stripe`, `boto3`, `octokit`). These encode auth, endpoint
  URLs, request/response shapes, and retry logic. The **next layer down** is raw
  HTTP calls using a lightweight HTTP client (httpx, fetch, curl). The primary
  reference when reimplementing is the **API documentation** — the wire protocol
  is the contract.
- **UX/orchestration layers** — Libraries that simplify or unify other SDKs
  (e.g., `litellm`, `langchain`, `passport`, `sqlalchemy`). These add
  convenience, provider abstraction, or workflow orchestration on top of lower
  layers. The **next layer down** is the underlying SDK(s) they wrap (e.g.,
  `openai` for litellm, provider SDKs for langchain). Decomposing means
  swapping in those underlying SDKs and reimplementing the orchestration logic
  yourself. The primary reference is the **library's source code** — read how it
  calls the layer below and what transformations it applies.
- **Utilities / data structures & algorithms** — Self-contained logic with no
  network dependency (e.g., `lodash`, `zod`, `pydantic`, `serde`, `date-fns`).
  These solve well-defined computational problems. The **next layer down** is
  standard library equivalents or inlined implementations using language builtins.
  Decomposing means extracting and inlining the specific functions you use.
  The primary reference is the **library's source code** — understanding how it
  handles edge cases (empty inputs, unicode, overflow, off-by-one) guides your
  implementation.
- **Frameworks** — Opinionated runtime scaffolding that owns the control flow
  (e.g., `express`, `next.js`, `axum`, `django`). Decomposing a framework is
  rarely worth it — you're usually better off working within it or replacing it
  wholly with a different framework. There is no "next layer down" within the
  same framework; decomposition here means a complete framework swap.

The category determines:
- **The next layer down** (which the orchestrator should target for future decomposition)
- **Where to look when reimplementing** (API docs vs. source code)
