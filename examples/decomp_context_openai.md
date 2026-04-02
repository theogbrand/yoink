Decision: Decompose
Reasoning: openai is a vendor SDK. The core usage is
limited to instantiating a client and calling
chat.completions.create(), both of which are
straightforward to replace using httpx. The exception
coupling adds complexity but is manageable.
Category: API wrapper
Strategy: Replace with raw HTTP calls using httpx:
1. Create a lightweight client that takes api_key,
base_url, timeout and calls {base_url}/chat/completions
via httpx.post()
2. Remove inheritance from openai exception classes —
define independent exceptions
3. Replace openai._models.BaseModel usage in
types/utils.py with pydantic BaseModel
4. Replace openai.types.completion_usage.* imports with
custom equivalents
Functions to replace:
- openai.OpenAI() constructor
- client.chat.completions.create() and with_raw_response variant
- All openai exception base classes
- openai._models.BaseModel (alias for OpenAIObject)
- openai.types.completion_usage.CompletionTokensDetails, CompletionUsage, PromptTokensDetails
Acceptable sub-dependencies: httpx (for HTTP calls), pydantic (already used)
