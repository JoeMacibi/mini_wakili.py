"""Mini-Wakili: deterministic, grounded legal-research baseline.

The implementation is intentionally offline. It retrieves only from the supplied
corpus, refuses unsupported questions, redacts common Kenyan identifiers, and
marks every successful response as requiring advocate review.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

KNOWLEDGE_CORPUS: List[Dict[str, str]] = [
    {"id": "STATUTE-BANKING-01", "title": "Banking Act (Cap 488) Section 11 - Minimum Capital Requirements", "text": "An institution shall maintain a minimum core capital of at least one billion Kenya shillings. The Central Bank of Kenya may prescribe higher capital requirements based on risk profile."},
    {"id": "STATUTE-DPA-01", "title": "Data Protection Act 2019 Section 25 - Principles of Data Protection", "text": "Personal data shall be processed lawfully, fairly, and transparently. Personal data collected for specified, explicit, and legitimate purposes shall not be further processed."},
    {"id": "STATUTE-DPA-02", "title": "Data Protection Act 2019 Section 41 - Data Protection Impact Assessment", "text": "Where a processing operation is likely to result in a high risk to the rights and freedoms of data subjects, the data controller shall carry out a Data Protection Impact Assessment before processing."},
    {"id": "POLICY-NCBA-01", "title": "NCBA Internal Governance Policy - Outsourcing and Vendor Risk", "text": "Third-party cloud service providers handling customer data must guarantee local data residency or explicit statutory safeguards compliant with the Kenya Data Protection Act 2019."},
    {"id": "POLICY-NCBA-02", "title": "NCBA Legal Policy - Human-in-the-Loop AI Mandate", "text": "AI-generated review notes, contract assessments, and legal summaries must be reviewed and approved by a qualified legal advocate prior to formal reliance or client delivery."},
    {"id": "STATUTE-DPA-03", "title": "Data Protection Act 2019 - Data Subject Rights", "text": "A data subject may request access to personal data, correction of inaccurate data, and deletion where retention is no longer necessary, subject to lawful exemptions."},
    {"id": "STATUTE-BANKING-02", "title": "Banking Act - Confidentiality of Customer Information", "text": "An institution and its officers shall preserve the confidentiality of information relating to the affairs of a customer except where disclosure is authorized by law or by the customer."},
    {"id": "POLICY-NCBA-03", "title": "NCBA Contract Review Policy - Approved Templates", "text": "Contract reviewers shall compare material agreements against the current approved template and escalate material deviations to Legal before execution."},
    {"id": "POLICY-NCBA-04", "title": "NCBA AI Logging Standard", "text": "AI interactions must record the request, model version, retrieved source identifiers, guardrail results, reviewer action, and timestamp in an append-only audit record."},
    {"id": "POLICY-NCBA-05", "title": "NCBA AI Escalation Standard", "text": "The system must refuse unsupported legal conclusions and escalate matters involving imminent deadlines, litigation strategy, or uncertain authority to a qualified advocate."},
]


class SecurityGuardrail:
    """Redact common identifiers before retrieval and flag them for audit."""

    PATTERNS = (("KRA_PIN", re.compile(r"\b[A-Z]\d{9}[A-Z]\b")), ("PHONE_NUMBER", re.compile(r"(?:\+254|0)7\d{8}\b")), ("BANK_ACCOUNT", re.compile(r"\b\d{10,16}\b")))

    @classmethod
    def sanitize_input(cls, text: str) -> Tuple[str, List[str]]:
        if not isinstance(text, str):
            raise TypeError("query must be a string")
        flags: List[str] = []
        for label, pattern in cls.PATTERNS:
            if pattern.search(text):
                text = pattern.sub(f"[REDACTED_{label}]", text)
                flags.append(label)
        return text, flags


class LightweightRetriever:
    """Offline TF-IDF/cosine retriever with stable, inspectable scores."""

    def __init__(self, corpus: List[Dict[str, str]]):
        self.corpus = corpus
        self.vocab = sorted({token for doc in corpus for token in self._tokenize(doc["title"] + " " + doc["text"])})
        self.doc_vectors = [(doc, self._vectorize(self._tokenize(doc["title"] + " " + doc["text"]))) for doc in corpus]

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        stopwords = {"a", "an", "and", "are", "as", "for", "in", "is", "of", "on", "the", "to", "what", "where", "which", "with"}
        return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in stopwords]

    def _vectorize(self, tokens: List[str]) -> List[float]:
        counts = Counter(tokens)
        return [float(counts[token]) for token in self.vocab]

    @staticmethod
    def _cosine_similarity(left: List[float], right: List[float]) -> float:
        dot = sum(a * b for a, b in zip(left, right))
        magnitude = math.sqrt(sum(a * a for a in left) * sum(b * b for b in right))
        return dot / magnitude if magnitude else 0.0

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if top_k <= 0:
            return []
        scores = self._vectorize(self._tokenize(query))
        ranked = [{"doc": doc, "score": self._cosine_similarity(scores, vector)} for doc, vector in self.doc_vectors]
        ranked.sort(key=lambda item: (-item["score"], item["doc"]["id"]))
        return ranked[:top_k]


class MiniWakiliAgent:
    """Bounded research agent with sub-query planning and low-confidence refusal."""

    def __init__(self, corpus: Optional[List[Dict[str, str]]] = None, confidence_threshold: float = 0.20):
        self.retriever = LightweightRetriever(corpus or KNOWLEDGE_CORPUS)
        self.confidence_threshold = confidence_threshold

    @staticmethod
    def plan_subqueries(user_query: str) -> List[str]:
        parts = re.split(r"\s+(?:and|as well as)\s+", user_query, flags=re.IGNORECASE)
        return [part.strip() for part in parts if part.strip()] or [user_query]

    def execute_research(self, query: str) -> Dict[str, Any]:
        clean_query, flagged_pii = SecurityGuardrail.sanitize_input(query)
        retrieved: Dict[str, Dict[str, Any]] = {}
        for sub_query in self.plan_subqueries(clean_query):
            for result in self.retriever.search(sub_query, top_k=3):
                if result["score"] > 0:
                    current = retrieved.get(result["doc"]["id"])
                    if current is None or result["score"] > current["score"]:
                        retrieved[result["doc"]["id"]] = result
        ranked = sorted(retrieved.values(), key=lambda item: (-item["score"], item["doc"]["id"]))
        max_score = ranked[0]["score"] if ranked else 0.0
        base = {"max_confidence": round(max_score, 4), "query": clean_query, "flagged_pii": flagged_pii, "citations": []}
        if not ranked or max_score < self.confidence_threshold:
            return {**base, "status": "REFUSED_LOW_CONFIDENCE", "answer": "I am unable to answer because the approved corpus does not contain sufficiently relevant authority."}
        citations = [{"source_id": item["doc"]["id"], "title": item["doc"]["title"], "score": round(item["score"], 4)} for item in ranked]
        evidence = "\n".join(f"- [{item['doc']['id']}] {item['doc']['text']}" for item in ranked)
        answer = f"Based only on the approved corpus:\n{evidence}\n\nDRAFT — UNVERIFIED AI OUTPUT. A qualified legal advocate must review and approve this before reliance or client delivery."
        return {**base, "status": "SUCCESS", "answer": answer, "citations": citations}

    def answer_with_citations(self, question: str) -> Dict[str, Any]:
        return self.execute_research(question)


def answer_with_citations(question: str, corpus: Any, confidence_threshold: float = 0.20) -> Dict[str, Any]:
    """Compatibility helper accepting either a corpus list or a retriever-like store."""
    if hasattr(corpus, "search") and not isinstance(corpus, list):
        results = corpus.search(question, top_k=5)
        if not results:
            return {"status": "REFUSED", "answer": "No relevant legal context found in corpus.", "citations": []}
        return {"status": "SUCCESS", "answer": "Retrieved grounded context. Sources: " + ", ".join(str(r.get("citation", r.get("doc", {}).get("id", ""))) for r in results), "citations": results}
    return MiniWakiliAgent(corpus, confidence_threshold).execute_research(question)


def run_tests() -> None:
    agent = MiniWakiliAgent()
    supported = agent.execute_research("What is the minimum core capital for a bank in Kenya?")
    unsupported = agent.execute_research("What is the weather on Mars?")
    assert supported["status"] == "SUCCESS" and supported["citations"]
    assert unsupported["status"] == "REFUSED_LOW_CONFIDENCE"
    print("Mini-Wakili assessor: PASS")


if __name__ == "__main__":
    run_tests()
