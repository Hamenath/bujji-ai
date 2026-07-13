import logging
from app.core.config import settings
from app.agent.schemas import PlanStep
from app.tools.base import ToolResult
from pydantic import BaseModel, Field

logger = logging.getLogger("app.agent.observer")

class ObserverDecision(BaseModel):
    """Structured decision returned by the AgentObserver."""
    decision: str = Field(..., description="One of: 'continue', 'complete', 'retry', 'fail'")
    reason_code: str = Field(..., description="Short machine-oriented reason code")

class AgentObserver:
    """Class handling deterministic evaluation of tool outputs to direct the orchestrator loop."""

    def observe(
        self,
        step: PlanStep,
        result: ToolResult,
        total_steps: int,
        current_retry_count: int
    ) -> ObserverDecision:
        """Determines the next orchestrator action based on the step execution result."""
        
        # 1. Success path
        if result.success:
            if step.id >= total_steps:
                logger.info("All planned steps completed. Goal satisfied.")
                return ObserverDecision(decision="complete", reason_code="GOAL_SATISFIED")
            else:
                logger.info(f"Step {step.id} completed successfully. Proceeding to next step.")
                return ObserverDecision(decision="continue", reason_code="MORE_STEPS_REQUIRED")
        
        # 2. Failure path - check if error is retryable
        # Treat timeout, connection errors, and general exceptions as retryable
        retryable_errors = ["TOOL_TIMEOUT", "TOOL_EXCEPTION"]
        is_retryable = any(err in (result.error or "") for err in retryable_errors) or (not result.success and result.error is None)
            
        if is_retryable and current_retry_count < settings.AGENT_MAX_RETRIES_PER_STEP:
            logger.warning(f"Step {step.id} failed with retryable error. Attempt {current_retry_count + 1} of {settings.AGENT_MAX_RETRIES_PER_STEP + 1}.")
            return ObserverDecision(decision="retry", reason_code="RETRYABLE_TOOL_ERROR")
            
        # 3. Non-retryable error (or retries exhausted)
        reason = "NON_RETRYABLE_TOOL_ERROR"
        if result.error == "CONFIRMATION_REQUIRED":
            reason = "CONFIRMATION_REQUIRED"
        elif result.error == "BLOCKED_DANGEROUS":
            reason = "BLOCKED_DANGEROUS"
            
        logger.error(f"Step {step.id} failed with error '{result.error}'. Deciding to fail execution.")
        return ObserverDecision(decision="fail", reason_code=reason)

agent_observer = AgentObserver()
