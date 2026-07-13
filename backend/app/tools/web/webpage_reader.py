import time
from typing import Any, Optional
from pydantic import BaseModel, Field
from app.tools.base import BaseTool, ToolResult
from app.web.webpage_fetcher import WebpageFetcher
from app.web.content_extractor import ContentExtractor
from app.web.exceptions import WebException
from app.core.config import settings

class WebpageReaderInput(BaseModel):
    url: str = Field(..., description="The HTTP/HTTPS URL of the webpage to read.")
    max_chars: Optional[int] = Field(default=None, ge=1, description="Optional character limit of text to extract.")

class WebpageReaderTool(BaseTool):
    name: str = "webpage_reader"
    description: str = (
        "Extract clean, readable text content from a public HTTP/HTTPS URL. "
        "Performs safety and SSRF validation, strips HTML clutter, and enforces length bounds."
    )
    input_schema: Any = WebpageReaderInput
    permission_level: str = "safe"
    timeout_seconds: int = 30

    def __init__(self):
        super().__init__()
        self._fetcher = WebpageFetcher()
        self._extractor = ContentExtractor()

    async def execute(self, url: str, max_chars: Optional[int] = None) -> ToolResult:
        start_time = time.perf_counter()
        
        try:
            # 1. Fetch contents safely
            raw_content, content_type, bytes_read, final_url = await self._fetcher.fetch(url)
            
            # 2. Extract contents
            # Clamp character limit if needed
            limit = max_chars if max_chars is not None else settings.WEB_READER_MAX_CHARS
            # We temporarily monkeypatch or pass the limit to the extractor
            # Since our ContentExtractor has max_chars hardcoded to settings, we can clamp it here or adjust:
            # Let's adjust ContentExtractor to accept max_chars
            extracted = self._extractor.extract(raw_content, content_type, final_url)
            
            # Apply custom max_chars if it is smaller than settings limit or custom-requested
            if max_chars is not None and len(extracted["content"]) > max_chars:
                extracted["content"] = extracted["content"][:max_chars]
                extracted["truncated"] = True
                
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            
            return ToolResult(
                success=True,
                data={
                    "title": extracted["title"],
                    "url": extracted["url"],
                    "domain": extracted["domain"],
                    "content": extracted["content"],
                    "truncated": extracted["truncated"]
                },
                metadata={
                    "content_type": content_type,
                    "bytes_read": bytes_read,
                    "duration_ms": duration_ms
                }
            )
            
        except WebException as we:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return ToolResult(
                success=False,
                error=we.code,
                metadata={"duration_ms": duration_ms, "error_detail": str(we)}
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return ToolResult(
                success=False,
                error="FETCH_FAILED",
                metadata={"duration_ms": duration_ms, "error_detail": str(e)}
            )
