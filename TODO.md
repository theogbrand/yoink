Decomp
* Uses external evaluator agent to write tests independently (debate with planner agent just like Anthropic does it?)
* After generation of single task/phase, run evaluator’s test and if it fails, we inject context to edit files to pass the test (without hacking)
* Pass criteria is when all tasks and tests pass
    * add more complex quality gates later, assume passing tests written by evaluator agent works
* UX: maybe after decomp, it should launch in a sandbox and notify user to merge the PR
* Agent should systematically breakdown the levels of abstraction slowly without skipping too far ahead. For example, you should rely on high-level SDKs in the first step, and then in a second step, break down those SDKs into the base functionality as well.
    * the agent should understand that different libraries are broken down in different kinds of taxonomies like SDKs that wrap APIs, SDKs that simplify UX over other SDKs, utilities like data structures and algos.
* Clear distinction between the tests we take from the official library and the ones we write. Some features only have compound tests, so we need to write the tests for them.

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
- [ ] Matching tests with the release that we downloaded
- [ ] We should record down the history of all the reasoning, input, and outputs between all the steps in the workflow, so that we can read what the agent decided to do at every step. 

## Inner Ralph Loop
- [ ] Add the SubAgent Stop Hook to call inner-diy-loop-stop-hook.sh and tie it to the decomp-implementer agent 
- [ ] rewrite imports from old library to newly written library to pass tests
- [] Use SubAgent Spawn Hook in decomp-implementor agent to read the inner-diy-loop.local.md file and execute the inner ralph loop until all Level 0 tests pass or max iterations are reached.