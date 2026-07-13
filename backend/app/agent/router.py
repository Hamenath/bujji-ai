import logging
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.llm.schemas import Message as LLMMessage, ChatRequest
from app.services.chat_service import chat_service
from app.agent.schemas import RouterDecision
from app.agent.prompts import ROUTER_SYSTEM_PROMPT
import re
import json

logger = logging.getLogger("app.agent.router")

def extract_json(text: str) -> Optional[dict]:
    """Robust helper to extract the first JSON object from a string."""
    text_clean = text.strip()
    text_clean = re.sub(r"^```(?:json)?\n", "", text_clean, flags=re.IGNORECASE)
    text_clean = re.sub(r"\n```$", "", text_clean)
    text_clean = text_clean.strip()
    try:
        return json.loads(text_clean)
    except json.JSONDecodeError:
        pass
    match = re.search(r"(\{.*\})", text_clean, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None

class AgentRouter:
    """Class handling routing of user requests to direct response vs tool agent workflows."""

    async def route(self, context: List[LLMMessage]) -> RouterDecision:
        """Determines whether to route to 'direct' or 'agent' execution path."""
        logger.info("Routing user request...")
        
        # Override the first message (system prompt) in the context window
        router_messages = []
        for i, msg in enumerate(context):
            if i == 0 and msg.role == "system":
                router_messages.append(LLMMessage(role="system", content=ROUTER_SYSTEM_PROMPT))
            else:
                router_messages.append(LLMMessage(role=msg.role, content=msg.content))
                
        if not router_messages or router_messages[0].role != "system":
            router_messages.insert(0, LLMMessage(role="system", content=ROUTER_SYSTEM_PROMPT))

        retries = 0
        max_retries = settings.AGENT_ROUTER_PARSE_RETRIES
        
        while retries <= max_retries:
            content = ""
            try:
                chat_req = ChatRequest(
                    messages=router_messages,
                    stream=False,
                    options={"temperature": 0.0}
                )
                response = await chat_service.get_chat_completion(chat_req)
                content = response.get("message", {}).get("content", "")
                
                parsed = extract_json(content)
                if parsed:
                    decision = RouterDecision(**parsed)
                    if decision.route in ["direct", "agent"]:
                        logger.info(f"Routed request to '{decision.route}' (reason: {decision.reason_code})")
                        return decision
                
                logger.warning(f"Failed to parse router output on attempt {retries + 1}. Content: {content}")
            except Exception as e:
                logger.warning(f"Error in router execution on attempt {retries + 1}: {e}")
                
            retries += 1
            if retries <= max_retries:
                router_messages.append(LLMMessage(role="assistant", content=content if 'content' in locals() else "Error"))
                router_messages.append(LLMMessage(role="user", content="Your previous response was not valid JSON. Please reply with ONLY the strict JSON object matching the format: {\"route\": \"direct\" | \"agent\", \"reason_code\": \"...\"}."))

        # Fallback to direct path
        logger.error("Router parse failed. Falling back to 'direct' route.")
        return RouterDecision(route="direct", reason_code="ROUTER_PARSE_FAILURE")

agent_router = AgentRouter()
