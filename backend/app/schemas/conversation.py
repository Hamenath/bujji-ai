from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

class MessageCreate(BaseModel):
    """Schema to validate incoming message content."""
    content: str = Field(..., description="Message text content")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Message content cannot be empty or only whitespace.")
        return cleaned

class MessageResponse(BaseModel):
    """Schema representing a persisted message."""
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

class ConversationCreate(BaseModel):
    """Schema to create a new conversation."""
    title: Optional[str] = Field(default=None, description="Optional title for the conversation")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            if not cleaned:
                raise ValueError("Conversation title cannot be empty or only whitespace.")
            return cleaned
        return v

class ConversationUpdate(BaseModel):
    """Schema to update conversation properties."""
    title: str = Field(..., description="New title for the conversation")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Conversation title cannot be empty or only whitespace.")
        return cleaned

class ConversationResponse(BaseModel):
    """Schema representing basic conversation metadata."""
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = Field(default=0)

    class Config:
        from_attributes = True

class ConversationDetailResponse(BaseModel):
    """Schema representing conversation metadata and complete message history."""
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse]

    class Config:
        from_attributes = True
