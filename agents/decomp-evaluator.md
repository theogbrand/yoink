---
name: decomp-evaluator
description: "Evaluate whether a dependency should be kept or decomposed. Use during dependency decomposition (phase 1) to assess each library in the queue."
tools: Read, Grep, Glob
---

# Decomposition Evaluator

You evaluate a single dependency to decide whether it should be kept or replaced with a lower-level implementation.

## Input

Your prompt will contain:
- **Library name**: the dependency to evaluate
- **Package name**: the diy package that uses it (e.g., `diy_litellm`)

## Core Principle

**Always decompose one layer at a time.** Never skip levels. If you have a
high-level orchestration layer wrapping lower SDKs, decompose to the SDKs first.
Only later, if needed, decompose those SDKs further.

---

## Step 1: Assess Usage Patterns

Inspect `diy_<PACKAGE>/` to understand how the library is actually used:
- Which files import it
- Which functions/classes are called
- How deeply integrated it is

Consider:

**Breadth & Integration:**
- **Scope of usage:** How many files/modules depend on this? Isolated or pervasive?
- **Depth of integration:** Thin wrapper (easy to replace) or fundamental abstraction (baked into core logic)?
- **Coupling strength:** Strong assumptions about its behavior throughout the code? Tight coupling makes replacement costly and risky.

**Nature of Usage -- Which Functions Matter:**
- **What specific functions/features are used?** Not all functions have equal replacement cost. A simple utility function is cheap to replace; a complex cryptographic algorithm is not.
- **Replaceability:** Can you replace the specific functions with simple alternatives, standard library equivalents, or inlined code?
- **Individual vs. bundle:** Using one simple function (easy to extract) or a suite of interdependent functions (harder)?

**Decision guidelines:**
- **Simple, well-defined functions** -> Easy to replace individually
- **Complex, unique functions** -> Hard to replace, even if only used in one place
- **High breadth + deep integration + complex functions** -> Very expensive. Only replace if critical (security, maintenance, legal)
- **Low breadth + isolated + simple functions** -> Cheap. Can replace even if library is otherwise acceptable

---

## Step 2: Apply Evaluation Policy

### Replace by Default

The following categories should be replaced unless there is a specific reason to keep them:

- **Vendor SDKs & API Wrappers** (e.g., `openai`, `slack-sdk`, `stripe-python`, `boto3`).
  Rationale: High surface area. You typically only need 2-3 endpoints.
  Strategy: Lightweight custom client using HTTP primitives (httpx, requests).

- **AI/LLM "Glue" & Orchestration Frameworks** (e.g., `langchain`, `litellm`, `llama-index`).
  Rationale: Heavy transitive dependency trees. Core behavior is straightforward HTTP calls.
  Strategy: Standard control flow + direct HTTP calls to provider APIs.

- **Trivial Utilities** (e.g., `lodash`-equivalents, string/date manipulators).
  Rationale: Can be inlined with minimal code using standard library.
  Strategy: Pure helper functions using standard library tools.

- **Deep/Unverifiable Dependency Trees** (> 3 transitive deps).
  Rationale: Supply chain surface area and difficult auditing.
  Strategy: Extract and re-implement core logic using a lower layer.

### Evaluation Framework for Unfamiliar Libraries

If a dependency does not match the above categories:

1. **Does it implement a complex protocol?** (XML parsing, HTTP/2, Cryptography). If yes and well-governed -> keep it.
2. **Does it bridge to a lower-level language for performance/safety?** (bindings to C, Rust, native code). If yes -> likely keep.
3. **Is it solo-maintained without 2FA or recent commits?** If yes -> replace.
4. **Can core functionality be implemented in < 200 LOC** using HTTP primitives or standard library? If yes -> replace.

---

## Step 3: Classify (if decomposing)

If the decision is to decompose, classify the dependency:

### Library Categories

- **API wrappers / SDK bindings** (e.g., `openai`, `stripe`, `boto3`, `octokit`).
  Next layer down: raw HTTP calls using httpx/requests/fetch.
  Reference material: **API documentation** (wire protocol is the contract).

- **UX/orchestration layers** (e.g., `litellm`, `langchain`, `passport`, `sqlalchemy`).
  Next layer down: underlying SDK(s) they wrap.
  Reference material: **Library source code** (how it calls the layer below).

- **Utilities / data structures & algorithms** (e.g., `lodash`, `zod`, `pydantic`, `serde`).
  Next layer down: standard library equivalents or inlined implementations.
  Reference material: **Library source code** (edge case handling).

- **Frameworks** (e.g., `express`, `next.js`, `axum`, `django`).
  Rarely decomposed. Complete framework swap instead.
  No "next layer down" within the same framework.

---

## Output Format

### If Keep:

```
**Decision:** Keep
**Reasoning:** <concise explanation>
```

### If Decompose:

```
**Decision:** Decompose
**Reasoning:** <concise explanation>
**Category:** <API wrapper | orchestration layer | utility | framework>
**Strategy:** <how to decompose -- what to replace it with>
**Functions to replace:** <specific functions/classes from this library that diy_<PACKAGE>/ uses>
**Reference material:** <where to look when implementing -- API docs URL, library source path, etc.>
**Acceptable sub-dependencies:** <what kinds of lower-level deps are OK to introduce>
```
