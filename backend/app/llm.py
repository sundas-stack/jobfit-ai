"""LLM clients.

* OpenAICompatLLM talks to Groq (or any OpenAI-compatible API).
* DemoLLM needs no key: it follows simple rules so the app (and the tests) work offline.

Both expose the same two methods, so the rest of the code never cares which one is used.
"""

import json
import re
from functools import lru_cache
from typing import Any, Protocol

from .config import get_settings
from .skills import SOFT, find_skills, mentions


class LLMError(RuntimeError):
    pass


class LLM(Protocol):
    name: str

    def json(self, task: str, system: str, payload: dict) -> dict: ...

    def chat(self, messages: list[dict], tools: list[dict]) -> dict: ...


# ───────────────────────────── real LLM ─────────────────────────────


class OpenAICompatLLM:
    def __init__(self, api_key: str, base_url: str, model: str):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=60)
        self.model = model
        self.name = model

    def json(self, task: str, system: str, payload: dict) -> dict:
        messages = [
            {"role": "system", "content": system + "\nRespond with one JSON object only."},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        last_err: Exception | None = None
        for _ in range(2):  # one retry if the model returns broken JSON
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.2,
                )
                return json.loads(resp.choices[0].message.content or "{}")
            except json.JSONDecodeError as exc:
                last_err = exc
            except Exception as exc:  # network / auth / rate limit
                raise LLMError(f"LLM request failed: {exc}") from exc
        raise LLMError(f"LLM returned invalid JSON for task '{task}': {last_err}")

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        extra = {"tools": tools, "tool_choice": "auto"} if tools else {}
        try:
            resp = self.client.chat.completions.create(model=self.model, messages=messages, temperature=0.2, **extra)
        except Exception as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc
        msg = resp.choices[0].message
        calls = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append({"id": tc.id, "name": tc.function.name, "arguments": args})
        return {"content": msg.content, "tool_calls": calls}


# ───────────────────────────── demo LLM ─────────────────────────────

NICE = re.compile(r"nice to have|bonus|\bplus\b|preferred|ideally|familiarity|desirable")
MUST = re.compile(r"required|must|essential|strong|proficien|\d\+? ?years|solid|expert|deep")


def _line_with(skill: str, text: str) -> str:
    for line in text.split("\n"):
        if mentions(skill, line):
            line = line.strip("•-* ").strip()
            words = line.split()
            return " ".join(words[:20]) + ("…" if len(words) > 20 else "")
    return ""


