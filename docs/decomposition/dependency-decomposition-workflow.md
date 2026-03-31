# Recursive Dependency Decomposition Workflow

**Purpose:** Evaluate a single dependency and decide whether it should be decomposed. If yes, provide classification and guidance on how to decompose it.

**How to use:** Run this workflow once per dependency. Input a dependency, receive a decision (keep or decompose) and if decomposing, receive a category and strategy.

**Scope:** This is a single-pass evaluation tool. An external system orchestrates calling this repeatedly on new sub-dependencies.

## Core Principle

**Always decompose one layer at a time.** Never skip levels. If you have a
high-level orchestration layer wrapping lower SDKs, decompose to the SDKs first.
Only later, if needed, decompose those SDKs further. This ensures:
- Changes are reviewable and auditable at each step
- You can stop at intermediate layers if they prove suitable
- Issues are localized to the most recent decomposition

---

## Step 1: Evaluate whether to decompose

**Input:** A single dependency to evaluate.

**Tool does:**
- Consult [decomposition-evaluation-policy.md](decomposition-evaluation-policy.md) (or your project's equivalent evaluation policy)
- Assess the dependency using both the library's characteristics and its usage patterns in
  your codebase
- Apply the evaluation framework to decide: Keep or Decompose?

**Output:** A decision—either "keep this dependency" or "decompose"

---

### If decision is "Keep"

**Output:**
- **Decision:** Keep this dependency
- **Reasoning:** Concise explanation for the decision. Examples:
  - "Not in 'replace by default' category and well-maintained"
  - "Used only as simple utility functions — cheap to keep, expensive to replace"
  - "Deeply integrated throughout codebase — high cost of decomposition outweighs benefits"
  - "Implements complex protocol — safer and more reliable to keep"

**Workflow ends.** The orchestrator will not call this workflow on this dependency again.

---

### If decision is "Decompose"

Proceed to step 2.

---

## Step 2: Classify the dependency

**Tool does:**
- Consult [library-decomposition-strategies.md](library-decomposition-strategies.md) to classify the dependency (API wrapper,
  orchestration layer, utility, or framework)
- For the identified category, determine:
  - **How to decompose it** (drop to raw HTTP, swap underlying SDK, inline functions, etc.)
  - **What reference material to use** (API docs, library source)

**Output:**
- **Functions to replace** — the specific functions, classes, or features from this library that `diy_<package>/` actually uses (e.g., `openai.chat.completions.create`, `httpx.AsyncClient.post`). Inspect the current `diy_<package>/` source to identify these. This scopes the implementation work — only these need to be replaced, not the entire library.
- **Category** of the dependency
- **Decomposition strategy** (category-specific approach)
- **Reference material** (where to look when implementing)
- **Acceptable sub-dependencies** (what kinds are reasonable to introduce)
- **Priority targets for future iterations** (which sub-dependencies to evaluate next)
