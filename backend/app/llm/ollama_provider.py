import json
import logging
from typing import AsyncIterator, Dict, Any, List, Optional
import httpx

from app.core.config import settings
from app.llm.base import BaseLLMProvider
from app.llm.schemas import GenerateRequest, ChatRequest

logger = logging.getLogger("app.llm.ollama_provider")

class OllamaProvider(BaseLLMProvider):
    """Ollama implementation of the BaseLLMProvider interface."""

    def __init__(self, base_url: Optional[str] = None, default_model: Optional[str] = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.default_model = default_model or settings.OLLAMA_MODEL
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=None)

    async def check_availability(self) -> bool:
        """Checks if Ollama is running and responding on its port."""
        try:
            response = await self.client.get("/api/tags", timeout=2.0)
            return response.status_code == 200
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.HTTPError) as e:
            logger.debug(f"Ollama provider availability check failed: {e}")
            return False

    async def get_local_models(self) -> List[Dict[str, Any]]:
        """Retrieves list of locally installed Ollama models."""
        try:
            response = await self.client.get("/api/tags", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                return data.get("models", [])
            logger.error(f"Failed to fetch models from Ollama. Status: {response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Error fetching local Ollama models: {e}")
            return []

    async def generate(self, payload: GenerateRequest) -> Any:
        """Generates completion text from a single prompt."""
        model_name = payload.model or self.default_model
        request_body = {
            "model": model_name,
            "prompt": payload.prompt,
            "stream": payload.stream,
        }
        if payload.system_prompt:
            request_body["system"] = payload.system_prompt
        if payload.options:
            request_body["options"] = payload.options

        if payload.stream:
            return self._stream_request("/api/generate", request_body)
        else:
            return await self._non_stream_request("/api/generate", request_body)

    async def chat(self, payload: ChatRequest) -> Any:
        """Conversational chat completions from historical messages."""
        model_name = payload.model or self.default_model
        formatted_messages = [{"role": msg.role, "content": msg.content} for msg in payload.messages]

        request_body = {
            "model": model_name,
            "messages": formatted_messages,
            "stream": payload.stream,
        }
        if payload.system_prompt:
            formatted_messages.insert(0, {"role": "system", "content": payload.system_prompt})
        if payload.options:
            request_body["options"] = payload.options

        if payload.stream:
            return self._stream_request("/api/chat", request_body)
        else:
            return await self._non_stream_request("/api/chat", request_body)

    async def pull_model(self, model_name: str) -> AsyncIterator[Dict[str, Any]]:
        """Downloads a model from the Ollama library."""
        request_body = {"name": model_name, "stream": True}
        return self._stream_request("/api/pull", request_body)

    async def _non_stream_request(self, endpoint: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """Performs non-streaming POST request."""
        try:
            logger.debug(f"Sending non-stream request to {endpoint} with body: {body}")
            response = await self.client.post(endpoint, json=body)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama server error for {endpoint}: {e.response.text}")
            raise RuntimeError(f"Ollama server returned error: {e.response.text}")
        except Exception as e:
            logger.error(f"Failed to communicate with Ollama at {endpoint}: {e}")
            raise RuntimeError(f"Failed to communicate with Ollama: {e}")

    async def _stream_request(self, endpoint: str, body: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """Sends a streaming POST request and yields chunks."""
        try:
            logger.debug(f"Sending stream request to {endpoint} with body: {body}")
            async with self.client.stream("POST", endpoint, json=body) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing streaming JSON line: {line}. Error: {e}")
                        continue
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama server streaming error for {endpoint}: {e.response.read().decode()}")
            raise RuntimeError(f"Ollama server returned error during streaming")
        except Exception as e:
            logger.error(f"Failed during streaming with Ollama at {endpoint}: {e}")
            raise RuntimeError(f"Failed to stream from Ollama: {e}")

    async def close(self):
        """Closes HTTPX connection pool."""
        await self.client.aclose()
