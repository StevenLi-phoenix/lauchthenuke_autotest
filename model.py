from pydantic import BaseModel

class PromptModel(BaseModel):
    prompt: str
    FLAG_SUCCESS: bool
    FLAG_STOP: bool
