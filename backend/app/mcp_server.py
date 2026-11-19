"""MCP server: lets AI assistants (Claude Desktop, etc.) use JobFit AI as a set of tools.

It talks to the JobFit API over HTTP, so it runs as its own small container.
Run:  python -m app.mcp_server     (serves http://0.0.0.0:8001/mcp)
"""

import json
import os

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

API = os.getenv("JOBFIT_API_URL", "http://localhost:8000").rstrip("/")

mcp = MCPServer(
    name="JobFit AI",
    instructions="Tools to compare a resume with a job ad. Call list_documents first to get ids.",
)


def _client() -> httpx.Client:
    return httpx.Client(base_url=API, timeout=120)


@mcp.tool()
def list_documents(kind: str = "") -> str:
    """List saved resumes and job ads. kind can be "resume", "job" or empty for both."""
    with _client() as c:
        docs = c.get("/api/documents", params={"kind": kind} if kind else None).raise_for_status().json()
    if not docs:
        return "No documents yet. Use add_document to add a resume or a job ad."
    return "\n".join(f"#{d['id']} [{d['kind']}] {d['title']}" for d in docs)


@mcp.tool()
def add_document(kind: str, text: str, title: str = "") -> str:
    """Save a resume or a job ad from plain text. kind must be "resume" or "job". Returns its id."""
    with _client() as c:
        r = c.post("/api/documents", data={"kind": kind, "text": text, "title": title})
    if r.status_code >= 400:
        return f"Could not save: {r.json().get('detail', r.text)}"
    d = r.json()
    return f"Saved {d['kind']} #{d['id']}: {d['title']} ({d['chunks']} chunks)"


@mcp.tool()
def analyze_fit(resume_id: int, job_id: int) -> str:
    """Run a full fit analysis: score, matched and missing skills, better resume lines, interview questions."""
    with _client() as c:
        r = c.post("/api/analyses", json={"resume_id": resume_id, "job_id": job_id})
    if r.status_code >= 400:
        return f"Analysis failed: {r.json().get('detail', r.text)}"
    a = r.json()
    rep = a["report"]
    lines = [
        f"{a['job_title']} {('at ' + a['company']) if a['company'] else ''}".strip(),
        f"Fit score: {a['score']}%",
        rep.get("summary", ""),
        "",
        "Requirements:",
    ]
    for q in rep["requirements"]:
        mark = {"matched": "✔", "partial": "~", "missing": "✘"}[q["status"]]
        ev = f' [{q["evidence_label"]}] "{q["quote"]}"' if q.get("evidence_label") else ""
        lines.append(f"  {mark} {q['skill']} ({q['importance']}){ev}")
    if rep.get("ats"):
        lines += ["", "ATS checks:"] + [f"  - {c['name']}: {c['score']}%. {c['tip']}" for c in rep["ats"]["checks"]]
    if rep.get("bullet_rewrites"):
        lines += ["", "Better resume lines:"] + [f"  - {b['after']}" for b in rep["bullet_rewrites"]]
    if rep.get("interview_questions"):
        lines += ["", "Likely interview questions:"] + [f"  - {q['question']}" for q in rep["interview_questions"]]
    return "\n".join(lines)


@mcp.tool()
def search_documents(query: str, document_ids: list[int], k: int = 5) -> str:
    """Semantic search inside the given documents. Returns the closest chunks with their labels."""
    with _client() as c:
        hits = c.post("/api/search", json={"query": query, "document_ids": document_ids, "k": k}).json()["results"]
    return (
        "\n\n".join(f"[{h['label']}] ({h['document_title']}, relevance {h['score']})\n{h['text']}" for h in hits)
        or "No results."
    )


@mcp.tool()
def ask_jobfit(question: str, resume_id: int, job_id: int) -> str:
    """Ask the JobFit agent a question about a resume and a job (it searches, compares and cites sources)."""
    steps, answer, sources = [], "", []
    with (
        _client() as c,
        c.stream("POST", "/api/agent/chat", json={"resume_id": resume_id, "job_id": job_id, "message": question}) as r,
    ):
        for line in r.iter_lines():
            if not line.startswith("data: "):
                continue
            ev = json.loads(line[6:])
            if ev["type"] == "step" and ev["status"] == "done":
                steps.append(f"{ev['label']}: {ev['summary']}")
            elif ev["type"] == "sources":
                sources = [f"[{s['label']}] {s['text'][:160]}" for s in ev["items"]]
            elif ev["type"] == "answer":
                answer = ev["text"]
            elif ev["type"] == "error":
                return f"Error: {ev['message']}"
    out = [answer]
    if steps:
        out += ["", "Agent steps:"] + [f"  {i}. {s}" for i, s in enumerate(steps, 1)]
    if sources:
        out += ["", "Sources:"] + [f"  {s}" for s in sources]
    return "\n".join(out)


def main() -> None:
    mcp.run(
        transport="streamable-http",
        host=os.getenv("MCP_HOST", "0.0.0.0"),
        port=int(os.getenv("MCP_PORT", "8001")),
        # Behind Docker the Host header is "localhost:8001" or "mcp:8001"; allow both.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )


if __name__ == "__main__":
    main()
