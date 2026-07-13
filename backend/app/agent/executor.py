import logging
import time
import asyncio
from typing import Dict, Any
from app.core.config import settings
from app.agent.schemas import PlanStep
from app.tools.base import ToolResult
from app.tools.registry import tool_registry

logger = logging.getLogger("app.agent.executor")

class AgentExecutor:
    """Class handling safe, isolated execution of single planned steps."""

    async def execute_step(self, step: PlanStep) -> ToolResult:
        """Executes a single step in a plan by running the registered tool."""
        start_time = time.perf_counter()
        tool_name = step.tool_name
        
        logger.info(f"Executing step {step.id}: calling tool '{tool_name}'...")
        
        # 1. Resolve tool from registry
        tool = tool_registry.get_tool(tool_name)
        if not tool:
            duration = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"Tool '{tool_name}' not found in registry.")
            return ToolResult(
                success=False,
                error="TOOL_NOT_FOUND",
                metadata={"duration_ms": duration}
            )

        # 2. Check permission level
        if tool.permission_level == "confirm":
            duration = int((time.perf_counter() - start_time) * 1000)
            logger.warning(f"Tool '{tool_name}' requires confirmation. Blocking execution.")
            return ToolResult(
                success=False,
                error="CONFIRMATION_REQUIRED",
                metadata={"duration_ms": duration}
            )
        elif tool.permission_level == "dangerous":
            duration = int((time.perf_counter() - start_time) * 1000)
            logger.warning(f"Tool '{tool_name}' is dangerous. Blocking execution.")
            return ToolResult(
                success=False,
                error="BLOCKED_DANGEROUS",
                metadata={"duration_ms": duration}
            )

        # 3. Validate arguments using Pydantic input schema
        try:
            validated_args = tool.input_schema(**step.arguments).model_dump()
        except Exception as e:
            duration = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"Validation failed for tool '{tool_name}' arguments: {e}")
            return ToolResult(
                success=False,
                error=f"INVALID_ARGUMENTS: {str(e)}",
                metadata={"duration_ms": duration}
            )

        # 4. Execute tool with timeout
        timeout = tool.timeout_seconds or settings.AGENT_TOOL_TIMEOUT_SECONDS
        try:
            async with asyncio.timeout(timeout):
                result = await tool.execute(**validated_args)
                duration = int((time.perf_counter() - start_time) * 1000)
                if not result.metadata:
                    result.metadata = {}
                result.metadata["duration_ms"] = duration
                
                if result.success:
                    logger.info(f"Successfully executed tool '{tool_name}' in {duration}ms")
                else:
                    logger.warning(f"Tool '{tool_name}' execution reported failure: {result.error}")
                return result
                
        except TimeoutError:
            duration = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"Tool '{tool_name}' execution timed out after {timeout} seconds.")
            return ToolResult(
                success=False,
                error="TOOL_TIMEOUT",
                metadata={"duration_ms": duration}
            )
        except Exception as e:
            duration = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"Exception raised by tool '{tool_name}': {e}", exc_info=True)
            return ToolResult(
                success=False,
                error=f"TOOL_EXCEPTION: {type(e).__name__}: {str(e)}",
                metadata={"duration_ms": duration}
            )

agent_executor = AgentExecutor()
