"""Package-level orchestration facade for the grounded research agent."""

from dataclasses import dataclass

from mini_wakili import MiniWakiliAgent

from .tools import CorpusTool


@dataclass
class ResearchAgent:
    corpus: CorpusTool

    def run(self, question: str) -> str:
        result = MiniWakiliAgent().execute_research(question)
        return result["answer"]
