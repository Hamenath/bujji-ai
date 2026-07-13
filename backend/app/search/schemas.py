from pydantic import BaseModel, Field

class SearchResultItem(BaseModel):
    title: str = Field(..., description="The title of the search result")
    url: str = Field(..., description="The URL of the search result page")
    snippet: str = Field(..., description="A short description snippet from the page")
    domain: str = Field(..., description="The domain of the search result")
    rank: int = Field(..., description="Chronological search ranking (starts at 1)")
