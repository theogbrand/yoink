Diy-loop
* add npm/github package URL as an argument so it can kick off "test search agent" to pull in the relevant test files
    * uses **subagents** to “study every file in tests/* using separate subagents and document in /specs/*.md and link the implementation as citations in the specification“
* Uses external evaluator agent to write tests independently (debate with planner agent just like Anthropic does it?)
* After generation of single task/phase, run evaluator’s test and if it fails, we inject context to edit files to pass the test (without hacking)
* Pass criteria is when all tasks and tests pass
    * add more complex quality gates later, assume passing tests written by evaluator agent works
* Agent should systematically breakdown the levels of attraction slowly without skipping too far ahead. For example, you should rely on high-level SDKs in the first step, and then in a second step, break down those SDKs into the base functionality as well. 
* Clear distiinction between the tests we take from the official library and the ones we write. Some features only have compound tests, so we need to write the tests for them.