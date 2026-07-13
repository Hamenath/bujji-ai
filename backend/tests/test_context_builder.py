import pytest
from app.services.context_builder import build_context
from app.llm.schemas import Message as LLMMessage

class DummyMessage:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

def test_context_builder_preserves_system_and_latest_message():
    """Test that context always starts with system prompt and ends with the newest message."""
    messages = [
        DummyMessage("user", "Hello"),
        DummyMessage("assistant", "Hi there"),
        DummyMessage("user", "What is the weather?")
    ]
    system_prompt = "You are a weather bot."
    
    result = build_context(messages, system_prompt, max_messages=10, max_chars=1000)
    
    assert len(result) == 4
    assert result[0].role == "system"
    assert result[0].content == system_prompt
    assert result[-1].role == "user"
    assert result[-1].content == "What is the weather?"
    assert result[1].content == "Hello"
    assert result[2].content == "Hi there"

def test_context_builder_trims_by_message_count():
    """Test that oldest messages are dropped when message count exceeds limit, preserving system + latest."""
    messages = [
        DummyMessage("user", "Turn 1"),
        DummyMessage("assistant", "Reply 1"),
        DummyMessage("user", "Turn 2"),
        DummyMessage("assistant", "Reply 2"),
        DummyMessage("user", "Turn 3"),
        DummyMessage("assistant", "Reply 3"),
        DummyMessage("user", "Turn 4 (Latest)")
    ]
    system_prompt = "Be brief."
    
    # max_messages=5. This means System Prompt (1) + Latest Message (1) + 3 history turns maximum.
    # Total selected turns = 3. We keep newest history turns: Turn 3, Reply 3, Reply 2 (going backwards).
    result = build_context(messages, system_prompt, max_messages=5, max_chars=1000)
    
    assert len(result) == 5
    assert result[0].role == "system"
    assert result[-1].content == "Turn 4 (Latest)"
    
    # Chronological ordering check
    assert result[1].content == "Reply 2"
    assert result[2].content == "Turn 3"
    assert result[3].content == "Reply 3"

def test_context_builder_trims_by_character_count():
    """Test that oldest history is dropped when aggregate character count exceeds limit."""
    messages = [
        DummyMessage("user", "Short turn"),
        DummyMessage("assistant", "Very long text that consumes character budget"),
        DummyMessage("user", "Keep this")
    ]
    system_prompt = "Short system prompt."
    
    # Budget check: len(system_prompt) = 21, len("Keep this") = 9. Total base = 30.
    # If limit is 60, we have 30 chars left.
    # "Short turn" is 10 chars. "Very long text..." is 43 chars.
    # Only "Short turn" will fit. The "Very long text..." will be skipped.
    result = build_context(messages, system_prompt, max_messages=10, max_chars=60)
    
    assert len(result) == 3
    assert result[0].role == "system"
    assert result[1].content == "Short turn"
    assert result[2].content == "Keep this"

def test_context_builder_unicode_safety():
    """Test that UTF-8 / multi-byte character strings are measured cleanly by char length."""
    messages = [
        DummyMessage("user", "안녕하세요 (Korean hello)"),
        DummyMessage("user", "Latest prompt")
    ]
    system_prompt = "Prompt"
    
    result = build_context(messages, system_prompt, max_messages=10, max_chars=200)
    assert len(result) == 3
    assert result[1].content == "안녕하세요 (Korean hello)"
