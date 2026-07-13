import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.conversation import MessageCreate
from app.schemas.agent import AgentRunResponse
from app.services.agent_service import agent_service

logger = logging.getLogger("app.api.routes.agent")

router = APIRouter(prefix="/conversations", tags=["Agent System"])

@router.post("/{conversation_id}/agent", response_model=AgentRunResponse, status_code=status.HTTP_201_CREATED)
async def process_agent_message(
    conversation_id: str,
    payload: MessageCreate,
    db: Session = Depends(get_db)
):
    """
    Processes a user message turn via the Agent system.
    Runs structured routing, planning, internal tool execution, and final response generation.
    Returns the final run ID, steps executed, and generated response.
    """
    try:
        result = await agent_service.process_agent_message_non_stream(
            db, conversation_id, payload.content
        )
        return AgentRunResponse(**result)
    except ValueError as e:
        logger.error(f"Value error in agent execution: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to process agent message in conversation {conversation_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent execution failed: {str(e)}"
        )
