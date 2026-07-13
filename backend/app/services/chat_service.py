import logging
from typing import Any, Optional
from app.llm.model_router import model_router
from app.llm.schemas import GenerateRequest, ChatRequest
from app.llm.prompts import DEFAULT_SYSTEM_PROMPT

logger = logging.getLogger("app.services.chat_service")

class ChatService:
    """Handles core conversational logic, sitting between routes and the LLM provider router."""

    async def generate_completion(self, payload: GenerateRequest, provider_name: Optional[str] = None) -> Any:
        """Handles single prompt generation routing and default system prompts."""
        provider = model_router.get_provider(provider_name)
        if not payload.system_prompt:
            payload.system_prompt = DEFAULT_SYSTEM_PROMPT
        return await provider.generate(payload)

    async def get_chat_completion(self, payload: ChatRequest, provider_name: Optional[str] = None) -> Any:
        """Handles conversational dialogue completion routing and default system prompts."""
        provider = model_router.get_provider(provider_name)
        if not payload.system_prompt:
            payload.system_prompt = DEFAULT_SYSTEM_PROMPT
        return await provider.chat(payload)

# Singleton service instance
chat_service = ChatService()
