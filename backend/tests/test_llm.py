import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import status

from app.llm.ollama_provider import OllamaProvider
from app.core.config import settings

def test_llm_status_offline(client):
    """Test /llm/status route when Ollama service is unavailable/offline."""
    with patch.object(OllamaProvider, "check_availability", new_callable=AsyncMock) as mock_avail:
        mock_avail.return_value = False
        
        response = client.get("/api/v1/llm/status")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["ollama_status"] == "offline"
        assert data["installed_models"] == []
        assert "hardware_detected" in data
        assert "cpu" in data["hardware_detected"]
        assert "gpu" in data["hardware_detected"]

def test_llm_status_online(client):
    """Test /llm/status route when Ollama service is online and returning installed models."""
    mock_models = [
        {"name": "llama3.2:latest", "model": "llama3.2:latest", "details": {"parameter_size": "3B"}}
    ]
    with patch.object(OllamaProvider, "check_availability", new_callable=AsyncMock) as mock_avail, \
         patch.object(OllamaProvider, "get_local_models", new_callable=AsyncMock) as mock_models_list:
        
        mock_avail.return_value = True
        mock_models_list.return_value = mock_models
        
        response = client.get("/api/v1/llm/status")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["ollama_status"] == "online"
        assert len(data["installed_models"]) == 1
        assert data["installed_models"][0]["name"] == "llama3.2:latest"

def test_llm_models_endpoint_offline(client):
    """Test that /llm/models raises 503 error if Ollama is offline."""
    with patch.object(OllamaProvider, "check_availability", new_callable=AsyncMock) as mock_avail:
        mock_avail.return_value = False
        
        response = client.get("/api/v1/llm/models")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

def test_llm_generate_non_streaming(client):
    """Test non-streaming /llm/generate route under normal conditions."""
    mock_response = {
        "model": "llama3.2",
        "response": "Hello there! I am your AI brain.",
        "done": True
    }
    with patch.object(OllamaProvider, "check_availability", new_callable=AsyncMock) as mock_avail, \
         patch.object(OllamaProvider, "generate", new_callable=AsyncMock) as mock_gen:
        
        mock_avail.return_value = True
        mock_gen.return_value = mock_response
        
        payload = {
            "prompt": "Say hello",
            "model": "llama3.2",
            "stream": False
        }
        response = client.post("/api/v1/llm/generate", json=payload)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["text"] == "Hello there! I am your AI brain."
        assert data["model"] == "llama3.2"
        assert data["done"] is True

def test_llm_chat_non_streaming(client):
    """Test non-streaming /llm/chat route under normal conditions."""
    mock_response = {
        "model": "llama3.2",
        "message": {"role": "assistant", "content": "I am doing well, thank you!"},
        "done": True
    }
    with patch.object(OllamaProvider, "check_availability", new_callable=AsyncMock) as mock_avail, \
         patch.object(OllamaProvider, "chat", new_callable=AsyncMock) as mock_chat:
        
        mock_avail.return_value = True
        mock_chat.return_value = mock_response
        
        payload = {
            "messages": [
                {"role": "user", "content": "How are you?"}
            ],
            "model": "llama3.2",
            "stream": False
        }
        response = client.post("/api/v1/llm/chat", json=payload)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["message"]["role"] == "assistant"
        assert data["message"]["content"] == "I am doing well, thank you!"
        assert data["model"] == "llama3.2"
        assert data["done"] is True

def test_llm_generate_streaming(client):
    """Test streaming /llm/generate route using server-sent events."""
    async def mock_generator(*args, **kwargs):
        chunks = [
            {"response": "Hello", "model": "llama3.2", "done": False},
            {"response": " world", "model": "llama3.2", "done": False},
            {"response": "!", "model": "llama3.2", "done": True}
        ]
        for chunk in chunks:
            yield chunk

    with patch.object(OllamaProvider, "check_availability", new_callable=AsyncMock) as mock_avail, \
         patch.object(OllamaProvider, "generate", new_callable=AsyncMock) as mock_gen:
        
        mock_avail.return_value = True
        mock_gen.return_value = mock_generator()
        
        payload = {
            "prompt": "Say hello world",
            "model": "llama3.2",
            "stream": True
        }
        
        response = client.post("/api/v1/llm/generate", json=payload)
        assert response.status_code == status.HTTP_200_OK
        assert "text/event-stream" in response.headers["content-type"]
        
        # Read the lines
        lines = [line if isinstance(line, str) else line.decode("utf-8") for line in response.iter_lines() if line]
        assert len(lines) == 3
        
        # Verify first chunk
        chunk_data1 = json.loads(lines[0].replace("data: ", ""))
        assert chunk_data1["text"] == "Hello"
        assert chunk_data1["done"] is False
        
        # Verify last chunk
        chunk_data3 = json.loads(lines[2].replace("data: ", ""))
        assert chunk_data3["text"] == "!"
        assert chunk_data3["done"] is True

def test_llm_chat_streaming(client):
    """Test streaming /llm/chat route using server-sent events."""
    async def mock_generator(*args, **kwargs):
        chunks = [
            {"message": {"role": "assistant", "content": "I"}, "model": "llama3.2", "done": False},
            {"message": {"role": "assistant", "content": " agree"}, "model": "llama3.2", "done": False},
            {"message": {"role": "assistant", "content": "."}, "model": "llama3.2", "done": True}
        ]
        for chunk in chunks:
            yield chunk

    with patch.object(OllamaProvider, "check_availability", new_callable=AsyncMock) as mock_avail, \
         patch.object(OllamaProvider, "chat", new_callable=AsyncMock) as mock_chat:
        
        mock_avail.return_value = True
        mock_chat.return_value = mock_generator()
        
        payload = {
            "messages": [{"role": "user", "content": "Agree with me"}],
            "model": "llama3.2",
            "stream": True
        }
        
        response = client.post("/api/v1/llm/chat", json=payload)
        assert response.status_code == status.HTTP_200_OK
        assert "text/event-stream" in response.headers["content-type"]
        
        lines = [line if isinstance(line, str) else line.decode("utf-8") for line in response.iter_lines() if line]
        assert len(lines) == 3
        
        chunk_data = json.loads(lines[1].replace("data: ", ""))
        assert chunk_data["message"]["content"] == " agree"
        assert chunk_data["done"] is False

def test_llm_pull_model_streaming(client):
    """Test streaming model pulling endpoint progress reporting."""
    async def mock_pull_generator(*args, **kwargs):
        chunks = [
            {"status": "pulling manifest", "completed": 0, "total": 100},
            {"status": "downloading", "completed": 50, "total": 100},
            {"status": "success", "completed": 100, "total": 100}
        ]
        for chunk in chunks:
            yield chunk

    with patch.object(OllamaProvider, "check_availability", new_callable=AsyncMock) as mock_avail, \
         patch.object(OllamaProvider, "pull_model", new_callable=AsyncMock) as mock_pull:
         
        mock_avail.return_value = True
        mock_pull.return_value = mock_pull_generator()
        
        payload = {"name": "llama3.2"}
        response = client.post("/api/v1/llm/models/pull", json=payload)
        
        assert response.status_code == status.HTTP_200_OK
        assert "text/event-stream" in response.headers["content-type"]
        
        lines = [line if isinstance(line, str) else line.decode("utf-8") for line in response.iter_lines() if line]
        assert len(lines) == 3
        
        chunk_data = json.loads(lines[1].replace("data: ", ""))
        assert chunk_data["status"] == "downloading"
        assert chunk_data["completed"] == 50
