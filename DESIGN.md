# Wakili Design Notes

## Architecture

The application uses a small `src` package with three explicit boundaries:

1. **Agent** coordinates a request and composes research tools.
2. **RAG** owns document normalization, chunking, and retrieval.
3. **Safety** validates grounding and citation metadata before an answer can be presented.

The initial implementation is dependency-light and deterministic. A production adapter can replace the in-memory retriever with a vector index and replace the tool stubs with jurisdiction-specific search providers without changing the package boundaries.

## RAG tradeoffs

Parent-child retrieval is represented by stable document and section identifiers. This keeps citations tied to source sections while allowing smaller chunks to be ranked later. The scaffold uses token overlap rather than embeddings so tests remain fast, offline, and reproducible.

## Safety guardrails

Research output should be treated as untrusted until every substantive claim is linked to a source citation. The safety module therefore exposes small, composable checks for citation presence and source grounding. It does not claim to determine legal correctness, and it should be paired with jurisdiction, date, and human-review checks before deployment.
