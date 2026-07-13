from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import Session
from app.database.models import AgentRun

class AgentRunRepository:
    """Repository class handling SQLite CRUD queries for AgentRun models."""

    def create(
        self, 
        db: Session, 
        conversation_id: str, 
        route: str, 
        user_message_id: Optional[str] = None,
        run_id: Optional[str] = None
    ) -> AgentRun:
        """Creates a new agent run record."""
        run = AgentRun(
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            route=route,
            status="pending"
        )
        if run_id:
            run.id = run_id
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    def get(self, db: Session, run_id: str) -> Optional[AgentRun]:
        """Retrieves an agent run by its unique ID."""
        return db.query(AgentRun).filter(AgentRun.id == run_id).first()

    def list_by_conversation(self, db: Session, conversation_id: str, limit: int = 100) -> List[AgentRun]:
        """Lists agent runs in a conversation, ordered chronologically (newest first)."""
        return db.query(AgentRun)\
            .filter(AgentRun.conversation_id == conversation_id)\
            .order_by(AgentRun.started_at.desc())\
            .limit(limit)\
            .all()

    def update_status(self, db: Session, run_id: str, status: str, step_count: Optional[int] = None) -> Optional[AgentRun]:
        """Updates the status and step count of an agent run."""
        run = self.get(db, run_id)
        if run:
            run.status = status
            if step_count is not None:
                run.step_count = step_count
            db.commit()
            db.refresh(run)
        return run

    def complete(self, db: Session, run_id: str, assistant_message_id: Optional[str] = None, step_count: Optional[int] = None) -> Optional[AgentRun]:
        """Marks an agent run as completed."""
        run = self.get(db, run_id)
        if run:
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            if assistant_message_id:
                run.assistant_message_id = assistant_message_id
            if step_count is not None:
                run.step_count = step_count
            db.commit()
            db.refresh(run)
        return run

    def fail(self, db: Session, run_id: str, error_code: str, step_count: Optional[int] = None) -> Optional[AgentRun]:
        """Marks an agent run as failed with a specific error code."""
        run = self.get(db, run_id)
        if run:
            run.status = "failed"
            run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            run.error_code = error_code
            if step_count is not None:
                run.step_count = step_count
            db.commit()
            db.refresh(run)
        return run

# Global repository instance
agent_run_repo = AgentRunRepository()
