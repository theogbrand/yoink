# Dependency Evaluation Policy

This policy evaluates a single dependency in isolation to decide whether to keep it or replace it with a lower-level implementation. Use this in **step 3** of the [Recursive Dependency Decomposition Workflow](recursive_decomposition.md): "evaluate whether to decompose further."

The policy is language-agnostic and focused on preventing unnecessary coupling and surface area.

---

## Replace by Default

The following categories should be replaced with lower-level implementations unless there is a specific reason to keep them:

*   **Vendor SDKs & API Wrappers** (e.g., `openai`, `slack-sdk`, `stripe-python`, `github3.py`, `boto3` for basic tasks).
    *   *Rationale:* High surface area. You typically only need 2-3 specific endpoints; a full SDK multiplies coupling and dependency risk.
    *   *Replacement strategy:* Write a lightweight, custom client using HTTP primitives (httpx, fetch, curl) and your project's data validation library (pydantic, zod). Map only the endpoints you actually call.

*   **AI/LLM "Glue" & Orchestration Frameworks** (e.g., `langchain`, `litellm`, `llama-index`).
    *   *Rationale:* Heavy transitive dependency trees. Core behavior is straightforward HTTP calls to a provider's API.
    *   *Replacement strategy:* Re-implement orchestration using standard control flow (if/while), string formatting, and direct HTTP calls to the provider's chat completion endpoint.

*   **Trivial Utilities** (e.g., `lodash`-equivalents, string/date manipulators).
    *   *Rationale:* Can be inlined with minimal code using language standard library.
    *   *Replacement strategy:* Write pure helper functions using standard library tools (itertools, datetime, collections, re in Python; lodash equivalents in JS; itertools in Rust).

*   **Deep/Unverifiable Dependency Trees.**
    *   *Rationale:* Packages with > 3 transitive dependencies create supply chain surface area and make auditing difficult.
    *   *Replacement strategy:* Extract and re-implement the core logic you need using a lower layer.

---

## Evaluation Framework for Unfamiliar Libraries

If a dependency does not match the above categories, apply this decision framework:

1.  **Does it implement a complex protocol?** (e.g., XML parsing, HTTP/2, Cryptography). If yes and it is well-governed → keep it.
2.  **Does it bridge to a lower-level language for performance/safety?** (e.g., bindings to C, Rust, or native code). If yes → likely worth keeping.
3.  **Is it solo-maintained without 2FA or recent commits?** If yes → replace it.
4.  **Can the core functionality be implemented in < 200 lines of code** using HTTP primitives or standard library? If yes → replace it.
