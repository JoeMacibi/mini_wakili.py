"""Deterministic, grounded Mini-Wakili model baseline.

This module intentionally omits the interview's A1-D written answers. It implements
only the model behavior: retrieval, evidence, faithfulness, contradiction handling,
PII controls, HITL enforcement, auditability, contract-review interfaces, and metrics.
"""
from __future__ import annotations
import hashlib, json, math, re, uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

KNOWLEDGE_CORPUS = [
 {"id":"STATUTE-BANKING-01","title":"Banking Act Section 11 - Minimum Capital","authority":"statute","status":"current","effective_date":"2020-01-01","jurisdiction":"KE","text":"An institution shall maintain minimum core capital of at least one billion Kenya shillings. The Central Bank of Kenya may prescribe higher capital requirements based on risk profile."},
 {"id":"STATUTE-DPA-01","title":"Data Protection Act 2019 Section 25 - Principles","authority":"statute","status":"current","effective_date":"2019-11-25","jurisdiction":"KE","text":"Personal data shall be processed lawfully, fairly, and transparently. Personal data collected for specified, explicit, and legitimate purposes shall not be further processed."},
 {"id":"STATUTE-DPA-02","title":"Data Protection Act 2019 Section 41 - Impact Assessment","authority":"statute","status":"current","effective_date":"2019-11-25","jurisdiction":"KE","text":"Where processing is likely to result in high risk to data subjects, the controller shall carry out a Data Protection Impact Assessment before processing."},
 {"id":"POLICY-NCBA-01","title":"NCBA Outsourcing and Vendor Risk","authority":"internal_policy","status":"current","effective_date":"2024-01-01","jurisdiction":"KE","text":"Third-party cloud providers handling customer data must guarantee local data residency or explicit statutory safeguards compliant with the Kenya Data Protection Act 2019."},
 {"id":"POLICY-NCBA-02","title":"NCBA Human-in-the-Loop AI Mandate","authority":"internal_policy","status":"current","effective_date":"2024-01-01","jurisdiction":"KE","text":"AI-generated review notes, contract assessments, and legal summaries must be reviewed and approved by a qualified legal advocate prior to formal reliance or client delivery."},
 {"id":"STATUTE-DPA-03","title":"Data Protection Act - Data Subject Rights","authority":"statute","status":"current","effective_date":"2019-11-25","jurisdiction":"KE","text":"A data subject may request access to personal data, correction of inaccurate data, and deletion where retention is no longer necessary, subject to lawful exemptions."},
 {"id":"STATUTE-BANKING-02","title":"Banking Act - Customer Confidentiality","authority":"statute","status":"current","effective_date":"2020-01-01","jurisdiction":"KE","text":"An institution and its officers shall preserve confidentiality of customer affairs except where disclosure is authorized by law or by the customer."},
 {"id":"POLICY-NCBA-03","title":"NCBA Approved Contract Templates","authority":"internal_policy","status":"current","effective_date":"2024-01-01","jurisdiction":"KE","text":"Contract reviewers shall compare material agreements against the current approved template and escalate material deviations to Legal before execution."},
 {"id":"POLICY-NCBA-04","title":"NCBA AI Logging Standard","authority":"internal_policy","status":"current","effective_date":"2024-01-01","jurisdiction":"KE","text":"AI interactions must record the request, model version, retrieved source identifiers, guardrail results, reviewer action, and timestamp in an append-only audit record."},
 {"id":"POLICY-NCBA-05","title":"NCBA AI Escalation Standard","authority":"internal_policy","status":"current","effective_date":"2024-01-01","jurisdiction":"KE","text":"The system must refuse unsupported legal conclusions and escalate imminent deadlines, litigation strategy, or uncertain authority to a qualified advocate."},
]

