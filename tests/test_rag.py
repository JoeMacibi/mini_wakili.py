from wakili.rag.indexer import chunk_text
from wakili.rag.retriever import Document, InMemoryRetriever


def test_chunk_text_preserves_content():
    assert chunk_text("one two three", size=2, overlap=0) == ["one two", "three"]


def test_retriever_ranks_matching_document():
    result = InMemoryRetriever([
        Document("a", "contract remedy", "a.txt"),
        Document("b", "court procedure", "b.txt"),
    ]).search("contract")
    assert result[0].id == "a"
