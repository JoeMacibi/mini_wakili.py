"""Offline keyword retriever with stable source metadata."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    id: str
    text: str
    citation: str


class InMemoryRetriever:
    def __init__(self, documents: list[Document]):
        self.documents = documents

    def search(self, query: str, limit: int = 5) -> list[Document]:
        terms = set(query.lower().split())
        ranked = sorted(
            self.documents,
            key=lambda doc: sum(term in doc.text.lower() for term in terms),
            reverse=True,
        )
        return [doc for doc in ranked if any(term in doc.text.lower() for term in terms)][:limit]
