from typing import List
from sqlalchemy.orm import Session
from app.database.models import Message

class MessageRepository:
    """Repository class handling SQLite CRUD queries for Message models."""

    def create(self, db: Session, conversation_id: str, role: str, content: str) -> Message:
        """Saves a new message turn within a conversation."""
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return msg

    def list_by_conversation(self, db: Session, conversation_id: str) -> List[Message]:
        """Lists all messages in a conversation ordered chronologically (oldest first)."""
        return db.query(Message)\
            .filter(Message.conversation_id == conversation_id)\
            .order_by(Message.created_at.asc())\
            .all()

    def get_recent_history(self, db: Session, conversation_id: str, limit: int = 50) -> List[Message]:
        """Gets recent conversation messages up to a limit, ordered chronologically."""
        # Query newest messages first, then reverse them to restore chronological order
        subquery = db.query(Message)\
            .filter(Message.conversation_id == conversation_id)\
            .order_by(Message.created_at.desc())\
            .limit(limit)\
            .all()
        return list(reversed(subquery))

    def count(self, db: Session, conversation_id: str) -> int:
        """Counts the total messages in a specific conversation."""
        return db.query(Message).filter(Message.conversation_id == conversation_id).count()

# Global repository instance
message_repo = MessageRepository()
