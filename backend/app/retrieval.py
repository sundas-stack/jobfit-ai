"""Vector search over chunks with pgvector (cosine distance)."""

from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Chunk, Document
from .embeddings import get_embedder


@dataclass
class Hit:
    chunk_id: int
    document_id: int
    document_title: str
    kind: str
    label: str
    text: str
    score: float  # 1.0 = identical meaning, 0 = unrelated

    def to_dict(self) -> dict:
        return asdict(self)


def search(session: Session, query: str, document_ids: list[int], k: int = 4) -> list[Hit]:
    if not query.strip() or not document_ids:
        return []
    qvec = get_embedder().embed([query])[0]
    distance = Chunk.embedding.cosine_distance(qvec)
    rows = session.execute(
        select(Chunk, Document.title, Document.kind, distance.label("distance"))
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.document_id.in_(document_ids))
        .order_by(distance)
        .limit(k)
    ).all()
    return [
        Hit(
            chunk_id=c.id,
            document_id=c.document_id,
            document_title=title,
            kind=kind,
            label=c.label,
            text=c.text,
            score=round(1 - float(dist), 3),
        )
        for c, title, kind, dist in rows
    ]