class DemoLLM:
    """Rule-based stand-in for an LLM. Clearly labelled as demo mode in the UI."""

    name = "demo (rule-based)"

    def json(self, task: str, system: str, payload: dict) -> dict:
        return getattr(self, f"_{task}")(payload)

    # requirements from the job ad
    def _requirements(self, p: dict) -> dict:
        chunks = p["job_chunks"]
        full = "\n".join(c["text"] for c in chunks)
        first = next((ln.strip() for ln in full.split("\n") if ln.strip()), "Job")
        company = ""
        m = re.search(r"(?i:company|employer)\s*[:\-]\s*([A-Z][\w&.\- ]{1,40})", full) or re.search(
            r"\bat ([A-Z][\w&.\-]+(?: [A-Z][\w&.\-]+)?)", full
        )
        if m:
            company = m.group(1).strip()
        rank = {"nice": 0, "should": 1, "must": 2}
        found: dict[str, dict] = {}
        section = None
        for c in chunks:
            for line in c["text"].split("\n"):
                low = line.lower().strip()
                is_heading = low and len(low) < 40 and not low.startswith(("•", "-", "*")) and not low.endswith(".")
                if is_heading:
                    section = (
                        "nice"
                        if NICE.search(low)
                        else "must"
                        if re.search(r"requirement|qualification|must|what you need|you have", low)
                        else None
                    )
                    continue
                importance = (
                    "nice"
                    if NICE.search(low) or section == "nice"
                    else "must"
                    if MUST.search(low) or section == "must"
                    else "should"
                )
                for skill in find_skills(line):
                    prev = found.get(skill)
                    if prev and rank[prev["importance"]] >= rank[importance]:
                        continue
                    found[skill] = {
                        "skill": skill,
                        "category": "soft" if skill in SOFT else "technical",
                        "importance": importance,
                        "detail": line.strip("•-* ").strip()[:90],
                        "source": c["label"],
                    }
        reqs = list(found.values())
        order = {"must": 0, "should": 1, "nice": 2}
        reqs.sort(key=lambda r: (order[r["importance"]], r["category"] == "soft"))
        return {"job_title": first[:90], "company": company, "requirements": reqs[:14]}

    # matched / partial / missing
    def _judge(self, p: dict) -> dict:
        results = []
        for r in p["requirements"]:
            hit = next((e for e in r["evidence"] if mentions(r["skill"], e["text"])), None)
            if hit:
                results.append(
                    {
                        "id": r["id"],
                        "status": "matched",
                        "evidence_label": hit["label"],
                        "quote": _line_with(r["skill"], hit["text"]),
                        "note": f"The resume mentions {r['skill']} directly.",
                    }
                )
            else:
                results.append(
                    {
                        "id": r["id"],
                        "status": "missing",
                        "evidence_label": None,
                        "quote": "",
                        "note": f"No mention of {r['skill']} found in the resume.",
                    }
                )
        return {"results": results}

    # coaching
    def _coach(self, p: dict) -> dict:
        matched, missing = p["matched"], p["missing"]
        lines = []
        for c in p["resume_chunks"]:
            for ln in c["text"].split("\n"):
                clean = ln.strip("•-* ").strip()
                if 40 < len(clean) < 220:
                    lines.append((c["label"], clean))
        lines.sort(key=lambda x: -len(x[1]))
        rewrites = []
        kw = ", ".join(matched[:2]) or "the core stack"
        for label, line in lines[:3]:
            after = line[0].upper() + line[1:]
            if not re.match(r"^(Built|Led|Designed|Developed|Created|Delivered|Shipped|Improved)", after):
                after = "Delivered: " + after
            after = after.rstrip(".,;: ")
            rewrites.append(
                {
                    "source": label,
                    "before": line,
                    "after": f"{after}, highlighting {kw}.",
                    "why": "Leads with impact and repeats keywords from the job ad.",
                }
            )
        qs = [
            {
                "question": f"Tell us about a project where you used {s}.",
                "why": f"{s} is a key requirement.",
                "tip": "Use the STAR format and point to the matching line in your resume.",
            }
            for s in matched[:3]
        ] + [
            {
                "question": f"How would you get up to speed with {s}?",
                "why": f"{s} is not on your resume.",
                "tip": "Be honest, then show a related skill and a concrete learning plan.",
            }
            for s in missing[:2]
        ]
        total = len(matched) + len(missing) + len(p.get("partial", []))
        return {
            "summary": (
                f"Demo mode: rule-based keyword matching (add an API key for real AI analysis). "
                f"You match {len(matched)} of {total} listed requirements."
            ),
            "strengths": [f"Hands-on {s}" for s in matched[:3]],
            "bullet_rewrites": rewrites,
            "interview_questions": qs,
            "next_steps": [f"Build a small project with {s}" for s in missing[:3]]
            or ["Tailor your summary to the job title"],
        }

    def _rewrite(self, p: dict) -> dict:
        line = p["text"].strip("•-* ").strip()
        focus = p.get("focus") or "the job's key skills"
        return {
            "after": f"Delivered {line[0].lower() + line[1:]}".rstrip(".") + f", highlighting {focus}.",
            "why": "Starts with impact and adds keywords from the job ad (demo mode).",
        }

    def _questions(self, p: dict) -> dict:
        skills = p.get("missing", [])[:2] + p.get("matched", [])[:3]
        return {
            "questions": [
                {
                    "question": f"Walk us through your experience with {s}.",
                    "why": f"{s} appears in the job ad.",
                    "tip": "Answer with one concrete project and its result.",
                }
                for s in skills
            ]
        }

    # scripted agent: compare skills -> search resume -> answer
    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        question = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        if len(tool_msgs) == 0:
            return {
                "content": None,
                "tool_calls": [{"id": "demo-1", "name": "compare_skills", "arguments": {}}],
            }
        if len(tool_msgs) == 1:
            return {
                "content": None,
                "tool_calls": [{"id": "demo-2", "name": "search_resume", "arguments": {"query": question}}],
            }
        fit: dict[str, Any] = json.loads(tool_msgs[0]["content"])
        hits = json.loads(tool_msgs[1]["content"]).get("results", [])
        cite = f" [{hits[0]['label']}]" if hits else ""
        matched = ", ".join(fit.get("matched", [])[:5]) or "none yet"
        missing = ", ".join(fit.get("missing", [])[:5]) or "nothing major"
        return {
            "content": (
                f"Your fit score is **{fit.get('score', 0)}%** (requirements {fit.get('requirement_match', 0)}%, "
                f"ATS readiness {fit.get('ats_readiness', 0)}%).\n\n"
                f"- **Strong matches:** {matched}{cite}\n- **Gaps:** {missing}\n\n"
                "_Demo mode: add an LLM API key for full AI answers._"
            ),
            "tool_calls": [],
        }


@lru_cache
def get_llm() -> LLM:
    s = get_settings()
    if s.demo_mode:
        return DemoLLM()
    return OpenAICompatLLM(s.llm_api_key, s.llm_base_url, s.llm_model)
