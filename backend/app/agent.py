"""Agent mode: the LLM picks tools in a loop, and every step is streamed to the UI.

loop:
    ask the LLM (with the tool list)
    if it wants tools -> run them, add the results to the conversation, repeat
    else             -> that's the final answer
"""

import json
import re
from collections.abc import Iterator

from sqlalchemy.orm import Session

from . import prompts
from .analysis import compare, latest_analysis, load_pair
from .db import Document
from .llm import LLM, LLMError, get_llm
from .retrieval import search

MAX_STEPS = 6

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_resume",
            "description": "Search the candidate's resume for evidence. Returns the most relevant chunks.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "What to look for"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_job",
            "description": "Search the job ad for requirements, responsibilities or company details.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "What to look for"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_skills",
            "description": "Compare the resume with the job's requirements. Returns the fit score and "
            "which skills are matched, partial or missing.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rewrite_bullet",
            "description": "Rewrite one resume line so it fits this job better, without inventing facts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The original resume line"},
                    "focus": {"type": "string", "description": "Optional skill to emphasise"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "interview_questions",
            "description": "Generate likely interview questions for this job, with answer tips.",
            "parameters": {
                "type": "object",
                "properties": {"focus": {"type": "string", "description": "Optional topic to focus on"}},
            },
        },
    },
]

LABELS = {
    "search_resume": "Searching your resume",
    "search_job": "Searching the job ad",
    "compare_skills": "Comparing skills with the job",
    "rewrite_bullet": "Rewriting a resume line",
    "interview_questions": "Preparing interview questions",
}


class Toolbox:
    """Runs tools for one resume + job pair and remembers every source it found."""

    def __init__(self, session: Session, resume: Document, job: Document, llm: LLM):
        self.session, self.resume, self.job, self.llm = session, resume, job, llm
        self.sources: dict[str, dict] = {}
        self._fit: dict | None = None

    def _search(self, query: str, doc: Document) -> tuple[dict, str]:
        hits = search(self.session, query, [doc.id], k=3)
        for h in hits:
            self.sources[h.label] = h.to_dict()
        results = [{"label": h.label, "text": h.text, "relevance": h.score} for h in hits]
        return {"results": results}, f"Found {len(hits)} relevant part{'s' if len(hits) != 1 else ''}"

    def fit(self) -> dict:
        if self._fit is None:
            saved = latest_analysis(self.session, self.resume.id, self.job.id)
            if saved and "ats" in saved.report:
                rep = saved.report
                results, score, title = rep["requirements"], saved.score, saved.job_title
                match, ats = rep["match_score"], rep["ats"]
            else:
                cmp = compare(self.session, self.resume, self.job, self.llm)
                results, score, title = cmp["results"], cmp["score"], cmp["job_title"]
                match, ats = cmp["match_score"], cmp["ats"]
            for r in results:
                if r.get("evidence_label"):
                    self.sources[r["evidence_label"]] = {
                        "label": r["evidence_label"],
                        "text": r["evidence_text"],
                        "kind": "resume",
                        "document_title": self.resume.title,
                        "document_id": self.resume.id,
                    }
            self._fit = {
                "job_title": title,
                "score": score,
                "requirement_match": match,
                "ats_readiness": ats["score"],
                "ats_problems": [f"{c['name']}: {c['tip']}" for c in ats["checks"] if c["status"] != "good"],
                **{s: [r["skill"] for r in results if r["status"] == s] for s in ("matched", "partial", "missing")},
                "evidence": {r["skill"]: r.get("evidence_label") for r in results if r.get("evidence_label")},
            }
        return self._fit

    def run(self, name: str, args: dict) -> tuple[dict, str]:
        if name == "search_resume":
            return self._search(str(args.get("query", "")), self.resume)
        if name == "search_job":
            return self._search(str(args.get("query", "")), self.job)
        if name == "compare_skills":
            fit = self.fit()
            return (
                fit,
                f"Fit score {fit['score']}% · {len(fit['missing'])} gap{'s' if len(fit['missing']) != 1 else ''}",
            )
        if name == "rewrite_bullet":
            fit = self.fit()
            out = self.llm.json(
                "rewrite",
                prompts.REWRITE,
                {
                    "text": str(args.get("text", "")),
                    "focus": args.get("focus"),
                    "job_requirements": fit["matched"] + fit["partial"] + fit["missing"],
                },
            )
            return out, "Rewrote the line"
        if name == "interview_questions":
            fit = self.fit()
            out = self.llm.json(
                "questions",
                prompts.QUESTIONS,
                {"matched": fit["matched"], "missing": fit["missing"], "focus": args.get("focus")},
            )
            return out, f"Prepared {len(out.get('questions', []))} questions"
        return {"error": f"Unknown tool {name}"}, "Unknown tool"


