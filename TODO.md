Decomp
* Uses external evaluator agent to write tests independently (debate with planner agent just like Anthropic does it?)
* After generation of single task/phase, run evaluator’s test and if it fails, we inject context to edit files to pass the test (without hacking)
* Pass criteria is when all tasks and tests pass
    * add more complex quality gates later, assume passing tests written by evaluator agent works
* UX: maybe after decomp, it should launch in a sandbox and notify user to merge the PR
* Agent should systematically breakdown the levels of abstraction slowly without skipping too far ahead. For example, you should rely on high-level SDKs in the first step, and then in a second step, break down those SDKs into the base functionality as well.
    * the agent should understand that different libraries are broken down in different kinds of taxonomies like SDKs that wrap APIs, SDKs that simplify UX over other SDKs, utilities like data structures and algos.
* Clear distinction between the tests we take from the official library and the ones we write. Some features only have compound tests, so we need to write the tests for them.
- [ ] Matching tests with the release that we downloaded
- [ ] We should record down the history of all the reasoning, input, and outputs between all the steps in the workflow, so that we can read what the agent decided to do at every step. 

## Inner Ralph Loop
- [ ] Add the SubAgent Stop Hook to call inner-yoink-loop-stop-hook.sh and tie it to the decomp-implementer agent 
- [ ] rewrite imports from old library to newly written library to pass tests
- [] Use SubAgent Spawn Hook in decomp-implementor agent to read the inner-yoink-loop.local.md file and execute the inner ralph loop until all Level 0 tests pass or max iterations are reached.