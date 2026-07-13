from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional
from app.tools.base import BaseTool, ToolResult

class DateTimeInput(BaseModel):
    format: Optional[str] = Field(
        default="datetime", 
        description="The desired format type. Supported values: 'datetime', 'date', 'time'."
    )

class DateTimeTool(BaseTool):
    name = "datetime"
    description = "Get the current local date and time information."
    input_schema = DateTimeInput
    permission_level = "safe"
    timeout_seconds = 5

    async def execute(self, format: str = "datetime", **kwargs) -> ToolResult:
        now = datetime.now()
        fmt_lower = format.lower()
        
        if fmt_lower == "date":
            res = now.strftime("%Y-%m-%d")
        elif fmt_lower == "time":
            res = now.strftime("%H:%M:%S")
        else:
            res = now.strftime("%Y-%m-%d %H:%M:%S")
            
        return ToolResult(
            success=True,
            data={"result": res},
            error=None
        )
