import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.repositories.message_repository import message_repo
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationDetailResponse,
    MessageCreate,
    MessageResponse
)
from app.services.conversation_service import conversation_service

logger = logging.getLogger("app.api.routes.conversations")

router = APIRouter(prefix="/conversations", tags=["Conversations System"])

@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(payload: ConversationCreate, db: Session = Depends(get_db)):
    """Creates a new conversation session."""
    conv = conversation_service.create_conversation(db, payload.title)
    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=0
    )

@router.get("", response_model=List[ConversationResponse])
def list_conversations(limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    """Retrieves list of all conversations ordered by active turns."""
    conversations = conversation_service.list_conversations(db, limit, offset)
    responses = []
    for conv in conversations:
        count = message_repo.count(db, conv.id)
        responses.append(ConversationResponse(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=count
        ))
    return responses

@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    """Retrieves conversation session metadata and all chronological messages."""
    conv = conversation_service.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Conversation session '{conversation_id}' not found."
        )
    
    messages = message_repo.list_by_conversation(db, conversation_id)
    return ConversationDetailResponse(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[
            MessageResponse(
                id=m.id,
                conversation_id=m.conversation_id,
                role=m.role,
                content=m.content,
                created_at=m.created_at
            )
            for m in messages
        ]
    )

@router.patch("/{conversation_id}", response_model=ConversationResponse)
def update_conversation(conversation_id: str, payload: ConversationUpdate, db: Session = Depends(get_db)):
    """Renames a conversation title manually."""
    conv = conversation_service.rename_conversation(db, conversation_id, payload.title)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Conversation session '{conversation_id}' not found."
        )
    
    count = message_repo.count(db, conversation_id)
    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=count
    )

@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: str, db: Session = Depends(get_db)):
    """Deletes a conversation session, cascade-deleting all related messages."""
    success = conversation_service.delete_conversation(db, conversation_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Conversation session '{conversation_id}' not found."
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.post("/{conversation_id}/messages")
async def send_message(conversation_id: str, payload: MessageCreate, db: Session = Depends(get_db)):
    """
    Sends a user chat prompt to the conversation session.
    Runs non-streaming local inference and returns user & assistant messages.
    """
    try:
        result = await conversation_service.process_message_non_stream(
            db, conversation_id, payload.content
        )
        return {
            "user_message": MessageResponse.model_validate(result["user_message"]),
            "assistant_message": MessageResponse.model_validate(result["assistant_message"])
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to process prompt in conversation {conversation_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference execution failed: {str(e)}"
        )
