import pytest

from app.analysis import fit_score
from app.ingest import IngestError, chunk_text, extract_text
from app.skills import find_skills, mentions


def test_chunks_keep_lines_whole():
    text = "\n".join(f"• Bullet number {i} about React and APIs" for i in range(40))
    chunks = chunk_text(text, size=200)
    assert len(chunks) > 1
    assert all(len(c) <= 260 for c in chunks)
    # no bullet is cut in half
    rebuilt = [ln for c in chunks for ln in c.split("\n")]
    assert len(rebuilt) == 40


def test_long_paragraph_is_split_on_sentences():
    para = " ".join(f"Sentence {i} talks about Python." for i in range(60))
    assert len(chunk_text(para, size=200)) > 3


def test_rejects_unknown_file_type():
    with pytest.raises(IngestError):
        extract_text("photo.png", b"\x89PNG")


def test_reads_plain_text():
    assert "React" in extract_text("cv.txt", b"Jane Doe\nFrontend developer skilled in React and TypeScript.")


def test_skill_matching_respects_word_boundaries():
    assert mentions("Java", "I write Java daily")
    assert not mentions("Java", "I write JavaScript daily")
    assert "Next.js" in find_skills("Built with nextjs and React")


@pytest.mark.parametrize(
    "statuses,expected",
    [
        ([("must", "matched"), ("nice", "missing")], 75),
        ([("must", "missing"), ("nice", "matched")], 25),
        ([("must", "partial"), ("must", "matched")], 75),
        ([("should", "missing")], 0),
    ],
)
def test_fit_score_weights_must_haves_more(statuses, expected):
    results = [{"importance": i, "status": s} for i, s in statuses]
    assert fit_score(results) == expected
