import json
import logging
import asyncio
from typing import Dict, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.database import get_db
from app.database.repositories.conversation_repository import conversation_repo
from app.websocket.connection_manager import connection_manager
from app.services.conversation_service import conversation_service
from app.services.agent_service import agent_service

logger = logging.getLogger("app.api.routes.websocket")

router = APIRouter(prefix="/ws", tags=["WebSocket Chat"])

# Module-level tracking of active tasks and associated runs
active_agent_tasks: Dict[str, asyncio.Task] = {}
conversation_runs: Dict[str, List[str]] = {}

@router.websocket("/chat/{conversation_id}")
async def websocket_chat(websocket: WebSocket, conversation_id: str, db: Session = Depends(get_db)):
    """
    WebSocket endpoint for real-time conversation.
    - Accepts client connection.
    - Listens for structured JSON 'message.send' and 'agent.run' events.
    - Supports 'agent.cancel' for cancellation.
    - Streams LLM chunks/agent events back to the client using structured events.
    - Saves user and assistant messages exactly once.
    """
    
    # 1. Accept and register WebSocket connection
    try:
        conv = conversation_repo.get(db, conversation_id)
        if not conv:
            await websocket.accept()
            await websocket.send_json({
                "type": "error",
                "data": {"code": "NOT_FOUND", "message": f"Conversation session '{conversation_id}' not found."}
            })
            await websocket.close()
            return

        await connection_manager.connect(websocket, conversation_id)
        
        # Send connection ready confirmation
        await connection_manager.send_json_event(
            websocket, 
            "connection.ready", 
            {"conversation_id": conversation_id}
        )

        # Helper to execute agent in a background task
        async def run_agent_task(content_val: str):
            current_task = asyncio.current_task()
            if current_task is None:
                return
            run_id_val = None
            try:
                stream = agent_service.process_agent_message_stream(db, conversation_id, content_val)
                async for response_event in stream:
                    ev_type = response_event["type"]
                    ev_data = response_event["data"]
                    
                    if ev_type == "agent.started":
                        run_id_val = ev_data["run_id"]
                        active_agent_tasks[run_id_val] = current_task
                        if conversation_id not in conversation_runs:
                            conversation_runs[conversation_id] = []
                        conversation_runs[conversation_id].append(run_id_val)
                        
                    await connection_manager.send_json_event(
                        websocket,
                        ev_type,
                        ev_data
                    )
            except asyncio.CancelledError:
                logger.info(f"Agent run task {run_id_val} cancelled cleanly.")
            except Exception as ex:
                logger.error(f"Error executing background agent task: {ex}", exc_info=True)
                await connection_manager.send_json_event(
                    websocket,
                    "error",
                    {"code": "SERVER_ERROR", "message": f"An error occurred during agent execution: {str(ex)}"}
                )
            finally:
                if run_id_val:
                    active_agent_tasks.pop(run_id_val, None)
                    if conversation_id in conversation_runs:
                        if run_id_val in conversation_runs[conversation_id]:
                            conversation_runs[conversation_id].remove(run_id_val)

        # 2. Main receive loop
        while True:
            raw_text = await websocket.receive_text()
            
            # Check length constraint
            if len(raw_text) > settings.WEBSOCKET_MAX_MESSAGE_CHARS:
                await connection_manager.send_json_event(
                    websocket,
                    "error",
                    {"code": "MESSAGE_TOO_LARGE", "message": f"Message size limit exceeded. Max is {settings.WEBSOCKET_MAX_MESSAGE_CHARS} chars."}
                )
                continue

            try:
                event = json.loads(raw_text)
            except json.JSONDecodeError:
                await connection_manager.send_json_event(
                    websocket, 
                    "error", 
                    {"code": "MALFORMED_JSON", "message": "The message sent was not valid JSON."}
                )
                continue

            event_type = event.get("type")
            event_data = event.get("data", {})

            if event_type not in ["message.send", "agent.run", "agent.cancel"]:
                await connection_manager.send_json_event(
                    websocket, 
                    "error", 
                    {"code": "INVALID_EVENT", "message": f"Event type '{event_type}' not supported. Expected 'message.send', 'agent.run', or 'agent.cancel'."}
                )
                continue

            if event_type == "agent.cancel":
                cancel_run_id = event_data.get("run_id")
                if not cancel_run_id:
                    await connection_manager.send_json_event(
                        websocket,
                        "error",
                        {"code": "MISSING_RUN_ID", "message": "Missing 'run_id' in cancellation request."}
                    )
                    continue
                if cancel_run_id in active_agent_tasks:
                    logger.info(f"Cancelling active agent run: {cancel_run_id}")
                    active_agent_tasks[cancel_run_id].cancel()
                else:
                    await connection_manager.send_json_event(
                        websocket,
                        "error",
                        {"code": "RUN_NOT_FOUND", "message": f"Active agent run '{cancel_run_id}' not found or completed."}
                    )
                continue

            content = event_data.get("content", "").strip()
            if not content:
                await connection_manager.send_json_event(
                    websocket, 
                    "error", 
                    {"code": "EMPTY_CONTENT", "message": "Message content cannot be empty."}
                )
                continue

            # 3. Stream processing
            if event_type == "message.send":
                try:
                    stream = conversation_service.process_message_stream(db, conversation_id, content)
                    async for response_event in stream:
                        await connection_manager.send_json_event(
                            websocket,
                            response_event["type"],
                            response_event["data"]
                        )
                except Exception as e:
                    logger.error(f"Error handling streaming message in WebSocket session: {e}")
                    await connection_manager.send_json_event(
                        websocket,
                        "error",
                        {"code": "SERVER_ERROR", "message": f"An error occurred during message generation: {str(e)}"}
                    )
            elif event_type == "agent.run":
                # Start agent loop as a background task to allow cancel events to be received
                asyncio.create_task(run_agent_task(content))

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected from conversation: {conversation_id}")
    except Exception as e:
        logger.error(f"Unexpected WebSocket error: {e}")
    finally:
        # Cancel any active tasks for this conversation on disconnect
        if conversation_id in conversation_runs:
            for r_id in list(conversation_runs[conversation_id]):
                if r_id in active_agent_tasks:
                    logger.info(f"Cancelling active task {r_id} due to WebSocket disconnect.")
                    active_agent_tasks[r_id].cancel()
            conversation_runs.pop(conversation_id, None)
        connection_manager.disconnect(websocket, conversation_id)
