from typing import Dict, Optional
from app.llm.base import BaseLLMProvider
from app.llm.ollama_provider import OllamaProvider

class ModelRouter:
    """Manages available LLM providers and routes requests to the active provider."""

    def __init__(self):
        self._providers: Dict[str, BaseLLMProvider] = {}
        # Set Ollama as default active provider
        self._active_provider_name: str = "ollama"
        self.register_provider("ollama", OllamaProvider())

    def register_provider(self, name: str, provider: BaseLLMProvider) -> None:
        """Registers a new LLM provider instance."""
        self._providers[name.lower()] = provider

    def get_provider(self, name: Optional[str] = None) -> BaseLLMProvider:
        """Retrieves a provider by name, falling back to the configured active provider."""
        provider_name = (name or self._active_provider_name).lower()
        if provider_name not in self._providers:
            raise ValueError(f"LLM Provider '{provider_name}' is not registered.")
        return self._providers[provider_name]

    def set_active_provider(self, name: str) -> None:
        """Sets the system-wide active provider."""
        provider_name = name.lower()
        if provider_name not in self._providers:
            raise ValueError(f"Cannot set active provider to unregistered '{provider_name}'.")
        self._active_provider_name = provider_name

    @property
    def active_provider(self) -> BaseLLMProvider:
        """Shortcut property to retrieve the currently active LLM provider."""
        return self.get_provider()

# Singleton instance for system usage
model_router = ModelRouter()
