import urllib.parse
from bs4 import BeautifulSoup
from app.core.config import settings
from app.web.exceptions import ContentExtractionError

class ContentExtractor:
    """
    Parses and cleans HTML/plain text webpage content, removing layout clutter
    and enforcing character limit bounds.
    """

    def extract(self, raw_content: str, content_type: str, url: str) -> dict:
        """
        Parses raw text/HTML content and extracts clean page details.
        Returns:
            dict containing title, content, domain, url, and truncated.
        """
        try:
            parsed_url = urllib.parse.urlparse(url)
            domain = parsed_url.netloc
        except Exception:
            domain = ""

        if content_type == "text/plain":
            # For plain text, clean whitespace and return
            cleaned_text = self._clean_whitespace(raw_content)
            title = "Plain Text Content"
        else:
            # For HTML, parse and decompose boilerplate elements
            try:
                soup = BeautifulSoup(raw_content, "html.parser")
                
                # Extract title
                title_tag = soup.title
                title = title_tag.string.strip() if title_tag and title_tag.string else "Untitled Page"

                # Extract description if available
                # (Optional meta description)
                
                # Decompose script, style, navigation, footer, header, form, etc.
                for tag in soup(["script", "style", "nav", "footer", "header", "form", "iframe", "noscript"]):
                    tag.decompose()
                    
                # Get clean text
                raw_text = soup.get_text(separator="\n")
                cleaned_text = self._clean_whitespace(raw_text)
                
            except Exception as e:
                raise ContentExtractionError(f"HTML parsing failed: {e}", code="CONTENT_EXTRACTION_FAILED")

        # Handle empty content
        if not cleaned_text.strip():
            raise ContentExtractionError("Extracted webpage text content is empty.", code="EMPTY_CONTENT")

        # Enforce character limit
        max_chars = settings.WEB_READER_MAX_CHARS
        truncated = False
        if len(cleaned_text) > max_chars:
            cleaned_text = cleaned_text[:max_chars]
            truncated = True

        return {
            "title": title,
            "content": cleaned_text,
            "url": url,
            "domain": domain,
            "truncated": truncated
        }

    def _clean_whitespace(self, text: str) -> str:
        """Helper to clean up trailing/leading and excessive whitespace."""
        lines = [line.strip() for line in text.splitlines()]
        # Remove empty lines
        cleaned_lines = [line for line in lines if line]
        return "\n".join(cleaned_lines)
