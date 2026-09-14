from langchain_core.documents import Document

from src.services.ingestion.splitter import split_document

MARKDOWN = """# Understanding Widgets

Widgets are a fundamental building block of modern user interfaces.

## Getting Started

To get started with widgets, install the widget library.

```
def create_widget(name):
    return Widget(name=name, active=True)
```

## Advanced Usage

Explore advanced features such as lazy loading and composition.
"""


def test_splits_by_heading_and_tracks_heading_path():
    doc = Document(page_content=MARKDOWN, metadata={"url": "https://example.com/widgets", "title": "Widgets"})
    chunks = split_document(doc)

    assert len(chunks) == 3
    assert chunks[0].metadata["heading_path"] == "Understanding Widgets"
    assert chunks[1].metadata["heading_path"] == "Understanding Widgets > Getting Started"
    assert chunks[2].metadata["heading_path"] == "Understanding Widgets > Advanced Usage"


def test_chunk_index_is_sequential():
    doc = Document(page_content=MARKDOWN, metadata={"url": "u", "title": "t"})
    chunks = split_document(doc)
    assert [c.metadata["chunk_index"] for c in chunks] == list(range(len(chunks)))


def test_code_block_kept_intact():
    doc = Document(page_content=MARKDOWN, metadata={"url": "u", "title": "t"})
    chunks = split_document(doc)
    getting_started = next(c for c in chunks if "Getting Started" in c.metadata["heading_path"])
    assert "def create_widget" in getting_started.page_content
    assert "return Widget" in getting_started.page_content


def test_original_metadata_preserved():
    doc = Document(page_content=MARKDOWN, metadata={"url": "https://example.com/widgets", "title": "Widgets"})
    chunks = split_document(doc)
    for c in chunks:
        assert c.metadata["url"] == "https://example.com/widgets"
        assert c.metadata["title"] == "Widgets"
