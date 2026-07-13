from pydantic import BaseModel, Field
from typing import Optional

class WebpageReaderData(BaseModel):
    title: str = Field(..., description="The title of the page")
    content: str = Field(..., description="The extracted clean content")
    url: str = Field(..., description="The final URL fetched")
    domain: str = Field(..., description="The domain of the final URL")
    truncated: bool = Field(..., description="Whether the content was truncated due to length limits")

class WebpageReaderMetadata(BaseModel):
    content_type: str = Field(..., description="The content type returned by the server")
    bytes_read: int = Field(..., description="The number of raw bytes read from the response")
    duration_ms: int = Field(..., description="Duration of the fetch and parse operation in milliseconds")
