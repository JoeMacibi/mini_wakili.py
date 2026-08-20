from mini_wakili import ContractReviewRequest, ContractReviewService, HITLWorkflow, MiniWakiliAgent, benchmark_metrics


def test_model_benchmark_exceeds_target():
    metrics = benchmark_metrics(MiniWakiliAgent())
    assert metrics["aggregate_score"] >= 85
    assert metrics["target_met"]


def test_chunk_citations_and_claim_support_are_emitted():
    result = MiniWakiliAgent().execute_research("minimum core capital for a bank")
    assert result["status"] == "SUCCESS"
    assert result["citations"][0]["chunk_id"]
    assert result["citations"][0]["quote"]
    assert all(claim["supported"] for claim in result["claims"])


def test_hitl_requires_authenticated_approval():
    workflow = HITLWorkflow(MiniWakiliAgent().audit)
    assert workflow.approve("reviewer-1", "approve")["state"] == "EVIDENCE_REVIEW"
    assert workflow.approve("reviewer-1", "approve")["state"] == "APPROVED_FOR_RELIANCE"


def test_contract_review_flags_risky_clauses_and_template_deviations():
    result = ContractReviewService().review(ContractReviewRequest(
        "The supplier may terminate this agreement. The supplier has unlimited liability.",
        template_text="The supplier may terminate this agreement. The supplier must maintain insurance.",
    ))
    assert result["status"] == "REVIEW_REQUIRED"
    assert any(r["type"] == "unlimited_liability" for r in result["risks"])
    assert result["template_deviations"]
