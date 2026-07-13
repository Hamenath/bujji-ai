import asyncio
import logging
from typing import Dict, Any, List, Optional, AsyncIterator
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.repositories.conversation_repository import conversation_repo
from app.database.repositories.message_repository import message_repo
from app.database.models import Conversation, Message
from app.services.context_builder import build_context
from app.services.chat_service import chat_service
from app.llm.schemas import ChatRequest as LLMChatRequest
from app.llm.prompts import DEFAULT_SYSTEM_PROMPT

logger = logging.getLogger("app.services.conversation_service")

class ConversationService:
    """Coordinates session lifecycle, message storage, context building, and provider execution."""

    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}
        self._lock_creation_lock = asyncio.Lock()

    async def get_lock(self, conversation_id: str) -> asyncio.Lock:
        """Retrieves or creates a unique asynchronous lock per conversation ID."""
        async with self._lock_creation_lock:
            if conversation_id not in self._locks:
                self._locks[conversation_id] = asyncio.Lock()
            return self._locks[conversation_id]

    def generate_title(self, content: str) -> str:
        """Generates a deterministic initial conversation title based on the first user message."""
        # Normalize whitespace and strip newlines
        single_line = " ".join(content.strip().split())
        limit = settings.CONVERSATION_TITLE_MAX_LENGTH
        if len(single_line) <= limit:
            return single_line
        # Truncate and add ellipsis
        return single_line[:limit].rstrip() + "..."

    def create_conversation(self, db: Session, title: Optional[str] = None) -> Conversation:
        """Creates a new conversation session."""
        return conversation_repo.create(db, title)

    def get_conversation(self, db: Session, conversation_id: str) -> Optional[Conversation]:
        """Retrieves conversation metadata and sessions."""
        return conversation_repo.get(db, conversation_id)

    def list_conversations(self, db: Session, limit: int = 100, offset: int = 0) -> List[Conversation]:
        """Lists active conversation sessions, ordered by last update."""
        return conversation_repo.list_all(db, limit, offset)

    def rename_conversation(self, db: Session, conversation_id: str, title: str) -> Optional[Conversation]:
        """Renames a conversation title manually."""
        return conversation_repo.update_title(db, conversation_id, title)

    def delete_conversation(self, db: Session, conversation_id: str) -> bool:
        """Deletes a conversation session, cascade-deleting messages."""
        # Remove active lock if present to avoid memory leak
        if conversation_id in self._locks:
            self._locks.pop(conversation_id, None)
        return conversation_repo.delete(db, conversation_id)

    async def process_message_non_stream(
        self, db: Session, conversation_id: str, user_content: str
    ) -> Dict[str, Any]:
        """
        Processes a user message non-streamingly:
        - Locks the conversation to avoid interleaving.
        - Persists user prompt.
        - Updates default title if it's the first message.
        - Trims conversation context.
        - Calls ChatService.
        - Persists assistant response.
        """
        lock = await self.get_lock(conversation_id)
        async with lock:
            # 1. Verify conversation exists
            conv = conversation_repo.get(db, conversation_id)
            if not conv:
                raise ValueError(f"Conversation '{conversation_id}' not found.")

            # 2. Persist user message
            user_msg = message_repo.create(db, conversation_id, "user", user_content)

            # 3. Update title if current title is default
            if conv.title == "New Conversation":
                # Only update if this is the first user message
                messages = message_repo.list_by_conversation(db, conversation_id)
                user_msgs = [m for m in messages if m.role == "user"]
                if len(user_msgs) == 1:
                    new_title = self.generate_title(user_content)
                    conversation_repo.update_title(db, conversation_id, new_title)

            # 4. Fetch history and compile trimmed context
            messages = message_repo.list_by_conversation(db, conversation_id)
            context = build_context(messages, DEFAULT_SYSTEM_PROMPT)

            # 5. Execute LLM completion request
            chat_req = LLMChatRequest(messages=context, stream=False)
            response_payload = await chat_service.get_chat_completion(chat_req)

            assistant_text = response_payload.get("message", {}).get("content", "")

            # 6. Save assistant message and update session timestamps
            assistant_msg = message_repo.create(db, conversation_id, "assistant", assistant_text)
            conversation_repo.touch(db, conversation_id)

            return {
                "user_message": user_msg,
                "assistant_message": assistant_msg
            }

    async def process_message_stream(
        self, db: Session, conversation_id: str, user_content: str
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Processes a user message streamingly:
        - Locks the conversation to avoid race conditions.
        - Yields progress events (user saved, response started, response chunks, completion).
        - Persists user prompt and the accumulated assistant response at the end.
        """
        lock = await self.get_lock(conversation_id)
        async with lock:
            # 1. Verify conversation exists
            conv = conversation_repo.get(db, conversation_id)
            if not conv:
                yield {"type": "error", "data": {"code": "NOT_FOUND", "message": f"Conversation '{conversation_id}' not found."}}
                return

            # 2. Persist user message
            user_msg = message_repo.create(db, conversation_id, "user", user_content)
            yield {"type": "message.user.saved", "data": {"message_id": user_msg.id}}

            # 3. Update title if needed
            if conv.title == "New Conversation":
                messages = message_repo.list_by_conversation(db, conversation_id)
                user_msgs = [m for m in messages if m.role == "user"]
                if len(user_msgs) == 1:
                    new_title = self.generate_title(user_content)
                    conversation_repo.update_title(db, conversation_id, new_title)

            # 4. Fetch history and compile trimmed context
            messages = message_repo.list_by_conversation(db, conversation_id)
            context = build_context(messages, DEFAULT_SYSTEM_PROMPT)

            # 5. Call LLM in streaming mode
            chat_req = LLMChatRequest(messages=context, stream=True)
            yield {
                "type": "response.started", 
                "data": {
                    "provider": "ollama", 
                    "model": chat_req.model or settings.OLLAMA_MODEL
                }
            }

            try:
                stream = await chat_service.get_chat_completion(chat_req)
                
                accumulated_text = []
                async for chunk in stream:
                    content_chunk = chunk.get("message", {}).get("content", "")
                    if content_chunk:
                        accumulated_text.append(content_chunk)
                        yield {"type": "response.chunk", "data": {"content": content_chunk}}

                # 6. Save complete assistant response
                full_response = "".join(accumulated_text)
                if full_response.strip():
                    assistant_msg = message_repo.create(db, conversation_id, "assistant", full_response)
                    conversation_repo.touch(db, conversation_id)
                    yield {
                        "type": "response.completed", 
                        "data": {
                            "message_id": assistant_msg.id, 
                            "content": full_response
                        }
                    }
                else:
                    yield {"type": "error", "data": {"code": "EMPTY_RESPONSE", "message": "LLM returned an empty response."}}

            except Exception as e:
                logger.error(f"Error during streaming response for conversation {conversation_id}: {e}")
                yield {"type": "error", "data": {"code": "LLM_ERROR", "message": f"Inference execution failed: {str(e)}"}}

# Global service instance
conversation_service = ConversationService()
