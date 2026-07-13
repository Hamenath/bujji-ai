from datetime import datetime, timezone
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class RouterDecision(BaseModel):
    """Decision model returned by the AgentRouter."""
    route: str = Field(..., description="The chosen route: 'direct' or 'agent'")
    reason_code: str = Field(..., description="A short machine-oriented reason code (e.g., 'NO_TOOL_REQUIRED', 'TOOL_REQUIRED')")

class PlanStep(BaseModel):
    """A single planned tool step in an action plan."""
    id: int = Field(..., description="Chronological step identifier starting at 1")
    description: str = Field(..., description="Human description of what the step performs")
    tool_name: str = Field(..., description="The name of the registered tool to execute")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Input arguments matching the tool's schema")

class ActionPlan(BaseModel):
    """A structured multi-step plan produced by the AgentPlanner."""
    goal: str = Field(..., description="Overall target goal for the request")
    steps: List[PlanStep] = Field(default_factory=list, description="Sequence of steps to satisfy the goal")

class AgentState(BaseModel):
    """The complete execution and runtime state of a single agent run."""
    run_id: str
    conversation_id: str
    user_message: str
    context: List[Dict[str, Any]] = Field(default_factory=list)
    route: Optional[str] = None
    plan: Optional[ActionPlan] = None
    current_step: int = 1
    completed_steps: List[Dict[str, Any]] = Field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    observations: List[Dict[str, Any]] = Field(default_factory=list)
    retry_counts: Dict[int, int] = Field(default_factory=dict)  # step_number -> retry_count
    sources: List[Dict[str, Any]] = Field(default_factory=list)  # Collected sources for citations
    status: str = "pending"  # "pending", "routing", "planning", "executing", "observing", "generating_final", "completed", "failed", "cancelled"
    final_response: Optional[str] = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    completed_at: Optional[datetime] = None
