import logging
from typing import Dict, List, Any, Optional
from app.tools.base import BaseTool

logger = logging.getLogger("app.tools.registry")

class ToolRegistry:
    """Central registry managing all available tools for the Agent Executor."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Registers a tool, rejecting duplicate names."""
        name = tool.name.lower()
        if name in self._tools:
            raise ValueError(f"Duplicate tool registration rejected: '{tool.name}' is already registered.")
        self._tools[name] = tool
        logger.debug(f"Registered tool: {tool.name} with permission level: {tool.permission_level}")

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Retrieves a registered tool by case-insensitive name."""
        return self._tools.get(name.lower())

    def list_tools(self) -> List[BaseTool]:
        """Lists all registered tools."""
        return list(self._tools.values())

    def get_tools_metadata(self) -> List[Dict[str, Any]]:
        """Exports LLM-friendly schemas for all registered tools."""
        metadata = []
        for tool in self.list_tools():
            schema = tool.input_schema.model_json_schema()
            metadata.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": schema.get("properties", {}),
                    "required": schema.get("required", [])
                },
                "permission_level": tool.permission_level
            })
        return metadata

    def clear(self) -> None:
        """Clears all registered tools. Primarily used for isolation in unit tests."""
        self._tools.clear()

# Global registry instance
tool_registry = ToolRegistry()
