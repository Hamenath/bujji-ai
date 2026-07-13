import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from app.web.webpage_fetcher import WebpageFetcher
from app.web.exceptions import (
    UnsupportedContentTypeError,
    ResponseTooLargeError,
    FetchTimeoutError,
    RedirectLoopError,
    SSRFBlockedError
)

@pytest.mark.asyncio
async def test_webpage_fetcher_success():
    fetcher = WebpageFetcher()
    
    # Mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "text/html; charset=UTF-8"}
    mock_response.encoding = "utf-8"
    mock_response.aiter_bytes = MagicMock()
    
    async def mock_aiter_bytes():
        yield b"<html><title>Test Title</title><body>Hello!</body></html>"
    mock_response.aiter_bytes.return_value = mock_aiter_bytes()
    
    # Mock stream context manager
    mock_stream = MagicMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
    mock_stream.__aexit__ = AsyncMock(return_value=None)
    
    with patch("socket.getaddrinfo") as mock_dns, \
         patch("httpx.AsyncClient.stream") as mock_stream_call:
        
        mock_dns.return_value = [(None, None, None, None, ("93.184.216.34", 80))]
        mock_stream_call.return_value = mock_stream
        
        html, ct, bytes_read, final_url = await fetcher.fetch("https://example.com")
        assert "Test Title" in html
        assert ct == "text/html"
        assert bytes_read > 0
        assert final_url == "https://example.com"

@pytest.mark.asyncio
async def test_webpage_fetcher_unsupported_type():
    fetcher = WebpageFetcher()
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "application/pdf"}
    
    mock_stream = MagicMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
    mock_stream.__aexit__ = AsyncMock(return_value=None)
    
    with patch("socket.getaddrinfo") as mock_dns, \
         patch("httpx.AsyncClient.stream") as mock_stream_call:
        
        mock_dns.return_value = [(None, None, None, None, ("93.184.216.34", 80))]
        mock_stream_call.return_value = mock_stream
        
        with pytest.raises(UnsupportedContentTypeError):
            await fetcher.fetch("https://example.com/file.pdf")

@pytest.mark.asyncio
async def test_webpage_fetcher_too_large():
    fetcher = WebpageFetcher()
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "text/html"}
    mock_response.aiter_bytes = MagicMock()
    
    async def mock_aiter_bytes():
        # Yield 3MB of data (limit is 2MB)
        yield b"a" * (3 * 1024 * 1024)
    mock_response.aiter_bytes.return_value = mock_aiter_bytes()
    
    mock_stream = MagicMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
    mock_stream.__aexit__ = AsyncMock(return_value=None)
    
    with patch("socket.getaddrinfo") as mock_dns, \
         patch("httpx.AsyncClient.stream") as mock_stream_call:
        
        mock_dns.return_value = [(None, None, None, None, ("93.184.216.34", 80))]
        mock_stream_call.return_value = mock_stream
        
        with pytest.raises(ResponseTooLargeError):
            await fetcher.fetch("https://example.com")

@pytest.mark.asyncio
async def test_webpage_fetcher_timeout():
    fetcher = WebpageFetcher()
    
    with patch("socket.getaddrinfo") as mock_dns, \
         patch("httpx.AsyncClient.stream", side_effect=httpx.TimeoutException("Timeout")):
        
        mock_dns.return_value = [(None, None, None, None, ("93.184.216.34", 80))]
        
        with pytest.raises(FetchTimeoutError):
            await fetcher.fetch("https://example.com")

