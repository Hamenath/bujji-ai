import json
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import status

from app.database.repositories.conversation_repository import conversation_repo
from app.database.repositories.message_repository import message_repo
from app.llm.ollama_provider import OllamaProvider

def test_websocket_connection_not_found(client):
    """Test that connection to invalid conversation returns error and closes."""
    with client.websocket_connect("/api/v1/ws/chat/invalid-id-999") as websocket:
        response = websocket.receive_json()
        assert response["type"] == "error"
        assert response["data"]["code"] == "NOT_FOUND"

def test_websocket_chat_streaming_success(client, db_session):
    """Test standard WebSocket streaming conversation message exchange and persistence."""
    # Create conversation
    conv = conversation_repo.create(db_session, "WS Conversation")
    conversation_id = conv.id

    async def mock_generator(*args, **kwargs):
        chunks = [
            {"message": {"role": "assistant", "content": "Hello"}, "model": "llama3.2", "done": False},
            {"message": {"role": "assistant", "content": " Bujji"}, "model": "llama3.2", "done": False},
            {"message": {"role": "assistant", "content": "!"}, "model": "llama3.2", "done": True}
        ]
        for chunk in chunks:
            yield chunk

    # Connect to websocket
    with patch.object(OllamaProvider, "check_availability", new_callable=AsyncMock) as mock_avail, \
         patch.object(OllamaProvider, "chat", new_callable=AsyncMock) as mock_chat:
        
        mock_avail.return_value = True
        mock_chat.return_value = mock_generator()
        
        with client.websocket_connect(f"/api/v1/ws/chat/{conversation_id}") as websocket:
            # 1. Connection ready check
            ready_event = websocket.receive_json()
            assert ready_event["type"] == "connection.ready"
            assert ready_event["data"]["conversation_id"] == conversation_id
            
            # 2. Send message
            payload = {
                "type": "message.send",
                "data": {"content": "Help me stream."}
            }
            websocket.send_text(json.dumps(payload))
            
            # 3. Receive user saved event
            user_saved = websocket.receive_json()
            assert user_saved["type"] == "message.user.saved"
            
            # 4. Receive response started event
            started = websocket.receive_json()
            assert started["type"] == "response.started"
            
            # 5. Receive response chunk events
            chunk1 = websocket.receive_json()
            assert chunk1["type"] == "response.chunk"
            assert chunk1["data"]["content"] == "Hello"
            
            chunk2 = websocket.receive_json()
            assert chunk2["type"] == "response.chunk"
            assert chunk2["data"]["content"] == " Bujji"
            
            chunk3 = websocket.receive_json()
            assert chunk3["type"] == "response.chunk"
            assert chunk3["data"]["content"] == "!"
            
            # 6. Receive response completed event
            completed = websocket.receive_json()
            assert completed["type"] == "response.completed"
            assert completed["data"]["content"] == "Hello Bujji!"
            
            # Verify exactly one user message and one assistant message are saved in database
            db_messages = message_repo.list_by_conversation(db_session, conversation_id)
            assert len(db_messages) == 2
            assert db_messages[0].role == "user"
            assert db_messages[0].content == "Help me stream."
            assert db_messages[1].role == "assistant"
            assert db_messages[1].content == "Hello Bujji!"

def test_websocket_chat_malformed_json(client, db_session):
    """Test that sending malformed JSON text returns a structured JSON error event."""
    conv = conversation_repo.create(db_session, "WS Error test")
    conversation_id = conv.id

    with client.websocket_connect(f"/api/v1/ws/chat/{conversation_id}") as websocket:
        # Connection ready
        websocket.receive_json()
        
        # Send bad JSON text
        websocket.send_text("{bad-json-format")
        
        # Read error event
        error_event = websocket.receive_json()
        assert error_event["type"] == "error"
        assert error_event["data"]["code"] == "MALFORMED_JSON"

def test_websocket_chat_invalid_event_type(client, db_session):
    """Test that sending an unsupported event type returns a structured JSON error event."""
    conv = conversation_repo.create(db_session, "WS Error test 2")
    conversation_id = conv.id

    with client.websocket_connect(f"/api/v1/ws/chat/{conversation_id}") as websocket:
        # Connection ready
        websocket.receive_json()
        
        # Send invalid event type
        payload = {
            "type": "invalid.type",
            "data": {"content": "testing"}
        }
        websocket.send_text(json.dumps(payload))
        
        # Read error event
        error_event = websocket.receive_json()
        assert error_event["type"] == "error"
        assert error_event["data"]["code"] == "INVALID_EVENT"
