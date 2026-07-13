import logging
from typing import List, Any, Optional
from app.core.config import settings
from app.llm.schemas import Message as LLMMessage

logger = logging.getLogger("app.services.context_builder")

def build_context(
    messages: List[Any], 
    system_prompt: str,
    max_messages: Optional[int] = None,
    max_chars: Optional[int] = None
) -> List[LLMMessage]:
    """
    Constructs a context window for local LLM generation.
    - Prepend the system prompt as the first message.
    - Always preserves the latest message in the list.
    - Pulls from recent conversation history (newest to oldest) until
      max_messages or max_chars is reached.
    - Restores chronological order before returning.
    """
    limit_messages = max_messages or settings.MAX_CONTEXT_MESSAGES
    limit_chars = max_chars or settings.MAX_CONTEXT_CHARS

    # Filter out any system role messages in the history to prevent duplicate system prompts
    history = [m for m in messages if m.role != "system"]

    if not history:
        return [LLMMessage(role="system", content=system_prompt)]

    # Preserve the last message (this is the newest user prompt)
    newest = history[-1]
    newest_llm_message = LLMMessage(role=newest.role, content=newest.content)

    # Context history turns to pull from
    prior_turns = history[:-1]

    # Initialize counter with system prompt and latest user message lengths
    current_chars = len(system_prompt) + len(newest_llm_message.content)
    selected_turns: List[LLMMessage] = []

    # Iterate backwards from newest prior turns to oldest
    for msg in reversed(prior_turns):
        # We always reserve 2 slots for System Prompt + Newest message
        if len(selected_turns) >= (limit_messages - 2):
            logger.debug(f"Trimming reached max message limit: {limit_messages}")
            break

        msg_len = len(msg.content)
        if current_chars + msg_len > limit_chars:
            logger.debug(f"Trimming reached max character limit: {limit_chars}")
            continue

        selected_turns.append(LLMMessage(role=msg.role, content=msg.content))
        current_chars += msg_len

    # Re-sort prior history turns chronologically (oldest to newest)
    selected_turns.reverse()

    # Build final message list
    context_list = [LLMMessage(role="system", content=system_prompt)]
    context_list.extend(selected_turns)
    context_list.append(newest_llm_message)

    return context_list
