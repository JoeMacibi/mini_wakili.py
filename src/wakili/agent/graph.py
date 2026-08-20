"""Minimal request orchestration for the research agent."""

from dataclasses import dataclass

from .tools import CorpusTool


@dataclass
class ResearchAgent:
    corpus: CorpusTool

    def run(self, question: str) -> str:
        documents = self.corpus.search(question)
        if not documents:
            return "No indexed source documents were found. Add material under data/raw before researching."
        citations = ", ".join(document.citation for document in documents)
        return f"Retrieved {len(documents)} source section(s) for: {question}\nSources: {citations}"