@pytest.mark.asyncio
async def test_webpage_fetcher_safe_redirects():
    fetcher = WebpageFetcher()
    
    # First response is a redirect
    mock_response_1 = MagicMock()
    mock_response_1.status_code = 302
    mock_response_1.headers = {"Location": "https://example.com/safe"}
    
    mock_stream_1 = MagicMock()
    mock_stream_1.__aenter__ = AsyncMock(return_value=mock_response_1)
    mock_stream_1.__aexit__ = AsyncMock(return_value=None)
    
    # Second response is success
    mock_response_2 = MagicMock()
    mock_response_2.status_code = 200
    mock_response_2.headers = {"Content-Type": "text/plain"}
    mock_response_2.encoding = "utf-8"
    mock_response_2.aiter_bytes = MagicMock()
    async def mock_aiter_bytes():
        yield b"Clean Content"
    mock_response_2.aiter_bytes.return_value = mock_aiter_bytes()
    
    mock_stream_2 = MagicMock()
    mock_stream_2.__aenter__ = AsyncMock(return_value=mock_response_2)
    mock_stream_2.__aexit__ = AsyncMock(return_value=None)
    
    with patch("socket.getaddrinfo") as mock_dns, \
         patch("httpx.AsyncClient.stream") as mock_stream_call:
        
        mock_dns.return_value = [(None, None, None, None, ("93.184.216.34", 80))]
        mock_stream_call.side_effect = [mock_stream_1, mock_stream_2]
        
        html, ct, bytes_read, final_url = await fetcher.fetch("https://example.com/start")
        assert html == "Clean Content"
        assert ct == "text/plain"
        assert final_url == "https://example.com/safe"

@pytest.mark.asyncio
async def test_webpage_fetcher_unsafe_redirect_blocked():
    fetcher = WebpageFetcher()
    
    # Redirect points to localhost
    mock_response = MagicMock()
    mock_response.status_code = 302
    mock_response.headers = {"Location": "http://127.0.0.1:8000/docs"}
    
    mock_stream = MagicMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
    mock_stream.__aexit__ = AsyncMock(return_value=None)
    
    with patch("socket.getaddrinfo") as mock_dns, \
         patch("httpx.AsyncClient.stream") as mock_stream_call:
        
        # DNS resolves public first URL safely
        mock_dns.side_effect = [
            [(None, None, None, None, ("93.184.216.34", 80))], # for start URL
            [(None, None, None, None, ("127.0.0.1", 80))]      # for localhost redirect
        ]
        mock_stream_call.return_value = mock_stream
        
        with pytest.raises(SSRFBlockedError):
            await fetcher.fetch("https://example.com/start")

@pytest.mark.asyncio
async def test_webpage_fetcher_metadata_redirect_blocked():
    fetcher = WebpageFetcher()
    
    # Redirect points to metadata service
    mock_response = MagicMock()
    mock_response.status_code = 302
    mock_response.headers = {"Location": "http://169.254.169.254/latest/meta-data/"}
    
    mock_stream = MagicMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
    mock_stream.__aexit__ = AsyncMock(return_value=None)
    
    with patch("socket.getaddrinfo") as mock_dns, \
         patch("httpx.AsyncClient.stream") as mock_stream_call:
        
        # DNS resolves public first URL safely
        mock_dns.side_effect = [
            [(None, None, None, None, ("93.184.216.34", 80))], # for start URL
            [(None, None, None, None, ("169.254.169.254", 80))] # for metadata redirect
        ]
        mock_stream_call.return_value = mock_stream
        
        with pytest.raises(SSRFBlockedError):
            await fetcher.fetch("https://example.com/start")

@pytest.mark.asyncio
async def test_webpage_fetcher_redirect_loop():
    fetcher = WebpageFetcher()
    
    # Redirect loop: start -> loop -> start
    mock_response_1 = MagicMock()
    mock_response_1.status_code = 302
    mock_response_1.headers = {"Location": "https://example.com/loop"}
    
    mock_response_2 = MagicMock()
    mock_response_2.status_code = 302
    mock_response_2.headers = {"Location": "https://example.com/start"}
    
    mock_stream_1 = MagicMock()
    mock_stream_1.__aenter__ = AsyncMock(return_value=mock_response_1)
    mock_stream_1.__aexit__ = AsyncMock(return_value=None)
    
    mock_stream_2 = MagicMock()
    mock_stream_2.__aenter__ = AsyncMock(return_value=mock_response_2)
    mock_stream_2.__aexit__ = AsyncMock(return_value=None)
    
    with patch("socket.getaddrinfo") as mock_dns, \
         patch("httpx.AsyncClient.stream") as mock_stream_call:
        
        mock_dns.return_value = [(None, None, None, None, ("93.184.216.34", 80))]
        mock_stream_call.side_effect = [mock_stream_1, mock_stream_2]
        
        with pytest.raises(RedirectLoopError):
            await fetcher.fetch("https://example.com/start")
