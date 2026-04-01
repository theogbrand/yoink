Decomp
* Uses external evaluator agent to write tests independently (debate with planner agent just like Anthropic does it?)
* After generation of single task/phase, run evaluator’s test and if it fails, we inject context to edit files to pass the test (without hacking)
* Pass criteria is when all tasks and tests pass
    * add more complex quality gates later, assume passing tests written by evaluator agent works
* UX: maybe after decomp, it should launch in a sandbox and notify user to merge the PR
* Agent should systematically breakdown the levels of abstraction slowly without skipping too far ahead. For example, you should rely on high-level SDKs in the first step, and then in a second step, break down those SDKs into the base functionality as well.
    * the agent should understand that different libraries are broken down in different kinds of taxonomies like SDKs that wrap APIs, SDKs that simplify UX over other SDKs, utilities like data structures and algos.
* Clear distinction between the tests we take from the official library and the ones we write. Some features only have compound tests, so we need to write the tests for them.

Beyond writing a naive AI-written test and running the original SDK with the user specified functionality, can we do better
    - becuase if this is not well written, the quality of everything else downstream will depend on this definition of correctness
    - go search original library for relevant tests, if not write an AI test, or give user ability to write their acceptance criteria

- we should rewrite non-pytest tests to standardize to PyTest, otherwise handle how to handle non PyTest TBD
- we should record down the history of all the reasoning, input, and outputs between all the steps in the workflow, so that we can read what the agent decided to do at every step. 