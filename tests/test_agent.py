from wakili.safety.guardrails import has_citation, validate_grounding


def test_guardrails_require_citations():
    answer = "A grounded result. Sources: statute.txt"
    assert has_citation(answer)
    assert validate_grounding(answer, ["statute.txt"])
    assert not validate_grounding("An uncited result.", ["statute.txt"])
