from pydantic import BaseModel, Field
from app.tools.base import BaseTool, ToolResult

class EchoInput(BaseModel):
    text: str = Field(..., description="The text string to echo back.")

class EchoTool(BaseTool):
    name = "echo"
    description = "Return the exact text provided. Primarily used for diagnostics and testing."
    input_schema = EchoInput
    permission_level = "safe"
    timeout_seconds = 5

    async def execute(self, text: str, **kwargs) -> ToolResult:
        return ToolResult(
            success=True,
            data={"result": text},
            error=None
        )
