from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from app.database.models import ToolExecution

class ToolExecutionRepository:
    """Repository class handling SQLite CRUD queries for ToolExecution models."""

    def create(
        self,
        db: Session,
        agent_run_id: str,
        step_number: int,
        tool_name: str,
        arguments_json: str,
        result_json: Optional[str] = None,
        success: bool = True,
        duration_ms: int = 0,
        error_code: Optional[str] = None
    ) -> ToolExecution:
        """Saves a new tool execution record."""
        exec_record = ToolExecution(
            agent_run_id=agent_run_id,
            step_number=step_number,
            tool_name=tool_name,
            arguments_json=arguments_json,
            result_json=result_json,
            success=success,
            duration_ms=duration_ms,
            error_code=error_code
        )
        db.add(exec_record)
        db.commit()
        db.refresh(exec_record)
        return exec_record

    def list_by_run(self, db: Session, agent_run_id: str) -> List[ToolExecution]:
        """Lists all tool executions in an agent run ordered by step number ascending."""
        return db.query(ToolExecution)\
            .filter(ToolExecution.agent_run_id == agent_run_id)\
            .order_by(ToolExecution.step_number.asc())\
            .all()

# Global repository instance
tool_execution_repo = ToolExecutionRepository()
