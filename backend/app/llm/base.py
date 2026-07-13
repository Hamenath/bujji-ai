from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Any, List
from app.llm.schemas import GenerateRequest, ChatRequest

class BaseLLMProvider(ABC):
    """Abstract Base Class defining the contract for LLM inference providers."""

    @abstractmethod
    async def check_availability(self) -> bool:
        """Checks if the provider service is active and responsive."""
        pass

    @abstractmethod
    async def get_local_models(self) -> List[Dict[str, Any]]:
        """Retrieves list of available models installed locally on the provider."""
        pass

    @abstractmethod
    async def generate(self, payload: GenerateRequest) -> Any:
        """
        Sends a single prompt completion request to the provider.
        Should return a dictionary response if stream=False, 
        or an AsyncIterator[Dict[str, Any]] if stream=True.
        """
        pass

    @abstractmethod
    async def chat(self, payload: ChatRequest) -> Any:
        """
        Sends a conversational chat completion request with message history.
        Should return a dictionary response if stream=False, 
        or an AsyncIterator[Dict[str, Any]] if stream=True.
        """
        pass

    @abstractmethod
    async def pull_model(self, model_name: str) -> AsyncIterator[Dict[str, Any]]:
        """
        Instructs the provider to download a model.
        Should return an AsyncIterator yielding status/progress updates.
        """
        pass
