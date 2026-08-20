# mini-wakili-agent

A modular Python scaffold for a grounded legal research agent. The repository separates orchestration, retrieval, and legal-AI safety concerns so each layer can be tested and replaced independently.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add provider credentials only when connecting a real model or search service.

## Run

```bash
PYTHONPATH=src python -m wakili.main "What documents are available?"
```

The default CLI runs locally without external services and reports the current corpus state.

## Test

```bash
PYTHONPATH=src python -m pytest
```

See [DESIGN.md](DESIGN.md) for architecture decisions and safety boundaries.

## Layout

- `src/wakili/agent`: orchestration and research tools
- `src/wakili/rag`: document chunking and retrieval
- `src/wakili/safety`: citation and grounding checks
- `data/raw`: source documents
- `data/index`: generated local indexes, ignored by Git
- `tests`: focused unit tests

This scaffold intentionally does not provide legal advice; it is infrastructure for building a cited research workflow.
