---
name: diy-decomp
description: "Curate tests then decompose dependencies"
argument-hint: "PROMPT [--url GITHUB_URL] [--package PACKAGE_NAME] [--skip-discovery]"
allowed-tools: ["Skill(setup *)", "Skill(test-curate *)", "Skill(decompose *)"]
disable-model-invocation: true
---

# DIY Decomp

Run the full DIY decomposition pipeline by invoking skills in sequence:

### 1. Setup

Invoke `/setup $ARGUMENTS` to scaffold the project (clone repo, install library).

**Wait for setup to complete before proceeding.**

### 2. Test Curation

Invoke `/test-curate $ARGUMENTS` to discover and generate tests, validate against the real library, rewrite imports, and sanity check.

**Wait for test curation to complete before proceeding.**

### 3. Dependency Decomposition

Invoke `/decompose $ARGUMENTS` to run the decomposition loop.
