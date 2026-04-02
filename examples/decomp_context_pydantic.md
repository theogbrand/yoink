Decision: Decompose
Reasoning: Pydantic is used only as simple data containers
  with no validation. ~15 model classes use only BaseModel,
  Field, PrivateAttr, model_dump(), and model_config. No
validators are used.
Category: Utility
Strategy: Replace pydantic BaseModel with plain Python
classes. Use __init__ for field declarations, custom
model_dump() methods for serialization.
Functions to replace:
- BaseModel → plain Python classes
- Field(default=None) → regular init parameters with defaults
- PrivateAttr() → Direct assignment in __init__
- model_dump() → custom serialization method
- model_config with extra='allow' → __setattr__ permissiveness or **kwargs in __init__
Acceptable sub-dependencies: None. Standard library only.
