import pytest
from app.web.content_extractor import ContentExtractor
from app.web.exceptions import ContentExtractionError

def test_content_extractor_html():
    extractor = ContentExtractor()
    html = """
    <html>
        <head><title>My Awesome Article</title></head>
        <body>
            <header>My Website Header</header>
            <nav><a href="/">Home</a></nav>
            <article>
                <h1>Article Title</h1>
                <p>This is the main body text of the article.</p>
                <script>console.log('Ignore me');</script>
                <style>body { color: red; }</style>
                <form><input type="submit"/></form>
            </article>
            <footer>Website Footer</footer>
        </body>
    </html>
    """
    
    result = extractor.extract(html, "text/html", "https://example.com/article")
    assert result["title"] == "My Awesome Article"
    assert result["domain"] == "example.com"
    assert "Article Title" in result["content"]
    assert "This is the main body text" in result["content"]
    # Verify decomposed tags are not in output
    assert "Ignore me" not in result["content"]
    assert "Website Footer" not in result["content"]
    assert "Home" not in result["content"]
    assert result["truncated"] is False

def test_content_extractor_plain_text():
    extractor = ContentExtractor()
    text = "Hello World!\n\nThis is plain text with unicode characters like \u2605.\n\n"
    
    result = extractor.extract(text, "text/plain", "https://example.org/doc.txt")
    assert result["title"] == "Plain Text Content"
    assert "\u2605" in result["content"]
    assert "Hello World!" in result["content"]
    assert result["truncated"] is False

def test_content_extractor_truncation():
    extractor = ContentExtractor()
    text = "a" * 30000
    result = extractor.extract(text, "text/plain", "https://example.org")
    assert len(result["content"]) == 20000
    assert result["truncated"] is True

def test_content_extractor_empty_html():
    extractor = ContentExtractor()
    html = "<html><body><script>alert(1)</script></body></html>"
    with pytest.raises(ContentExtractionError) as exc:
        extractor.extract(html, "text/html", "https://example.com")
    assert exc.value.code == "EMPTY_CONTENT"
