"""Research tool interfaces used by the agent."""

from pathlib import Path

from wakili.rag.retriever import Document, InMemoryRetriever


class CorpusTool:
    def __init__(self, corpus_path: Path):
        self.corpus_path = corpus_path
        self.retriever = InMemoryRetriever(self._load_documents())

    def _load_documents(self) -> list[Document]:
        if not self.corpus_path.exists():
            return []
        return [
            Document(id=path.stem, text=path.read_text(encoding="utf-8"), citation=path.name)
            for path in sorted(self.corpus_path.glob("*.txt"))
        ]

    def search(self, query: str) -> list[Document]:
        return self.retriever.search(query)