def run_agent(
    session: Session,
    resume_id: int,
    job_id: int,
    message: str,
    history: list[dict] | None = None,
    llm: LLM | None = None,
) -> Iterator[dict]:
    llm = llm or get_llm()
    try:
        resume, job = load_pair(session, resume_id, job_id)
    except ValueError as exc:
        yield {"type": "error", "message": str(exc)}
        return

    box = Toolbox(session, resume, job, llm)
    context = f"Resume: '{resume.title}' (chunks R1..). Job ad: '{job.title}' (chunks J1..)."
    messages: list[dict] = [{"role": "system", "content": prompts.AGENT + "\n" + context}]
    for h in (history or [])[-8:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            messages.append({"role": h["role"], "content": str(h["content"])[:4000]})
    messages.append({"role": "user", "content": message})

    step = 0
    try:
        for _ in range(MAX_STEPS):
            reply = llm.chat(messages, TOOLS)
            calls = reply["tool_calls"]
            if not calls:
                yield from _finish(reply.get("content") or "", box)
                return
            messages.append(
                {
                    "role": "assistant",
                    "content": reply.get("content") or "",
                    "tool_calls": [
                        {
                            "id": c["id"],
                            "type": "function",
                            "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])},
                        }
                        for c in calls
                    ],
                }
            )
            for c in calls:
                step += 1
                base = {
                    "type": "step",
                    "id": step,
                    "tool": c["name"],
                    "label": LABELS.get(c["name"], c["name"]),
                    "args": c["arguments"],
                }
                yield {**base, "status": "running"}
                result, summary = box.run(c["name"], c["arguments"])
                yield {**base, "status": "done", "summary": summary}
                messages.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(result)[:6000]})
        # too many steps: ask for an answer without tools
        reply = llm.chat(messages + [{"role": "user", "content": "Please answer now with what you found."}], [])
        yield from _finish(reply.get("content") or "", box)
    except LLMError as exc:
        yield {"type": "error", "message": str(exc)}


def clean_answer(text: str) -> str:
    """Normalise model quirks: 【R4】 or 【R4†L1】 citations, <br> tags and tool-name citations."""
    text = re.sub(r"【\s*([RJ]\d+)[^】]*】", r"[\1]", text)
    text = re.sub(r"【[^】]*】", "", text)
    # inside a table row a line break would split the row, so use a separator there
    text = "\n".join(
        re.sub(r"(?i)<br\s*/?>", "; " if ln.lstrip().startswith("|") else "\n", ln) for ln in text.split("\n")
    )
    text = re.sub(r"\[(?:compare_skills|search_resume|search_job|rewrite_bullet|interview_questions)\]", "", text)
    return text.strip()


def _finish(text: str, box: Toolbox) -> Iterator[dict]:
    text = clean_answer(text)
    cited = [lbl for lbl in box.sources if f"[{lbl}]" in text]
    yield {"type": "sources", "items": [box.sources[lbl] for lbl in cited]}
    yield {"type": "answer", "text": text}
    yield {"type": "done"}
