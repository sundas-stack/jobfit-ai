import json

from app.agent import run_agent
from app.db import SessionLocal


def test_health_reports_demo_mode(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["demo_mode"] is True


def test_upload_text_document_creates_labelled_chunks(client):
    r = client.post("/api/documents", data={"kind": "resume", "text": "Jane Doe\n" + "Built React apps.\n" * 80})
    assert r.status_code == 201
    doc = client.get(f"/api/documents/{r.json()['id']}").json()
    assert doc["chunk_list"][0]["label"] == "R1"
    assert doc["chunks"] == len(doc["chunk_list"]) > 1


def test_upload_validation(client):
    assert client.post("/api/documents", data={"kind": "resume"}).status_code == 422
    assert client.post("/api/documents", data={"kind": "resume", "text": "too short"}).status_code == 422
    assert client.post("/api/documents", data={"kind": "cv", "text": "x" * 100}).status_code == 422


def test_search_finds_relevant_chunk(client, sample_ids):
    resume_id, _ = sample_ids
    hits = client.post("/api/search", json={"query": "Power BI report", "document_ids": [resume_id], "k": 2})
    top = hits.json()["results"][0]
    assert "Power BI" in top["text"] and top["label"].startswith("R")


def test_full_analysis_report(client, sample_ids):
    resume_id, job_id = sample_ids
    r = client.post("/api/analyses", json={"resume_id": resume_id, "job_id": job_id})
    assert r.status_code == 201, r.text
    a = r.json()
    assert 0 < a["score"] < 100
    reqs = a["report"]["requirements"]
    by_skill = {q["skill"]: q for q in reqs}
    assert by_skill["React"]["status"] == "matched"
    assert by_skill["React"]["evidence_label"].startswith("R")
    assert by_skill["Cypress"]["status"] == "missing"
    assert by_skill["Next.js"]["importance"] == "nice"
    assert a["report"]["interview_questions"] and a["report"]["bullet_rewrites"]
    # listed on the dashboard
    assert client.get("/api/analyses").json()[0]["id"] == a["id"]


def test_analysis_rejects_swapped_ids(client, sample_ids):
    resume_id, job_id = sample_ids
    assert client.post("/api/analyses", json={"resume_id": job_id, "job_id": resume_id}).status_code == 422


def test_deleting_document_removes_its_analyses(client, sample_ids):
    resume_id, job_id = sample_ids
    client.post("/api/analyses", json={"resume_id": resume_id, "job_id": job_id})
    assert client.delete(f"/api/documents/{resume_id}").status_code == 204
    assert client.get("/api/analyses").json() == []


def test_agent_streams_steps_then_answer(client, sample_ids):
    resume_id, job_id = sample_ids
    with client.stream(
        "POST",
        "/api/agent/chat",
        json={"resume_id": resume_id, "job_id": job_id, "message": "Am I a good fit?"},
    ) as r:
        events = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]
    types = [e["type"] for e in events]
    assert types[:4] == ["step", "step", "step", "step"]
    assert types[-3:] == ["sources", "answer", "done"]
    assert "fit score" in events[-2]["text"].lower()
    assert events[-3]["items"], "the answer should cite at least one source"


class LoopingLLM:
    """A model that never stops calling tools: the agent must still finish."""

    name = "looping"

    def chat(self, messages, tools):
        if not tools:
            return {"content": "Final answer.", "tool_calls": []}
        return {
            "content": None,
            "tool_calls": [{"id": "x", "name": "search_job", "arguments": {"query": "React"}}],
        }

    def json(self, task, system, payload):
        raise AssertionError("not used")


def test_agent_stops_after_max_steps(client, sample_ids):
    resume_id, job_id = sample_ids
    session = SessionLocal()
    events = list(run_agent(session, resume_id, job_id, "hi", llm=LoopingLLM()))
    session.close()
    assert sum(1 for e in events if e["type"] == "step" and e["status"] == "done") == 6
    assert events[-2] == {"type": "answer", "text": "Final answer."}
