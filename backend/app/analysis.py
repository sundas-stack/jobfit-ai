"""The fit-report pipeline.

1. requirements  : LLM reads the job ad and lists requirements (with the chunk they came from)
2. retrieval     : for each requirement, pgvector finds the closest resume chunks
3. judge         : LLM decides matched / partial / missing, quoting the resume
4. score         : plain Python (not the LLM) turns those decisions into a 0-100 score
5. coach         : LLM writes better resume lines, interview questions and next steps
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import prompts
from .ats import ats_report
from .db import Analysis, Document
from .llm import LLM, get_llm
from .retrieval import search

IMPORTANCE_WEIGHT = {"must": 3, "should": 2, "nice": 1}
MATCH_SHARE = 0.65  # final score = 65% requirement match + 35% ATS readiness
STATUS_VALUE = {"matched": 1.0, "partial": 0.5, "missing": 0.0}


class AnalysisError(ValueError):
    pass


def load_pair(session: Session, resume_id: int, job_id: int) -> tuple[Document, Document]:
    resume, job = session.get(Document, resume_id), session.get(Document, job_id)
    if not resume or resume.kind != "resume":
        raise AnalysisError("Resume not found.")
    if not job or job.kind != "job":
        raise AnalysisError("Job ad not found.")
    return resume, job


def extract_requirements(job: Document, llm: LLM) -> dict:
    data = llm.json(
        "requirements",
        prompts.REQUIREMENTS,
        {"job_chunks": [{"label": c.label, "text": c.text} for c in job.chunks]},
    )
    labels = {c.label for c in job.chunks}
    reqs = []
    for r in data.get("requirements", [])[:14]:
        skill = str(r.get("skill", "")).strip()
        if not skill:
            continue
        reqs.append(
            {
                "skill": skill[:60],
                "category": r.get("category", "technical"),
                "importance": r.get("importance") if r.get("importance") in IMPORTANCE_WEIGHT else "should",
                "detail": str(r.get("detail", ""))[:160],
                "source": r.get("source") if r.get("source") in labels else None,
            }
        )
    if not reqs:
        raise AnalysisError("Could not find any requirements in this job ad.")
    return {
        "job_title": str(data.get("job_title", ""))[:200],
        "company": str(data.get("company", ""))[:200],
        "requirements": reqs,
    }


def judge_requirements(session: Session, resume: Document, reqs: list[dict], llm: LLM) -> list[dict]:
    items = []
    for i, r in enumerate(reqs, start=1):
        hits = search(session, f"{r['skill']}. {r['detail']}", [resume.id], k=3)
        items.append({"id": i, **r, "evidence": [{"label": h.label, "text": h.text} for h in hits]})

    data = llm.json(
        "judge",
        prompts.JUDGE,
        {"requirements": [{k: v for k, v in it.items() if k != "source"} for it in items]},
    )
    by_id = {int(x.get("id", 0)): x for x in data.get("results", []) if str(x.get("id", "")).isdigit()}
    chunk_text = {c.label: c.text for c in resume.chunks}

    results = []
    for it in items:
        verdict = by_id.get(it["id"], {})
        status = verdict.get("status") if verdict.get("status") in STATUS_VALUE else "missing"
        label = verdict.get("evidence_label")
        if label not in chunk_text:
            label = None
        results.append(
            {
                "skill": it["skill"],
                "category": it["category"],
                "importance": it["importance"],
                "detail": it["detail"],
                "job_source": it["source"],
                "status": status,
                "evidence_label": label,
                "evidence_text": chunk_text.get(label, "") if label else "",
                "quote": str(verdict.get("quote", ""))[:240] if label else "",
                "note": str(verdict.get("note", ""))[:240],
            }
        )
    return results


def fit_score(results: list[dict]) -> int:
    """Weighted score: a missing 'must' hurts three times more than a missing 'nice'."""
    total = sum(IMPORTANCE_WEIGHT[r["importance"]] for r in results)
    if not total:
        return 0
    got = sum(IMPORTANCE_WEIGHT[r["importance"]] * STATUS_VALUE[r["status"]] for r in results)
    return round(100 * got / total)


def coach(resume: Document, job_title: str, results: list[dict], llm: LLM) -> dict:
    by = {s: [r["skill"] for r in results if r["status"] == s] for s in STATUS_VALUE}
    data = llm.json(
        "coach",
        prompts.COACH,
        {
            "job_title": job_title,
            "matched": by["matched"],
            "partial": by["partial"],
            "missing": by["missing"],
            "resume_chunks": [{"label": c.label, "text": c.text} for c in resume.chunks[:12]],
        },
    )
    labels = {c.label for c in resume.chunks}
    rewrites = [
        {**b, "source": b.get("source") if b.get("source") in labels else None}
        for b in data.get("bullet_rewrites", [])[:4]
        if b.get("before") and b.get("after")
    ]
    return {
        "summary": str(data.get("summary", "")),
        "strengths": [str(s) for s in data.get("strengths", [])][:4],
        "bullet_rewrites": rewrites,
        "interview_questions": [q for q in data.get("interview_questions", []) if q.get("question")][:6],
        "next_steps": [str(s) for s in data.get("next_steps", [])][:4],
    }


def overall_score(match: int, ats: int) -> int:
    return round(MATCH_SHARE * match + (1 - MATCH_SHARE) * ats)


def compare(session: Session, resume: Document, job: Document, llm: LLM | None = None) -> dict:
    """Requirements + judging + ATS checks + score. Used by the agent and the full report."""
    llm = llm or get_llm()
    req = extract_requirements(job, llm)
    results = judge_requirements(session, resume, req["requirements"], llm)
    match = fit_score(results)
    ats = ats_report(resume.text, results)
    return {**req, "results": results, "match_score": match, "ats": ats, "score": overall_score(match, ats["score"])}


def run_analysis(session: Session, resume_id: int, job_id: int, llm: LLM | None = None) -> Analysis:
    llm = llm or get_llm()
    resume, job = load_pair(session, resume_id, job_id)
    cmp = compare(session, resume, job, llm)
    results = cmp["results"]
    advice = coach(resume, cmp["job_title"] or job.title, results, llm)
    counts = {s: sum(1 for r in results if r["status"] == s) for s in STATUS_VALUE}

    analysis = Analysis(
        resume_id=resume.id,
        job_id=job.id,
        job_title=cmp["job_title"] or job.title,
        company=cmp["company"],
        score=cmp["score"],
        report={
            "requirements": results,
            "counts": counts,
            "match_score": cmp["match_score"],
            "ats": cmp["ats"],
            **advice,
            "model": llm.name,
            "resume_title": resume.title,
            "job_doc_title": job.title,
        },
    )
    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    return analysis


def latest_analysis(session: Session, resume_id: int, job_id: int) -> Analysis | None:
    return session.scalars(
        select(Analysis)
        .where(Analysis.resume_id == resume_id, Analysis.job_id == job_id)
        .order_by(Analysis.created_at.desc())
    ).first()
