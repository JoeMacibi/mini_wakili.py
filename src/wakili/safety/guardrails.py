"""Small, testable checks for source-grounded output."""


def has_citation(answer: str) -> bool:
    return "Sources:" in answer and len(answer.split("Sources:", 1)[1].strip()) > 0


def validate_grounding(answer: str, citations: list[str]) -> bool:
    return bool(citations) and has_citation(answer) and all(citation in answer for citation in citations)
