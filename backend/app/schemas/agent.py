from pydantic import BaseModel
from typing import List, Optional

class AgentStepResponse(BaseModel):
    """Schema representing a single executed step in the agent run response."""
    step_number: int
    tool_name: str
    success: bool

class SourceResponse(BaseModel):
    id: int
    title: Optional[str] = None
    url: str
    domain: Optional[str] = None
    snippet: Optional[str] = None
    accessed_at: Optional[str] = None
    source_type: Optional[str] = None

class AgentRunResponse(BaseModel):
    """Schema representing the full REST response for an agent execution run."""
    run_id: str
    conversation_id: str
    route: str
    status: str
    response: str
    steps: List[AgentStepResponse]
    sources: List[SourceResponse] = []

