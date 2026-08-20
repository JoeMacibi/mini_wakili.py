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

## Model-only benchmark and operational controls

The interview answers A1 through D are intentionally omitted from this repository. The executable assessment is limited to model behavior and can be measured with:

```bash
PYTHONPATH=src python mini_wakili.py
PYTHONPATH=src python -m pytest -q
```

The model pipeline exposes chunk-level citations with quoted evidence, claim-to-chunk support records, source authority/status metadata, contradiction signals, low-confidence refusal, PII input/output controls, contract-review risk flags, and deterministic benchmark metrics. The aggregate metric is a model-quality signal, not a substitute for human legal judgment.

HITL is enforced in code through `INTAKE_REVIEW`, `EVIDENCE_REVIEW`, `APPROVED_FOR_RELIANCE`, `ACTION_APPROVAL`, and `CLOSED` states. Every transition requires a reviewer identity and creates an append-only audit event. A draft is never considered approved merely because retrieval confidence is high.

For production deployment, PDF parsing and OCR must run in an isolated, malware-scanned adapter; model hosting must satisfy Kenyan data-residency and transfer requirements; retries must be bounded and idempotent; matter memory must be tenant- and matter-scoped; and audit records must follow the applicable five-year retention policy. Missing OCR, unavailable sources, conflicting versions, or failed guardrails are stop-and-escalate conditions.
