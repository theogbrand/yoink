---
name: decomp-evaluator
description: "Evaluate whether a dependency should be kept or decomposed. Use during dependency decomposition (phase 1) to assess each library in the queue."
tools: Read, Grep, Glob
---

# Decomposition Evaluator

Evaluate a single dependency: **keep** or **decompose one layer down**.

**Core rule:** Always decompose one layer at a time. Never skip levels.

## Input

- **library_name**: The dependency to evaluate
- **package_name**: The diy package that uses it (e.g., `diy_litellm`)

## Steps

### 1. Assess usage

Inspect `diy_<PACKAGE>/` for how the library is actually used:
- Which files import it, which functions/classes are called
- Breadth (isolated vs. pervasive) and depth (thin wrapper vs. baked into core logic)
- Replaceability: can the specific functions used be replaced with simple code, stdlib, or inlined logic?

**Quick heuristics:**
- Simple functions + isolated usage -> cheap to replace
- Complex functions OR deep integration -> expensive, only replace if critical
- Using one function from a large library -> easy to extract

### 2. Evaluate

#### Foundational Primitives

These are the low-level layer that decomposition usually stops at unless there is an unusual project-specific reason to avoid them or asked to be replaced explicitly by the user.

| Domain | Libraries | Why keep |
|---|---|---|
| Networking & Web | `httpx`, `websockets`, `FastAPI`, `Starlette`, `uvicorn` | They ARE the HTTP layer; replacement means raw sockets |
| Validation & Serialization | `pydantic` v2, `orjson`, `PyYAML` | Non-trivial coercion/validation logic; C/Rust-accelerated JSON; battle-tested YAML parser |
| Database & State | `SQLAlchemy` v2 core, `psycopg` v3, `asyncpg`, `valkey-py` | Wire protocol implementations + connection management. Prefer `valkey-py` over `redis-py` |
| Security & Crypto | `cryptography`, `PyJWT` | OpenSSL C bindings; subtle algorithm/timing concerns |
| Observability & Config | `structlog`, `opentelemetry-api`, `pydantic-settings` | Cross-cutting infrastructure; no supply-chain benefit to replacing |
| Image Processing | `Pillow` | C-accelerated codec for dozens of formats |
| gRPC & Protobuf | `grpcio`, `protobuf` | Google-maintained binary wire protocol + codegen via C bindings |

#### Replacement Signals

These are indicators, not automatic verdicts. Weigh against step 1 findings and the primitives list above.

| Pattern | Signal | Typical strategy |
|---|---|---|
| **Vendor SDKs** (`openai`, `slack-sdk`, `boto3`) | High surface area, you use 2-3 endpoints | Custom `httpx` client |
| **AI/LLM orchestration** (`langchain`, `litellm`) | Heavy transitive deps, core is HTTP + retry | Direct HTTP calls + standard control flow |
| **Trivial utilities** (lodash-equivalents, date helpers) | Inlineable with stdlib | Pure helper functions |
| **Deep dep trees** (> 3 transitive deps) | Supply-chain surface area | Extract and reimplement core logic |

#### Unfamiliar Libraries

For libraries that don't clearly fit either list, reason from first principles about what makes something a foundational primitive versus a replaceable layer.

**What makes a foundational primitive:**

- Implements a wire protocol, binary format, or spec-driven standard (HTTP/2, WebSocket, protobuf, XML parsing) — reimplementing means tracking an evolving spec
- Bridges to C/Rust/system libraries for correctness or performance (crypto, image codecs, compression) — the binding IS the value
- Well-governed: multiple maintainers, 2FA enforced, regular releases, security audit history
- Used broadly across the ecosystem — battle-tested edge cases you'd rediscover painfully
- Replacement would require reimplementing > 500 LOC of non-trivial logic

**What makes a replaceable layer:**

- Wraps another library's API with convenience methods — the underlying library does the real work
- Primary value is DX (nicer syntax, auto-retry, config merging) rather than correctness-critical logic
- Solo-maintained, no 2FA, stale commits, or unclear governance
- Heavy transitive dependency tree (> 3 deps) for functionality you use narrowly
- Core functionality you actually use is < 200 LOC with stdlib or a kept primitive
- Acts as a compatibility shim across providers — you only use one provider

**Grey areas — lean toward keeping:**

- Library is well-governed but you're unsure about complexity -> keep, revisit later
- Library has C bindings but you only use a pure-Python subset -> still keep, the binding signals non-trivial domain
- Library is large but you use it pervasively -> replacing is expensive and risky, keep unless supply-chain concern is acute

### 3. Classify

- If **decision is Decompose** then **classify the library and continue**.
- If **decision is Keep** then **skip this step**.

| Category | Next layer down | Reference material |
|---|---|---|
| **API wrappers** (`openai`, `stripe`, `boto3`) | Raw HTTP calls via httpx | API documentation |
| **Orchestration layers** (`litellm`, `langchain`) | Underlying SDK(s) they wrap | Library source code |
| **Utilities** (`lodash`, `zod`) | Stdlib or inlined implementations | Library source code |
| **Frameworks** (`express`, `django`, `axum`) | Rarely decomposed; full swap instead | — |

## Output

- **decision**: "Keep" or "Decompose"
- **reasoning**: Concise explanation of the verdict

If **Decompose**, also include:
- **category**: API wrapper | orchestration layer | utility | framework
- **strategy**: What to replace it with
- **functions_to_replace**: Specific functions/classes used by diy_<PACKAGE>/
- **reference_material**: API docs URL or library source path
- **acceptable_sub_dependencies**: What lower-level deps are OK to introduce
