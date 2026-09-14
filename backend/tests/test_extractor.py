import pytest

from src.services.ingestion.extractor import ExtractionError, extract_page

REALISTIC_HTML = """<html><head><title>Understanding Widgets</title></head><body>
<nav>Home About Contact Blog Docs</nav>
<div id="content">
<article>
<h1>Understanding Widgets</h1>
<p>Widgets are a fundamental building block of modern user interfaces. In this guide we
will walk through everything you need to know about widgets, starting from the basics and
progressing to advanced usage patterns that experienced developers rely on daily.</p>
<h2>Getting Started</h2>
<p>To get started with widgets, you first need to install the widget library using your
favorite package manager. Once installed, you can import the widget module and begin
creating your first widget instance right away.</p>
<pre><code class="language-python">def create_widget(name):
    return Widget(name=name, active=True)
</code></pre>
<h2>Advanced Usage</h2>
<p>Once you are comfortable with the basics, you can explore advanced features such as lazy
loading, custom rendering pipelines, and widget composition, which allow you to build much
more sophisticated interfaces than a beginner would attempt.</p>
</article>
</div>
<footer>Copyright 2026 Example Corp. All rights reserved.</footer>
</body></html>"""

TINY_JS_ONLY_HTML = """<html><head><title>App</title></head>
<body><div id="root"></div><script src="/app.js"></script></body></html>"""


def test_extracts_title_and_markdown_headings():
    page = extract_page(REALISTIC_HTML, "https://example.com/widgets")
    assert page.title == "Understanding Widgets"
    assert "# Understanding Widgets" in page.markdown
    assert "## Getting Started" in page.markdown
    assert "```" in page.markdown  # code block preserved
    assert "create_widget" in page.markdown


def test_outline_extracted_in_order():
    page = extract_page(REALISTIC_HTML, "https://example.com/widgets")
    levels = [h["level"] for h in page.outline]
    assert levels == [1, 2, 2]
    assert page.outline[1]["text"] == "Getting Started"


def test_js_only_page_raises_extraction_error():
    with pytest.raises(ExtractionError):
        extract_page(TINY_JS_ONLY_HTML, "https://example.com/app")
