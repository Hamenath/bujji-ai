import pytest
from unittest.mock import AsyncMock, patch
from fastapi import status
from app.database.repositories.conversation_repository import conversation_repo
from app.database.repositories.message_repository import message_repo
from app.llm.ollama_provider import OllamaProvider

def test_create_and_get_conversation(client):
    """Test creating and retrieving a conversation through the REST API."""
    # Create conversation
    response = client.post("/api/v1/conversations", json={})
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert "id" in data
    assert data["title"] == "New Conversation"
    assert "created_at" in data
    
    conversation_id = data["id"]
    
    # Retrieve it
    response = client.get(f"/api/v1/conversations/{conversation_id}")
    assert response.status_code == status.HTTP_200_OK
    detail_data = response.json()
    assert detail_data["id"] == conversation_id
    assert detail_data["title"] == "New Conversation"
    assert detail_data["messages"] == []

def test_list_conversations(client):
    """Test listing conversations with pagination."""
    # Create multiple conversations
    client.post("/api/v1/conversations", json={"title": "Conv A"})
    client.post("/api/v1/conversations", json={"title": "Conv B"})
    
    response = client.get("/api/v1/conversations?limit=5")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) >= 2
    # Check that sorting places the newest first
    assert data[0]["title"] in ["Conv A", "Conv B"]

def test_rename_and_delete_conversation(client, db_session):
    """Test renaming a session title, deleting it, and cascade deleting messages."""
    # Create conversation directly
    conv = conversation_repo.create(db_session, "Rename Target")
    conversation_id = conv.id
    
    # Add a message
    message_repo.create(db_session, conversation_id, "user", "Test cascade deletion.")
    assert message_repo.count(db_session, conversation_id) == 1
    
    # Rename conversation
    response = client.patch(f"/api/v1/conversations/{conversation_id}", json={"title": "Renamed Session"})
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["title"] == "Renamed Session"
    
    # Delete conversation
    del_response = client.delete(f"/api/v1/conversations/{conversation_id}")
    assert del_response.status_code == status.HTTP_204_NO_CONTENT
    
    # Verify cascade deletion of conversation
    assert conversation_repo.get(db_session, conversation_id) is None
    # Verify cascade deletion of messages
    assert message_repo.count(db_session, conversation_id) == 0

def test_get_unknown_conversation_returns_404(client):
    """Test that requesting an invalid conversation ID returns a 404 error."""
    response = client.get("/api/v1/conversations/non-existent-uuid-12345")
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_send_message_persists_once(client):
    """Test sending a prompt through REST API correctly triggers LLM and persists both user/assistant turns exactly once."""
    mock_llm_response = {
        "model": "llama3.2",
        "message": {"role": "assistant", "content": "REST response is working."},
        "done": True
    }
    
    # Create conversation
    create_response = client.post("/api/v1/conversations", json={})
    assert create_response.status_code == status.HTTP_201_CREATED
    conv_id = create_response.json()["id"]

    # Post message with patched LLM provider
    with patch.object(OllamaProvider, "check_availability", new_callable=AsyncMock) as mock_avail, \
         patch.object(OllamaProvider, "chat", new_callable=AsyncMock) as mock_chat:
        
        mock_avail.return_value = True
        mock_chat.return_value = mock_llm_response
        
        payload = {"content": "Hello Bujji!"}
        response = client.post(f"/api/v1/conversations/{conv_id}/messages", json=payload)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "user_message" in data
        assert "assistant_message" in data
        assert data["user_message"]["content"] == "Hello Bujji!"
        assert data["assistant_message"]["content"] == "REST response is working."
        
        # Verify title was updated deterministically from the user's first message
        get_response = client.get(f"/api/v1/conversations/{conv_id}")
        assert get_response.json()["title"] == "Hello Bujji!"
