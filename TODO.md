# Diy-loop TODO

## Phase 0: Test Curation
- [x] Add npm/github package URL as an argument so it can kick off "test search agent" to pull in the relevant test files
- [x] Use subagents to:
    - [x] Study every file in tests/* using separate subagents
    - [ ] Document findings in /specs/*.md
    - [ ] Link the implementation as citations in the specification (requires writing the spec first)
- [ ] Use an external evaluator agent to write tests independently (debate with planner agent, similar to Anthropic approach)

## Phase X: Raph Inner Loop
- [ ] After generation of a single task/phase:
    - [ ] Run evaluator's test
    - [ ] If it fails, inject context to edit files to pass the test (without hacking)
- [ ] Ensure pass criteria: all tasks and tests must pass
    - [ ] Add more complex quality gates later (for now, assume passing evaluator agent tests is sufficient)
- [ ] UX: After the /diy-loop command, launch in a sandbox and notify user to merge the PR
- [ ] Spin up subagent to complete TODO item and update progress.txt or check off TODO item
    - [ ] Send back progress to main agent with a structured report defined by us

## Phase Y: Recursive Decomposition
- [ ] Agent should systematically break down the levels of abstraction without skipping ahead:
    - [ ] First, rely on high-level SDKs
    - [ ] In second step, break down SDK calls to base functions
    - [ ] Recognize taxonomies in libraries (e.g. SDKs that wrap APIs, SDKs that simplify UX, utility libraries with data structures/algorithms)

## Misc
- [ ] Clearly distinguish between tests sourced from the official library and new tests we write
    - [ ] Identify features with only compound tests and write additional tests for them if needed
- [ ] Go beyond naive AI-written tests:
    - [ ] Recognize that initial correctness definition greatly affects downstream quality
    - [ ] Search original library for relevant tests
    - [ ] If no tests found, write AI test or enable user to define acceptance criteria
- [ ] Rewrite non-pytest tests to standardize on PyTest
    - [ ] Otherwise, define how to handle non-PyTest test cases (TBD)