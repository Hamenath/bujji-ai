import logging
import json
import asyncio
from typing import Dict, Any, List, Optional, AsyncIterator
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.repositories.conversation_repository import conversation_repo
from app.database.repositories.message_repository import message_repo
from app.database.repositories.agent_run_repository import agent_run_repo
from app.database.repositories.tool_execution_repository import tool_execution_repo
from app.services.context_builder import build_context
from app.services.conversation_service import conversation_service
from app.agent.orchestrator import agent_orchestrator
from app.llm.prompts import DEFAULT_SYSTEM_PROMPT

logger = logging.getLogger("app.services.agent_service")

class AgentService:
    """Orchestrates database persistence and coordinates REST/WebSocket execution for agents."""

    async def process_agent_message_non_stream(
        self, db: Session, conversation_id: str, content: str
    ) -> Dict[str, Any]:
        """
        Executes agent run synchronously for REST API:
        - Locks the conversation to avoid interleaving.
        - Saves user message.
        - Persists agent runs and tool executions as they happen.
        - Saves assistant message exactly once upon completion.
        """
        lock = await conversation_service.get_lock(conversation_id)
        async with lock:
            # 1. Verify conversation exists
            conv = conversation_repo.get(db, conversation_id)
            if not conv:
                raise ValueError(f"Conversation '{conversation_id}' not found.")

            # 2. Persist user message
            user_msg = message_repo.create(db, conversation_id, "user", content)

            # 3. Update title if needed
            if conv.title == "New Conversation":
                messages = message_repo.list_by_conversation(db, conversation_id)
                user_msgs = [m for m in messages if m.role == "user"]
                if len(user_msgs) == 1:
                    new_title = conversation_service.generate_title(content)
                    conversation_repo.update_title(db, conversation_id, new_title)

            # 4. Compile context
            messages = message_repo.list_by_conversation(db, conversation_id)
            context = build_context(messages, DEFAULT_SYSTEM_PROMPT)

            run_id = ""
            route = "direct"
            steps = []
            sources = []
            final_response = ""
            error_code = None
            status = "pending"
            step_count = 0

            stream = agent_orchestrator.execute(conversation_id, content, context, stream=False)
            async for event_type, event_data in stream:
                if event_type == "agent.started":
                    run_id = event_data["run_id"]
                    agent_run_repo.create(db, conversation_id, route="direct", user_message_id=user_msg.id, run_id=run_id)
                    agent_run_repo.update_status(db, run_id, status="routing")
                    status = "routing"
                    
                elif event_type == "agent.route.selected":
                    route = event_data["route"]
                    run = agent_run_repo.get(db, run_id)
                    if run:
                        run.route = route
                        db.commit()
                        
                elif event_type == "agent.plan.created":
                    agent_run_repo.update_status(db, run_id, status="planning")
                    status = "planning"
                    
                elif event_type == "tool.started":
                    agent_run_repo.update_status(db, run_id, status="executing")
                    status = "executing"
                    
                elif event_type == "tool.completed":
                    tool_execution_repo.create(
                        db,
                        agent_run_id=run_id,
                        step_number=event_data["step_number"],
                        tool_name=event_data["tool_name"],
                        arguments_json=json.dumps(event_data["arguments"]),
                        result_json=json.dumps(event_data["result"]),
                        success=True,
                        duration_ms=event_data["duration_ms"]
                    )
                    steps.append({
                        "step_number": event_data["step_number"],
                        "tool_name": event_data["tool_name"],
                        "success": True
                    })
                    step_count = max(step_count, event_data["step_number"])
                    
                elif event_type == "tool.failed":
                    tool_execution_repo.create(
                        db,
                        agent_run_id=run_id,
                        step_number=event_data["step_number"],
                        tool_name=event_data["tool_name"],
                        arguments_json=json.dumps(event_data["arguments"]),
                        result_json=None,
                        success=False,
                        duration_ms=event_data["duration_ms"],
                        error_code=event_data["error_code"]
                    )
                    steps.append({
                        "step_number": event_data["step_number"],
                        "tool_name": event_data["tool_name"],
                        "success": False
                    })
                    step_count = max(step_count, event_data["step_number"])
                    
                elif event_type == "response.chunk":
                    final_response = event_data["content"]
                    
                elif event_type == "agent.completed":
                    sources = event_data.get("sources", [])
                    assistant_msg = message_repo.create(db, conversation_id, "assistant", final_response)
                    agent_run_repo.complete(db, run_id, assistant_message_id=assistant_msg.id, step_count=step_count)
                    conversation_repo.touch(db, conversation_id)
                    status = "completed"
                    
                elif event_type == "agent.failed":
                    error_code = event_data["error_code"]
                    agent_run_repo.fail(db, run_id, error_code=error_code, step_count=step_count)
                    status = "failed"

            if status == "failed":
                raise ValueError(f"Agent run failed: {error_code}")

            return {
                "run_id": run_id,
                "conversation_id": conversation_id,
                "route": route,
                "status": status,
                "response": final_response,
                "steps": steps,
                "sources": sources
            }

    async def process_agent_message_stream(
        self, db: Session, conversation_id: str, content: str
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Executes agent run streamingly for WebSockets:
        - Locks the conversation to avoid race conditions.
        - Saves user message.
        - Persists agent runs and tool executions as they happen.
        - Yields real-time events to the caller.
        - Saves assistant response exactly once upon completion.
        """
        lock = await conversation_service.get_lock(conversation_id)
        async with lock:
            conv = conversation_repo.get(db, conversation_id)
            if not conv:
                yield {"type": "error", "data": {"code": "NOT_FOUND", "message": f"Conversation session '{conversation_id}' not found."}}
                return

            user_msg = message_repo.create(db, conversation_id, "user", content)
            yield {"type": "message.user.saved", "data": {"message_id": user_msg.id}}

            if conv.title == "New Conversation":
                messages = message_repo.list_by_conversation(db, conversation_id)
                user_msgs = [m for m in messages if m.role == "user"]
                if len(user_msgs) == 1:
                    new_title = conversation_service.generate_title(content)
                    conversation_repo.update_title(db, conversation_id, new_title)

            messages = message_repo.list_by_conversation(db, conversation_id)
            context = build_context(messages, DEFAULT_SYSTEM_PROMPT)

            run_id: str = ""
            route = "direct"
            accumulated_chunks = []
            step_count = 0
            status = "pending"

            stream = agent_orchestrator.execute(conversation_id, content, context, stream=True)
            try:
                async for event_type, event_data in stream:
                    if event_type == "agent.started":
                        run_id = event_data["run_id"]
                        agent_run_repo.create(db, conversation_id, route="direct", user_message_id=user_msg.id, run_id=run_id)
                        agent_run_repo.update_status(db, run_id, status="routing")
                        status = "routing"
                        
                    elif event_type == "agent.route.selected":
                        route = event_data["route"]
                        run = agent_run_repo.get(db, run_id)
                        if run:
                            run.route = route
                            db.commit()
                            
                    elif event_type == "agent.plan.created":
                        agent_run_repo.update_status(db, run_id, status="planning")
                        status = "planning"
                        
                    elif event_type == "tool.started":
                        agent_run_repo.update_status(db, run_id, status="executing")
                        status = "executing"
                        
                    elif event_type == "tool.completed":
                        tool_execution_repo.create(
                            db,
                            agent_run_id=run_id,
                            step_number=event_data["step_number"],
                            tool_name=event_data["tool_name"],
                            arguments_json=json.dumps(event_data["arguments"]),
                            result_json=json.dumps(event_data["result"]),
                            success=True,
                            duration_ms=event_data["duration_ms"]
                        )
                        step_count = max(step_count, event_data["step_number"])
                        client_data = {
                            "step_number": event_data["step_number"],
                            "tool_name": event_data["tool_name"],
                            "success": True,
                            "duration_ms": event_data["duration_ms"]
                        }
                        yield {"type": "tool.completed", "data": client_data}
                        continue
                        
                    elif event_type == "tool.failed":
                        tool_execution_repo.create(
                            db,
                            agent_run_id=run_id,
                            step_number=event_data["step_number"],
                            tool_name=event_data["tool_name"],
                            arguments_json=json.dumps(event_data["arguments"]),
                            result_json=None,
                            success=False,
                            duration_ms=event_data["duration_ms"],
                            error_code=event_data["error_code"]
                        )
                        step_count = max(step_count, event_data["step_number"])
                        client_data = {
                            "step_number": event_data["step_number"],
                            "tool_name": event_data["tool_name"],
                            "success": False,
                            "error_code": event_data["error_code"]
                        }
                        yield {"type": "tool.failed", "data": client_data}
                        continue
                        
                    elif event_type == "response.chunk":
                        accumulated_chunks.append(event_data["content"])
                        
                    elif event_type == "agent.completed":
                        final_response = "".join(accumulated_chunks)
                        assistant_msg = message_repo.create(db, conversation_id, "assistant", final_response)
                        agent_run_repo.complete(db, run_id, assistant_message_id=assistant_msg.id, step_count=step_count)
                        conversation_repo.touch(db, conversation_id)
                        status = "completed"
                        
                    elif event_type == "agent.failed":
                        agent_run_repo.fail(db, run_id, error_code=event_data["error_code"], step_count=step_count)
                        status = "failed"
                        
                    yield {"type": event_type, "data": event_data}

            except asyncio.CancelledError:
                logger.warning(f"Agent stream processing cancelled for conversation: {conversation_id}")
                if run_id:
                    agent_run_repo.fail(db, run_id, error_code="AGENT_CANCELLED", step_count=step_count)
                yield {"type": "agent.failed", "data": {"run_id": run_id, "error_code": "AGENT_CANCELLED"}}
                raise

# Global service instance
agent_service = AgentService()
