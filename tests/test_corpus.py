import json
from pathlib import Path

from mini_wakili import KNOWLEDGE_CORPUS, MiniWakiliAgent, load_local_corpus


def test_local_corpus_has_twenty_materials():
    assert len(KNOWLEDGE_CORPUS) >= 20
    assert len({item["id"] for item in KNOWLEDGE_CORPUS}) == len(KNOWLEDGE_CORPUS)
    assert all(item["jurisdiction"] == "KE" for item in KNOWLEDGE_CORPUS)


def test_local_materials_produce_specific_citations():
    result = MiniWakiliAgent().execute_research("what are employee written contract particulars")
    assert result["status"] == "SUCCESS"
    assert any("Employment Act" in citation["title"] for citation in result["citations"])
    assert all(citation["quote"] and citation["chunk_id"] for citation in result["citations"])


def test_loader_falls_back_for_invalid_corpus(tmp_path: Path):
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps([]), encoding="utf-8")
    assert len(load_local_corpus(broken)) >= 10
