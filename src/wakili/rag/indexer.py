"""Deterministic text chunking used before indexing."""


def chunk_text(text: str, size: int = 500, overlap: int = 50) -> list[str]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("overlap must be non-negative and smaller than size")
    words = text.split()
    step = size - overlap
    return [" ".join(words[start : start + size]) for start in range(0, len(words), step)]
