"""JobFit AI REST API."""

import json
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .agent import run_agent
from .analysis import AnalysisError, run_analysis
from .config import get_settings
from .db import Analysis, Document, SessionLocal, get_session, init_db
from .ingest import IngestError, create_document, extract_text
from .llm import LLMError, get_llm
from .retrieval import search
from .samples import SAMPLE_JOB, SAMPLE_RESUME

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="JobFit AI", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ───────────── schemas ─────────────


class DocumentOut(BaseModel):
    id: int
    kind: str
    title: str
    filename: str | None
    chars: int
    chunks: int
    created_at: datetime


class ChunkOut(BaseModel):
    label: str
    text: str


class DocumentDetail(DocumentOut):
    text: str
    chunk_list: list[ChunkOut]


class AnalysisIn(BaseModel):
    resume_id: int
    job_id: int


class AnalysisSummary(BaseModel):
    id: int
    resume_id: int
    job_id: int
    job_title: str
    company: str
    score: int
    counts: dict
    created_at: datetime


class AnalysisOut(AnalysisSummary):
    report: dict


class SearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    document_ids: list[int]
    k: int = Field(default=5, ge=1, le=20)


class ChatTurn(BaseModel):
    role: str
    content: str


class AgentIn(BaseModel):
    resume_id: int
    job_id: int
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = []


def doc_out(d: Document) -> DocumentOut:
    return DocumentOut(
        id=d.id,
        kind=d.kind,
        title=d.title,
        filename=d.filename,
        chars=len(d.text),
        chunks=len(d.chunks),
        created_at=d.created_at,
    )


def analysis_summary(a: Analysis) -> AnalysisSummary:
    return AnalysisSummary(
        id=a.id,
        resume_id=a.resume_id,
        job_id=a.job_id,
        job_title=a.job_title,
        company=a.company,
        score=a.score,
        counts=a.report.get("counts", {}),
        created_at=a.created_at,
    )


# ───────────── routes ─────────────


@app.get("/api/health")
def health():
    s = get_settings()
    return {"status": "ok", "demo_mode": s.demo_mode, "model": get_llm().name}


@app.post("/api/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    kind: str = Form(...),
    title: str | None = Form(None),
    text: str | None = Form(None),
    file: UploadFile | None = File(None),
    session: Session = Depends(get_session),
):
    try:
        if file is not None and file.filename:
            data = await file.read()
            if len(data) > MAX_UPLOAD_BYTES:
                raise IngestError("File is too large (max 10 MB).")
            body, filename = extract_text(file.filename, data), file.filename
        elif text:
            body, filename = text, None
        else:
            raise IngestError("Upload a file or paste some text.")
        doc = create_document(session, kind=kind, text=body, title=title or None, filename=filename)
    except IngestError as exc:
        raise HTTPException(422, str(exc)) from exc
    return doc_out(doc)


@app.get("/api/documents", response_model=list[DocumentOut])
def list_documents(kind: str | None = None, session: Session = Depends(get_session)):
    q = select(Document).order_by(Document.created_at.desc())
    if kind:
        q = q.where(Document.kind == kind)
    return [doc_out(d) for d in session.scalars(q)]


@app.get("/api/documents/{doc_id}", response_model=DocumentDetail)
def get_document(doc_id: int, session: Session = Depends(get_session)):
    d = session.get(Document, doc_id)
    if not d:
        raise HTTPException(404, "Document not found")
    return DocumentDetail(
        **doc_out(d).model_dump(),
        text=d.text,
        chunk_list=[ChunkOut(label=c.label, text=c.text) for c in d.chunks],
    )


@app.delete("/api/documents/{doc_id}", status_code=204)
def delete_document(doc_id: int, session: Session = Depends(get_session)):
    d = session.get(Document, doc_id)
    if not d:
        raise HTTPException(404, "Document not found")
    for a in session.scalars(select(Analysis).where((Analysis.resume_id == doc_id) | (Analysis.job_id == doc_id))):
        session.delete(a)
    session.delete(d)
    session.commit()


@app.post("/api/samples", response_model=list[DocumentOut], status_code=201)
def load_samples(session: Session = Depends(get_session)):
    resume = create_document(session, kind="resume", text=SAMPLE_RESUME, title="Sample · Alex Morgan resume")
    job = create_document(session, kind="job", text=SAMPLE_JOB, title="Sample · Frontend Engineer, Nimbus Health")
    return [doc_out(resume), doc_out(job)]


@app.post("/api/analyses", response_model=AnalysisOut, status_code=201)
def create_analysis(body: AnalysisIn, session: Session = Depends(get_session)):
    try:
        a = run_analysis(session, body.resume_id, body.job_id)
    except AnalysisError as exc:
        raise HTTPException(422, str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(502, str(exc)) from exc
    return AnalysisOut(**analysis_summary(a).model_dump(), report=a.report)


@app.get("/api/analyses", response_model=list[AnalysisSummary])
def list_analyses(session: Session = Depends(get_session)):
    return [analysis_summary(a) for a in session.scalars(select(Analysis).order_by(Analysis.created_at.desc()))]


@app.get("/api/analyses/{analysis_id}", response_model=AnalysisOut)
def get_analysis(analysis_id: int, session: Session = Depends(get_session)):
    a = session.get(Analysis, analysis_id)
    if not a:
        raise HTTPException(404, "Analysis not found")
    return AnalysisOut(**analysis_summary(a).model_dump(), report=a.report)


@app.delete("/api/analyses/{analysis_id}", status_code=204)
def delete_analysis(analysis_id: int, session: Session = Depends(get_session)):
    a = session.get(Analysis, analysis_id)
    if not a:
        raise HTTPException(404, "Analysis not found")
    session.delete(a)
    session.commit()


@app.post("/api/search")
def search_documents(body: SearchIn, session: Session = Depends(get_session)):
    return {"results": [h.to_dict() for h in search(session, body.query, body.document_ids, body.k)]}


@app.post("/api/agent/chat")
def agent_chat(body: AgentIn):
    """Server-Sent Events: one `data: {json}` line per agent event."""

    def stream():
        session = SessionLocal()
        try:
            history = [t.model_dump() for t in body.history]
            for event in run_agent(session, body.resume_id, body.job_id, body.message, history):
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            session.close()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
