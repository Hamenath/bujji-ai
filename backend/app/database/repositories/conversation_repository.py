from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from app.database.models import Conversation

class ConversationRepository:
    """Repository class handling SQLite CRUD queries for Conversation models."""

    def create(self, db: Session, title: Optional[str] = None) -> Conversation:
        """Creates a new conversation record."""
        conv = Conversation(title=title or "New Conversation")
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return conv

    def get(self, db: Session, conversation_id: str) -> Optional[Conversation]:
        """Retrieves a conversation by its unique ID."""
        return db.query(Conversation).filter(Conversation.id == conversation_id).first()

    def list_all(self, db: Session, limit: int = 100, offset: int = 0) -> List[Conversation]:
        """Lists all conversations ordered by updated_at descending (newest activity first)."""
        return db.query(Conversation)\
            .order_by(Conversation.updated_at.desc())\
            .offset(offset)\
            .limit(limit)\
            .all()

    def update_title(self, db: Session, conversation_id: str, title: str) -> Optional[Conversation]:
        """Updates the conversation title."""
        conv = self.get(db, conversation_id)
        if conv:
            conv.title = title
            conv.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
            db.refresh(conv)
        return conv

    def touch(self, db: Session, conversation_id: str) -> Optional[Conversation]:
        """Updates the updated_at timestamp to the current UTC time."""
        conv = self.get(db, conversation_id)
        if conv:
            conv.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
            db.refresh(conv)
        return conv

    def delete(self, db: Session, conversation_id: str) -> bool:
        """Deletes a conversation by its ID. Triggers cascade deletion of messages in SQLite."""
        conv = self.get(db, conversation_id)
        if conv:
            db.delete(conv)
            db.commit()
            return True
        return False

# Global repository instance
conversation_repo = ConversationRepository()