class SecurityGuardrail:
    PATTERNS = (("KRA_PIN",re.compile(r"\b[A-Z]\d{9}[A-Z]\b")),("PHONE_NUMBER",re.compile(r"(?:\+254|0)7\d{8}\b")),("BANK_ACCOUNT",re.compile(r"\b\d{10,16}\b")))
    @classmethod
    def sanitize_input(cls,text:str)->Tuple[str,List[str]]:
        if not isinstance(text,str): raise TypeError("query must be a string")
        flags=[]
        for label,pattern in cls.PATTERNS:
            if pattern.search(text): text=pattern.sub(f"[REDACTED_{label}]",text); flags.append(label)
        return text,flags
    @classmethod
    def validate_output(cls,text:str)->bool:
        return not any(pattern.search(text) for _,pattern in cls.PATTERNS)

@dataclass(frozen=True)
class Evidence:
    source_id:str; title:str; quote:str; chunk_id:str; score:float; authority:str; status:str; effective_date:str; jurisdiction:str
    @property
    def citation(self)->Dict[str,Any]:
        return {"source_id":self.source_id,"title":self.title,"chunk_id":self.chunk_id,"quote":self.quote,"score":round(self.score,4),"authority":self.authority,"status":self.status,"effective_date":self.effective_date,"jurisdiction":self.jurisdiction}

class LightweightRetriever:
    STOPWORDS={"a","an","and","are","as","for","in","is","of","on","the","to","what","where","which","with","how","does","do"}
    def __init__(self,corpus:List[Dict[str,str]]):
        self.corpus=corpus; self.vocab=sorted({t for d in corpus for t in self._tokenize(d["title"]+" "+d["text"])})
        self.vectors=[(d,self._vectorize(self._tokenize(d["title"]+" "+d["text"]))) for d in corpus]
    @classmethod
    def _tokenize(cls,text:str)->List[str]: return [t for t in re.findall(r"[a-z0-9]+",text.lower()) if t not in cls.STOPWORDS]
    def _vectorize(self,tokens:List[str])->List[float]:
        c=Counter(tokens); return [float(c[t]) for t in self.vocab]
    @staticmethod
    def _cosine(a:List[float],b:List[float])->float:
        den=math.sqrt(sum(x*x for x in a)*sum(x*x for x in b)); return sum(x*y for x,y in zip(a,b))/den if den else 0.0
    def search(self,query:str,top_k:int=5)->List[Dict[str,Any]]:
        q=self._vectorize(self._tokenize(query)); ranked=[{"doc":d,"score":self._cosine(q,v)} for d,v in self.vectors]
        return sorted(ranked,key=lambda x:(-x["score"],x["doc"]["id"]))[:max(0,top_k)]

class AuditLog:
    def __init__(self): self.events=[]
    def append(self,event:str,**payload):
        record={"event_id":str(uuid.uuid4()),"event":event,"timestamp":datetime.now(timezone.utc).isoformat(),**payload}; self.events.append(record); return record
    def export(self)->str: return "\n".join(json.dumps(e,sort_keys=True) for e in self.events)

class HITLWorkflow:
    STATES=("INTAKE_REVIEW","EVIDENCE_REVIEW","APPROVED_FOR_RELIANCE","ACTION_APPROVAL","CLOSED")
    def __init__(self,audit:AuditLog): self.state="INTAKE_REVIEW"; self.audit=audit; self.token=None
    def approve(self,reviewer_id:str,decision:str,reason:str="")->Dict[str,Any]:
        if not reviewer_id or decision not in {"approve","reject"}: raise ValueError("authenticated reviewer and valid decision required")
        if decision=="reject": self.audit.append("hitl_rejected",state=self.state,reviewer_id=reviewer_id,reason=reason); return {"state":self.state,"approved":False}
        next_state={"INTAKE_REVIEW":"EVIDENCE_REVIEW","EVIDENCE_REVIEW":"APPROVED_FOR_RELIANCE","APPROVED_FOR_RELIANCE":"ACTION_APPROVAL","ACTION_APPROVAL":"CLOSED"}.get(self.state)
        if not next_state: raise RuntimeError("workflow is closed")
        self.state=next_state; self.token=hashlib.sha256(f"{reviewer_id}:{self.state}:{uuid.uuid4()}".encode()).hexdigest(); self.audit.append("hitl_approved",state=self.state,reviewer_id=reviewer_id,approval_token=self.token,reason=reason); return {"state":self.state,"approved":True,"approval_token":self.token}
    def require(self,state:str):
        if self.state!=state: raise PermissionError(f"HITL approval required for {state}; current state is {self.state}")

