import httpx
import urllib.parse
from typing import Tuple
from app.core.config import settings
from app.web.url_validator import validate_url
from app.web.exceptions import (
    FetchTimeoutError,
    TooManyRedirectsError,
    RedirectLoopError,
    UnsupportedContentTypeError,
    ResponseTooLargeError,
    WebException
)

class WebpageFetcher:
    """
    Safely and asynchronously fetches the contents of a webpage with SSRF, size,
    redirect, and content-type restrictions.
    """

    async def fetch(self, url: str) -> Tuple[str, str, int, str]:
        """
        Fetches the content of a URL.
        Returns:
            Tuple[content_text, content_type, bytes_read, final_url]
        """
        headers = {
            "User-Agent": f"BujjiAssistant/{settings.APP_VERSION} (Zero-cost web reader; safe AI assistant)"
        }
        
        timeout = httpx.Timeout(settings.WEB_FETCH_TIMEOUT_SECONDS)
        max_redirects = settings.WEB_FETCH_MAX_REDIRECTS
        max_bytes = settings.WEB_FETCH_MAX_BYTES
        
        visited_urls = {url}
        current_url = url
        redirect_count = 0
        
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            while True:
                # 1. Validate the URL before sending request
                validate_url(current_url)
                
                try:
                    # 2. Use stream to read the response header and limit bytes read
                    async with client.stream("GET", current_url, headers=headers) as response:
                        # 3. Check for redirects
                        if response.status_code in (301, 302, 303, 307, 308):
                            redirect_count += 1
                            if redirect_count > max_redirects:
                                raise TooManyRedirectsError(
                                    f"Too many redirects (limit: {max_redirects})",
                                    code="TOO_MANY_REDIRECTS"
                                )
                                
                            location = response.headers.get("Location")
                            if not location:
                                raise WebException("Redirect response missing Location header", code="INVALID_REDIRECT")
                                
                            # Resolve relative redirects
                            new_url = urllib.parse.urljoin(current_url, location)
                            
                            # Check redirect loops
                            if new_url in visited_urls:
                                raise RedirectLoopError("Redirect loop detected", code="REDIRECT_LOOP")
                                
                            visited_urls.add(new_url)
                            current_url = new_url
                            continue
                            
                        # If not redirect, verify success status code
                        if response.status_code != 200:
                            raise WebException(
                                f"Failed to fetch page. HTTP Status Code: {response.status_code}",
                                code="FETCH_FAILED"
                            )
                            
                        # 4. Check content type
                        content_type = response.headers.get("Content-Type", "")
                        ct_clean = content_type.split(";")[0].strip().lower()
                        if ct_clean not in ("text/html", "text/plain"):
                            raise UnsupportedContentTypeError(
                                f"Unsupported Content-Type '{ct_clean}'. Only text/html and text/plain are supported.",
                                code="UNSUPPORTED_CONTENT_TYPE"
                            )
                            
                        # 5. Read body streamingly with size limits
                        chunks = []
                        bytes_read = 0
                        async for chunk in response.aiter_bytes():
                            bytes_read += len(chunk)
                            if bytes_read > max_bytes:
                                raise ResponseTooLargeError(
                                    f"Response size exceeded limit of {max_bytes} bytes",
                                    code="RESPONSE_TOO_LARGE"
                                )
                            chunks.append(chunk)
                            
                        # 6. Decode content safely
                        body_bytes = b"".join(chunks)
                        encoding = response.encoding or "utf-8"
                        try:
                            content_text = body_bytes.decode(encoding, errors="replace")
                        except Exception:
                            content_text = body_bytes.decode("utf-8", errors="replace")
                            
                        return content_text, ct_clean, bytes_read, current_url
                        
                except httpx.TimeoutException as e:
                    raise FetchTimeoutError(f"Request timed out: {e}", code="FETCH_TIMEOUT")
                except WebException:
                    raise
                except Exception as e:
                    raise WebException(f"Connection error: {str(e)}", code="FETCH_FAILED")
