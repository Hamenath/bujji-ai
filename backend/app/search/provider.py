import asyncio
import logging
from urllib.parse import urlparse
from typing import List
from duckduckgo_search import DDGS
from app.search.base import BaseSearchProvider
from app.search.schemas import SearchResultItem
from app.search.exceptions import SearchProviderUnavailableError, SearchFailedError, SearchTimeoutError

logger = logging.getLogger("app.search.provider")

class DuckDuckGoSearchProvider(BaseSearchProvider):
    """
    Zero-cost Search Provider implementation using the duckduckgo_search library.
    No API keys required.
    """

    async def search(self, query: str, max_results: int) -> List[SearchResultItem]:
        if not query.strip():
            raise SearchFailedError("Search query cannot be empty.", code="SEARCH_FAILED")
            
        try:
            # Run the synchronous duckduckgo_search block in a separate thread to prevent blocking the event loop
            results = await asyncio.to_thread(self._run_ddgs_text, query, max_results)
            
            normalized_results: List[SearchResultItem] = []
            seen_urls = set()
            rank = 1
            
            for item in results:
                title = item.get("title")
                url = item.get("href") or item.get("url")
                snippet = item.get("body") or item.get("snippet") or ""
                
                if not title or not url:
                    continue
                    
                try:
                    parsed_url = urlparse(url)
                    domain = parsed_url.netloc.lower()
                    if not domain:
                        continue
                except Exception:
                    continue
                    
                # Deduplicate by normalized URL (exclude fragment, lowercase)
                norm_url = url.split("#")[0].strip().lower()
                if norm_url in seen_urls:
                    continue
                seen_urls.add(norm_url)
                
                try:
                    res_item = SearchResultItem(
                        title=title.strip(),
                        url=url.strip(),
                        snippet=snippet.strip(),
                        domain=domain,
                        rank=rank
                    )
                    normalized_results.append(res_item)
                    rank += 1
                except Exception as e:
                    logger.warning(f"Failed to parse search result item: {e}. Item: {item}")
                    continue
                    
                if len(normalized_results) >= max_results:
                    break
                    
            return normalized_results
            
        except asyncio.TimeoutError:
            raise SearchTimeoutError("DuckDuckGo search request timed out.")
        except Exception as e:
            err_msg = str(e).lower()
            if "ratelimit" in err_msg or "403" in err_msg or "forbidden" in err_msg:
                raise SearchProviderUnavailableError(
                    f"DuckDuckGo search rate limit or blocking occurred: {e}"
                )
            raise SearchFailedError(f"DuckDuckGo search failed: {e}")

    def _run_ddgs_text(self, query: str, max_results: int) -> list:
        with DDGS() as ddgs:
            fetch_limit = min(max(max_results * 2, 10), 50)
            results = ddgs.text(query, max_results=fetch_limit)
            return list(results) if results else []