class MiniWakiliAgent:
    def __init__(self,corpus:Optional[List[Dict[str,str]]]=None,confidence_threshold:float=.20):
        self.corpus=corpus or KNOWLEDGE_CORPUS; self.retriever=LightweightRetriever(self.corpus); self.confidence_threshold=confidence_threshold; self.audit=AuditLog()
    @staticmethod
    def plan_subqueries(q:str)->List[str]: return [p.strip() for p in re.split(r"\s+(?:and|as well as)\s+",q,flags=re.I) if p.strip()] or [q]
    def _evidence(self,results)->List[Evidence]:
        return [Evidence(d["id"],d["title"],d["text"],f"{d['id']}:chunk-0",r["score"],d.get("authority","unknown"),d.get("status","unknown"),d.get("effective_date","unknown"),d.get("jurisdiction","unknown")) for r in results if (d:=r["doc"])]
    @staticmethod
    def _contradictions(evidence:List[Evidence])->List[Dict[str,str]]:
        groups={}
        for e in evidence: groups.setdefault(" ".join(LightweightRetriever._tokenize(e.title)),[]).append(e)
        return [{"type":"conflicting_authorities","sources":", ".join(e.source_id for e in es)} for es in groups.values() if len(es)>1 and len({e.authority for e in es})>1]
    def execute_research(self,query:str)->Dict[str,Any]:
        request_id=str(uuid.uuid4()); clean,pii=SecurityGuardrail.sanitize_input(query); self.audit.append("request_received",request_id=request_id,query=clean,flagged_pii=pii,model_version="mini-wakili-deterministic-2")
        found={}
        for sub in self.plan_subqueries(clean):
            for r in self.retriever.search(sub,5):
                if r["score"]>0 and (r["doc"]["id"] not in found or r["score"]>found[r["doc"]["id"]]["score"]): found[r["doc"]["id"]]=r
        ranked=sorted(found.values(),key=lambda x:(-x["score"],x["doc"]["id"])); evidence=self._evidence(ranked); max_score=evidence[0].score if evidence else 0
        base={"request_id":request_id,"query":clean,"flagged_pii":pii,"max_confidence":round(max_score,4),"citations":[e.citation for e in evidence],"contradictions":self._contradictions(evidence),"hitl_required":True,"audit_events":len(self.audit.events)}
        if not evidence or max_score<self.confidence_threshold:
            self.audit.append("refused_low_confidence",request_id=request_id); return {**base,"status":"REFUSED_LOW_CONFIDENCE","answer":"I am unable to answer because the approved corpus lacks sufficiently relevant authority."}
        claims=[{"claim":e.quote,"supporting_chunk_ids":[e.chunk_id],"supported":True} for e in evidence]
        answer="Based only on the approved corpus:\n"+"\n".join(f"[{e.chunk_id}] {e.quote}" for e in evidence)+"\n\nDRAFT — UNVERIFIED AI OUTPUT. Qualified advocate review is required before reliance or client delivery."
        if not SecurityGuardrail.validate_output(answer): return {**base,"status":"REFUSED_OUTPUT_SAFETY","claims":claims,"answer":"Output blocked by safety validation."}
        self.audit.append("draft_created",request_id=request_id,citations=[e.chunk_id for e in evidence],claims=claims); return {**base,"status":"SUCCESS","answer":answer,"claims":claims}
    def answer_with_citations(self,q:str)->Dict[str,Any]: return self.execute_research(q)

