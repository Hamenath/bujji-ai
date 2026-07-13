import time
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from app.tools.base import BaseTool, ToolResult
from app.search.provider import DuckDuckGoSearchProvider
from app.search.exceptions import SearchException

class WebSearchInput(BaseModel):
    query: str = Field(..., min_length=1, description="The search query query string.")
    max_results: int = Field(default=5, ge=1, le=10, description="Maximum number of search results to return (1-10).")

class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = (
        "Search the web for current or external information. "
        "Returns a list of matching results with titles, domains, URLs, and snippets."
    )
    input_schema: Any = WebSearchInput
    permission_level: str = "safe"
    timeout_seconds: int = 30

    def __init__(self):
        super().__init__()
        self._provider = DuckDuckGoSearchProvider()

    async def execute(self, query: str, max_results: int = 5) -> ToolResult:
        start_time = time.perf_counter()
        
        # Enforce limits
        if not query.strip():
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return ToolResult(
                success=False,
                error="SEARCH_FAILED",
                metadata={"duration_ms": duration_ms, "error_detail": "Query cannot be empty."}
            )

        if max_results < 1 or max_results > 10:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return ToolResult(
                success=False,
                error="SEARCH_FAILED",
                metadata={"duration_ms": duration_ms, "error_detail": "max_results must be between 1 and 10."}
            )

        try:
            results = await self._provider.search(query, max_results)
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            
            # Map Pydantic models to dict
            results_dict = [r.model_dump() for r in results]
            
            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "results": results_dict
                },
                metadata={
                    "provider": "duckduckgo",
                    "result_count": len(results_dict),
                    "duration_ms": duration_ms
                }
            )
            
        except SearchException as se:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return ToolResult(
                success=False,
                error=se.code,
                metadata={"duration_ms": duration_ms, "error_detail": str(se)}
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return ToolResult(
                success=False,
                error="SEARCH_FAILED",
                metadata={"duration_ms": duration_ms, "error_detail": str(e)}
            )
