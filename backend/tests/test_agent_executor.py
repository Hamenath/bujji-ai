import pytest
import asyncio
from unittest.mock import patch
from pydantic import BaseModel, Field
from app.agent.schemas import PlanStep
from app.agent.executor import AgentExecutor
from app.tools.base import BaseTool, ToolResult
from app.tools.registry import tool_registry

# Define test tools with varying configurations
class MockInput(BaseModel):
    value: int = Field(..., description="An integer value")

class QuickTool(BaseTool):
    name = "quick"
    description = "Quick tool"
    input_schema = MockInput
    permission_level = "safe"
    timeout_seconds = 1

    async def execute(self, value: int) -> ToolResult:
        return ToolResult(success=True, data={"result": value * 2})

class SlowTool(BaseTool):
    name = "slow"
    description = "Slow tool"
    input_schema = MockInput
    permission_level = "safe"
    timeout_seconds = 1

    async def execute(self, value: int) -> ToolResult:
        await asyncio.sleep(2)  # Exceeds timeout
        return ToolResult(success=True, data={"result": value})

class ConfirmTool(BaseTool):
    name = "confirm_tool"
    description = "Requires confirmation"
    input_schema = MockInput
    permission_level = "confirm"

    async def execute(self, value: int) -> ToolResult:
        return ToolResult(success=True)

class DangerousTool(BaseTool):
    name = "dangerous_tool"
    description = "Dangerous tool"
    input_schema = MockInput
    permission_level = "dangerous"

    async def execute(self, value: int) -> ToolResult:
        return ToolResult(success=True)

class ExceptionTool(BaseTool):
    name = "exception_tool"
    description = "Raises exception"
    input_schema = MockInput
    permission_level = "safe"

    async def execute(self, value: int) -> ToolResult:
        raise RuntimeError("Something went wrong inside the tool.")

@pytest.fixture(autouse=True)
def register_mock_tools():
    tool_registry.clear()
    tool_registry.register(QuickTool())
    tool_registry.register(SlowTool())
    tool_registry.register(ConfirmTool())
    tool_registry.register(DangerousTool())
    tool_registry.register(ExceptionTool())
    yield
    tool_registry.clear()

@pytest.mark.asyncio
async def test_agent_executor_success():
    executor = AgentExecutor()
    step = PlanStep(id=1, description="Run quick", tool_name="quick", arguments={"value": 10})
    result = await executor.execute_step(step)
    assert result.success is True
    assert result.data == {"result": 20}
    assert result.metadata is not None
    assert result.metadata["duration_ms"] >= 0

@pytest.mark.asyncio
async def test_agent_executor_unknown_tool():
    executor = AgentExecutor()
    step = PlanStep(id=1, description="Run unknown", tool_name="nonexistent", arguments={})
    result = await executor.execute_step(step)
    assert result.success is False
    assert result.error == "TOOL_NOT_FOUND"

@pytest.mark.asyncio
async def test_agent_executor_invalid_arguments():
    executor = AgentExecutor()
    step = PlanStep(id=1, description="Run quick", tool_name="quick", arguments={"invalid_arg": 10})
    result = await executor.execute_step(step)
    assert result.success is False
    assert result.error is not None
    assert "INVALID_ARGUMENTS" in result.error

@pytest.mark.asyncio
async def test_agent_executor_timeout():
    executor = AgentExecutor()
    step = PlanStep(id=1, description="Run slow", tool_name="slow", arguments={"value": 5})
    result = await executor.execute_step(step)
    assert result.success is False
    assert result.error == "TOOL_TIMEOUT"

@pytest.mark.asyncio
async def test_agent_executor_exception():
    executor = AgentExecutor()
    step = PlanStep(id=1, description="Run exception", tool_name="exception_tool", arguments={"value": 5})
    result = await executor.execute_step(step)
    assert result.success is False
    assert result.error is not None
    assert "TOOL_EXCEPTION" in result.error
    assert "RuntimeError" in result.error

@pytest.mark.asyncio
async def test_agent_executor_confirm_permission():
    executor = AgentExecutor()
    step = PlanStep(id=1, description="Run confirm", tool_name="confirm_tool", arguments={"value": 5})
    result = await executor.execute_step(step)
    assert result.success is False
    assert result.error == "CONFIRMATION_REQUIRED"

@pytest.mark.asyncio
async def test_agent_executor_dangerous_permission():
    executor = AgentExecutor()
    step = PlanStep(id=1, description="Run dangerous", tool_name="dangerous_tool", arguments={"value": 5})
    result = await executor.execute_step(step)
    assert result.success is False
    assert result.error == "BLOCKED_DANGEROUS"
