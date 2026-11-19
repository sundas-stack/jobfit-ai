from app.agent import clean_answer
from app.analysis import overall_score
from app.ats import ats_report

STRONG = """Jane Doe
jane@example.com | +92 300 1234567

SUMMARY
Frontend developer with three years of React experience.

EXPERIENCE
• Built a React dashboard used by 120 staff, cutting report time by 40%.
• Led the migration of 30 pages to TypeScript in 2 months.
• Automated weekly Excel reports with Python, saving 6 hours a week.
• Reduced page load time from 4s to 1.5s by code-splitting.

EDUCATION
BS Computer Science, 2021

SKILLS
React, TypeScript, Python, Excel, Git
""" + " ".join(["Extra detail about projects and responsibilities."] * 45)

WEAK = """Jane Doe
Skills: Excel
I am hardworking and want a job."""

REQS = [
    {"skill": "React", "category": "technical"},
    {"skill": "TypeScript", "category": "technical"},
    {"skill": "Excel", "category": "tool"},
    {"skill": "Docker", "category": "tool"},
    {"skill": "Communication", "category": "soft"},
]


def test_strong_resume_scores_higher_than_weak():
    strong, weak = ats_report(STRONG, REQS), ats_report(WEAK, REQS)
    assert strong["score"] > 70 > weak["score"]


def test_keyword_check_lists_missing_terms():
    kw = next(c for c in ats_report(STRONG, REQS)["checks"] if c["id"] == "keywords")
    assert kw["missing"] == ["Docker"]
    assert "Docker" in kw["tip"]


def test_sections_and_numbers_are_detected():
    checks = {c["id"]: c for c in ats_report(STRONG, REQS)["checks"]}
    assert checks["sections"]["score"] == 100
    assert checks["achievements"]["status"] == "good"
    assert checks["verbs"]["status"] == "good"


def test_perfect_requirement_match_is_not_automatically_100():
    # every requirement matched, but a thin resume still loses points
    assert overall_score(100, ats_report(WEAK, REQS)["score"]) < 85


def test_clean_answer_fixes_model_quirks():
    raw = "You match Excel 【R4】 and SQL 【R2†L3】.<br>• Next line 【compare_skills】 [search_resume]"
    out = clean_answer(raw)
    assert "[R4]" in out and "[R2]" in out
    assert "<br>" not in out and "【" not in out and "search_resume" not in out
