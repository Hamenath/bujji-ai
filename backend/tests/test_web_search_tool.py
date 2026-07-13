import pytest
from unittest.mock import AsyncMock, patch
from app.tools.web.web_search import WebSearchTool
from app.search.schemas import SearchResultItem
from app.search.exceptions import SearchProviderUnavailableError, SearchFailedError, SearchTimeoutError

@pytest.mark.asyncio
async def test_web_search_tool_success():
    tool = WebSearchTool()
    
    mock_results = [
        SearchResultItem(title="Python Info", url="https://python.org", snippet="Great programming lang", domain="python.org", rank=1),
        SearchResultItem(title="Python Guide", url="https://realpython.com", snippet="Tutorials for python", domain="realpython.com", rank=2),
    ]
    
    with patch("app.search.provider.DuckDuckGoSearchProvider.search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_results
        
        result = await tool.execute(query="python", max_results=2)
        assert result.success is True
        assert result.data["query"] == "python"
        assert len(result.data["results"]) == 2
        assert result.data["results"][0]["title"] == "Python Info"
        assert result.data["results"][0]["url"] == "https://python.org"
        assert result.metadata["result_count"] == 2

@pytest.mark.asyncio
async def test_web_search_tool_empty():
    tool = WebSearchTool()
    
    with patch("app.search.provider.DuckDuckGoSearchProvider.search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = []
        
        result = await tool.execute(query="some obscure query", max_results=5)
        assert result.success is True
        assert len(result.data["results"]) == 0
        assert result.metadata["result_count"] == 0

@pytest.mark.asyncio
async def test_web_search_tool_provider_unavailable():
    tool = WebSearchTool()
    
    with patch("app.search.provider.DuckDuckGoSearchProvider.search", new_callable=AsyncMock) as mock_search:
        mock_search.side_effect = SearchProviderUnavailableError("DDG ratelimit")
        
        result = await tool.execute(query="python")
        assert result.success is False
        assert result.error == "SEARCH_PROVIDER_UNAVAILABLE"
        assert "ratelimit" in result.metadata["error_detail"]

@pytest.mark.asyncio
async def test_web_search_tool_timeout():
    tool = WebSearchTool()
    
    with patch("app.search.provider.DuckDuckGoSearchProvider.search", new_callable=AsyncMock) as mock_search:
        mock_search.side_effect = SearchTimeoutError("Timed out")
        
        result = await tool.execute(query="python")
        assert result.success is False
        assert result.error == "SEARCH_TIMEOUT"
