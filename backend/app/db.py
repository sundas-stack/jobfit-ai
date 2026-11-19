"""Database models (Postgres + pgvector) and session helpers."""

from collections.abc import Iterator
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from .config import get_settings


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Document(Base):
    """A resume or a job ad."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), index=True)  # "resume" | "job"
    title: Mapped[str] = mapped_column(String(200))
    filename: Mapped[str | None] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="Chunk.idx"
    )


class Chunk(Base):
    """A small piece of a document with its embedding vector."""

    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(12))  # e.g. "R3" (resume) or "J2" (job)
    text: Mapped[str] = mapped_column(Text)
    embedding = mapped_column(Vector(get_settings().embedding_dim))

    document: Mapped[Document] = relationship(back_populates="chunks")


class Analysis(Base):
    """A saved fit report for one resume + one job."""

    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    job_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    job_title: Mapped[str] = mapped_column(String(200), default="")
    company: Mapped[str] = mapped_column(String(200), default="")
    score: Mapped[int] = mapped_column(Integer, default=0)
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
