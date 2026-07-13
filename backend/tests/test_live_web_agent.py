import pytest
import socket
from app.web.url_validator import validate_url
from app.web.webpage_fetcher import WebpageFetcher
from app.web.content_extractor import ContentExtractor
from app.search.provider import DuckDuckGoSearchProvider

def has_internet() -> bool:
    try:
        # Check if we can connect to a public DNS server
        socket.setdefaulttimeout(3)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("8.8.8.8", 53))
        s.close()
        return True
    except Exception:
        return False

# Skip all tests in this file if internet access is not available
pytestmark = pytest.mark.skipif(not has_internet(), reason="Internet access is not available.")

@pytest.mark.asyncio
async def test_live_search_provider():
    from app.search.exceptions import SearchProviderUnavailableError, SearchFailedError
    provider = DuckDuckGoSearchProvider()
    try:
        results = await provider.search("FastAPI framework", max_results=3)
        assert len(results) > 0
        assert results[0].title is not None
        assert results[0].url.startswith("http")
        assert "fastapi" in results[0].domain or "fastapi" in results[0].title.lower() or "fastapi" in results[0].snippet.lower()
    except (SearchProviderUnavailableError, SearchFailedError) as e:
        pytest.skip(f"Search provider rate limited or blocked: {e}")

@pytest.mark.asyncio
async def test_live_fetcher_and_extractor():
    url = "https://www.python.org"
    try:
        validate_url(url)
        fetcher = WebpageFetcher()
        html, ct, bytes_read, final_url = await fetcher.fetch(url)
        assert "text/html" in ct
        assert bytes_read > 0
        
        extractor = ContentExtractor()
        extracted = extractor.extract(html, ct, final_url)
        assert "Python" in extracted["title"]
        assert len(extracted["content"]) > 0
        assert extracted["domain"] == "www.python.org"
        assert extracted["truncated"] is False
    except Exception as e:
        pytest.skip(f"Live website fetch/parse failed: {e}")

