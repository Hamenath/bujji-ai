import pytest
from pydantic import BaseModel, Field
from app.tools.base import BaseTool, ToolResult
from app.tools.registry import ToolRegistry
from app.tools.internal.calculator import CalculatorTool, safe_eval

# Dummy tools for testing registry
class DummyInput(BaseModel):
    val: str = Field(..., description="A dummy string")

class DummyTool(BaseTool):
    name = "dummy"
    description = "A dummy test tool"
    input_schema = DummyInput
    permission_level = "safe"

    async def execute(self, val: str) -> ToolResult:
        return ToolResult(success=True, data={"res": val})

class AnotherDummyTool(BaseTool):
    name = "dummy"  # Duplicate name
    description = "Another dummy tool"
    input_schema = DummyInput
    permission_level = "confirm"

    async def execute(self, val: str) -> ToolResult:
        return ToolResult(success=True)

def test_tool_registry_operations():
    registry = ToolRegistry()
    tool = DummyTool()
    
    # 1. Registration
    registry.register(tool)
    assert registry.get_tool("dummy") == tool
    assert registry.get_tool("DUMMY") == tool
    
    # 2. Duplicate registration rejected
    with pytest.raises(ValueError) as exc:
        registry.register(AnotherDummyTool())
    assert "Duplicate tool registration" in str(exc.value)

    # 3. List and metadata export
    tools = registry.list_tools()
    assert len(tools) == 1
    assert tools[0] == tool

    metadata = registry.get_tools_metadata()
    assert len(metadata) == 1
    assert metadata[0]["name"] == "dummy"
    assert metadata[0]["permission_level"] == "safe"
    assert "val" in metadata[0]["parameters"]["properties"]

    # 4. Unknown tool lookup
    assert registry.get_tool("nonexistent") is None

def test_calculator_tool_eval():
    # Test valid cases
    assert safe_eval("2 + 2") == 4
    assert safe_eval("125 * 48") == 6000
    assert safe_eval("10 / 4") == 2.5
    assert safe_eval("(3 + 5) * 2") == 16
    assert safe_eval("-5 + 10") == 5
    assert safe_eval("2.5 * 2") == 5.0

    # Division by zero
    with pytest.raises(ZeroDivisionError):
        safe_eval("10 / 0")

    # Limit power size
    with pytest.raises(ValueError) as exc:
        safe_eval("2 ** 1000")
    assert "operation parameters too large" in str(exc.value).lower()

    # Reject function calls
    with pytest.raises(ValueError):
        safe_eval("abs(-5)")

    # Reject attribute access
    with pytest.raises(ValueError):
        safe_eval("int.__name__")

    # Reject imports and code execution
    with pytest.raises(ValueError):
        safe_eval("__import__('os').system('dir')")