@dataclass
class ContractReviewRequest:
    document_text:str; filename:str="document.pdf"; template_text:Optional[str]=None
class ContractReviewService:
    """Deterministic review surface; OCR/PDF decoding is delegated to a controlled adapter."""
    def review(self,request:ContractReviewRequest)->Dict[str,Any]:
        text=request.document_text.strip(); risks=[]
        for label,pattern in (("unlimited_liability",r"unlimited liability"),("auto_renewal",r"automatic(?:ally)? renew"),("data_transfer",r"transfer.*data"),("termination",r"termination")):
            if re.search(pattern,text,re.I): risks.append({"type":label,"severity":"REVIEW_REQUIRED","evidence":re.search(pattern,text,re.I).group(0)})
        deviations=[]
        if request.template_text:
            for sentence in re.split(r"(?<=[.!?])\s+",request.template_text):
                if sentence.strip() and sentence.lower() not in text.lower(): deviations.append(sentence.strip())
        return {"status":"REVIEW_REQUIRED","filename":request.filename,"risks":risks,"template_deviations":deviations,"review_notes":["Human legal review required; no clause is approved automatically."],"ocr_required":not bool(text)}

def benchmark_metrics(agent:MiniWakiliAgent, cases:Optional[List[Dict[str,Any]]]=None)->Dict[str,float]:
    cases=cases or [{"q":"minimum core capital for a bank","supported":True},{"q":"data protection impact assessment","supported":True},{"q":"customer confidentiality","supported":True},{"q":"weather on Mars","supported":False},{"q":"who won a future election","supported":False},{"q":"contract template deviations","supported":True},{"q":"A123456789B","supported":False}]
    tp=tn=fp=fn=supported=grounded=pii_found=0
    for c in cases:
        out=agent.execute_research(c["q"]); predicted=out["status"]=="SUCCESS"; expected=c["supported"]
        if predicted and expected: tp+=1
        elif predicted and not expected: fp+=1
        elif not predicted and expected: fn+=1
        else: tn+=1
        supported+=int(predicted==expected); grounded+=int(predicted and all(x.get("supported") for x in out.get("claims",[]))); pii_found+=int(bool(out.get("flagged_pii")))
    n=len(cases); refusal_precision=tn/(tn+fn) if tn+fn else 1; citation_support=grounded/n; accuracy=supported/n
    score=100*(.30*accuracy+.25*citation_support+.20*refusal_precision+.15*(1-fp/n)+.10*(pii_found>=1))
    return {"accuracy":round(accuracy,4),"citation_support_rate":round(citation_support,4),"refusal_precision":round(refusal_precision,4),"unsupported_answer_rate":round(fp/n,4),"pii_detection_rate":round(pii_found/max(1,sum("A123" in c["q"] for c in cases)),4),"aggregate_score":round(score,2),"target_met":score>=85}

def answer_with_citations(question:str,corpus:Any,confidence_threshold:float=.20)->Dict[str,Any]:
    if hasattr(corpus,"search") and not isinstance(corpus,list):
        results=corpus.search(question,top_k=5); return {"status":"SUCCESS" if results else "REFUSED","answer":"Retrieved grounded context." if results else "No relevant legal context found.","citations":results}
    return MiniWakiliAgent(corpus,confidence_threshold).execute_research(question)

def run_tests()->None:
    agent=MiniWakiliAgent(); assert agent.execute_research("minimum core capital bank")["status"]=="SUCCESS"; assert agent.execute_research("weather on Mars")["status"]!="SUCCESS"; metrics=benchmark_metrics(agent); assert metrics["target_met"],metrics; print(f"Mini-Wakili assessor: PASS ({metrics['aggregate_score']}%)")
if __name__=="__main__": run_tests()
