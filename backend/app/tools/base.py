from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel

class ToolResult(BaseModel):
    """Normalized structured result returned by any tool execution."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class BaseTool(ABC):
    """Abstract base class defining the contract for all tools in the registry."""
    name: str
    description: str
    input_schema: Type[BaseModel]
    permission_level: str = "safe"  # "safe", "confirm", "dangerous"
    timeout_seconds: int = 30

    @abstractmethod
    async def execute(self, *args: Any, **kwargs: Any) -> ToolResult:
        """Asynchronously executes the tool logic with validated inputs."""
        pass
