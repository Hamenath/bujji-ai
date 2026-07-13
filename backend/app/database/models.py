import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.database.database import Base

def utc_now() -> datetime:
    """Returns a timezone-naive UTC datetime for database compatibility."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

class SystemCheck(Base):
    """A minimal database model to verify migrations, schema creation, and queries."""
    __tablename__ = "system_checks"
    __allow_unmapped__ = True

    id: Any = Column(Integer, primary_key=True, index=True)
    checked_at: Any = Column(DateTime, default=utc_now)
    status: Any = Column(String, default="healthy")

class Conversation(Base):
    """A user conversation session containing multiple message turns."""
    __tablename__ = "conversations"
    __allow_unmapped__ = True

    id: Any = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    title: Any = Column(String, default="New Conversation", nullable=False)
    created_at: Any = Column(DateTime, default=utc_now, nullable=False)
    updated_at: Any = Column(DateTime, default=utc_now, nullable=False)

    messages: Any = relationship(
        "Message", 
        back_populates="conversation", 
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    agent_runs: Any = relationship(
        "AgentRun",
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

class Message(Base):
    """An individual text message in a conversation sequence."""
    __tablename__ = "messages"
    __allow_unmapped__ = True

    id: Any = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    conversation_id: Any = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Any = Column(String, nullable=False)  # "system", "user", "assistant"
    content: Any = Column(String, nullable=False)
    created_at: Any = Column(DateTime, default=utc_now, nullable=False)

    conversation: Any = relationship("Conversation", back_populates="messages")

class AgentRun(Base):
    """Represents a structured execution run of an agent for a conversation turn."""
    __tablename__ = "agent_runs"
    __allow_unmapped__ = True

    id: Any = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    conversation_id: Any = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_message_id: Any = Column(String, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True)
    assistant_message_id: Any = Column(String, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True)
    route: Any = Column(String, nullable=False)  # "direct", "agent"
    status: Any = Column(String, nullable=False)  # "pending", "routing", "planning", "executing", "observing", "generating_final", "completed", "failed", "cancelled"
    step_count: Any = Column(Integer, default=0, nullable=False)
    started_at: Any = Column(DateTime, default=utc_now, nullable=False)
    completed_at: Any = Column(DateTime, nullable=True)
    error_code: Any = Column(String, nullable=True)

    conversation: Any = relationship("Conversation", back_populates="agent_runs")
    tool_executions: Any = relationship(
        "ToolExecution", 
        back_populates="agent_run", 
        cascade="all, delete-orphan",
        passive_deletes=True
    )

class ToolExecution(Base):
    """Represents a single tool invocation step within an agent run."""
    __tablename__ = "tool_executions"
    __allow_unmapped__ = True

    id: Any = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    agent_run_id: Any = Column(String, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_number: Any = Column(Integer, nullable=False)
    tool_name: Any = Column(String, nullable=False)
    arguments_json: Any = Column(String, nullable=False)
    result_json: Any = Column(String, nullable=True)
    success: Any = Column(Boolean, nullable=False)
    duration_ms: Any = Column(Integer, nullable=False)
    error_code: Any = Column(String, nullable=True)
    created_at: Any = Column(DateTime, default=utc_now, nullable=False)

    agent_run: Any = relationship("AgentRun", back_populates="tool_executions")
