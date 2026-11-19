"""ATS readiness: the checks applicant-tracking systems and recruiters' first scan really apply.

All rules, no AI, so the result is the same every time and each point can be explained:
  * keywords      : do the job's key terms appear word-for-word in the resume? (ATS filters match text)
  * sections      : contact details, summary, experience, education, skills
  * achievements  : do bullet points show results with numbers?
  * action verbs  : do bullet points start with strong verbs?
  * length        : not too short, not too long
"""

import re

from .skills import PATTERNS, mentions

WEIGHTS = {"keywords": 40, "sections": 20, "achievements": 20, "verbs": 10, "length": 10}

SECTION_PATTERNS = {
    "Contact details": None,  # checked with email / phone patterns
    "Summary": r"summary|profile|objective|about me",
    "Experience": r"experience|employment|work history|internship",
    "Education": r"education|academic|qualification|degree|university|college",
    "Skills": r"skills|technologies|tools|competencies",
}

VERBS = {
    "built",
    "developed",
    "designed",
    "led",
    "created",
    "delivered",
    "implemented",
    "improved",
    "reduced",
    "increased",
    "automated",
    "managed",
    "launched",
    "optimised",
    "optimized",
    "analysed",
    "analyzed",
    "engineered",
    "integrated",
    "migrated",
    "organised",
    "organized",
    "coordinated",
    "trained",
    "wrote",
    "maintained",
    "handled",
    "processed",
    "prepared",
    "achieved",
    "streamlined",
    "deployed",
    "tested",
    "collaborated",
    "presented",
    "established",
    "resolved",
    "supported",
    "conducted",
    "entered",
    "verified",
}

BULLET = re.compile(r"^\s*(?:[•●▪◦\-–*]|\d+[.)])\s*")
NUMBER = re.compile(r"\d|%|\bone\b|\btwo\b|\bthree\b|\bfive\b|\bten\b|\bhundred|\bthousand")


def _status(score: int) -> str:
    return "good" if score >= 75 else "ok" if score >= 45 else "poor"


def _bullets(text: str) -> list[str]:
    lines = [ln.strip() for ln in text.split("\n")]
    bullets = [BULLET.sub("", ln) for ln in lines if BULLET.match(ln) and len(ln) > 25]
    if len(bullets) < 3:  # resumes without bullet symbols: use longer sentence-like lines instead
        bullets = [ln for ln in lines if len(ln.split()) >= 7]
    return bullets


def _keyword_in(term: str, text: str) -> bool:
    if term in PATTERNS:
        return mentions(term, text)
    words = [w for w in re.findall(r"[a-z0-9+#./]+", term.lower()) if len(w) > 2]
    low = text.lower()
    return bool(words) and all(w in low for w in words)


def check_keywords(resume: str, requirements: list[dict]) -> dict:
    terms = [r["skill"] for r in requirements if r.get("category") not in ("soft", "education", "experience")]
    terms = terms or [r["skill"] for r in requirements]
    found = [t for t in terms if _keyword_in(t, resume)]
    missing = [t for t in terms if t not in found]
    score = round(100 * len(found) / len(terms)) if terms else 0
    tip = (
        f"Add these exact words where they are true for you: {', '.join(missing[:6])}."
        if missing
        else "Every key term from the ad appears in your resume."
    )
    return {
        "id": "keywords",
        "name": "Job keywords in your resume",
        "score": score,
        "detail": f"{len(found)} of {len(terms)} key terms appear word-for-word.",
        "tip": tip,
        "missing": missing,
    }


def check_sections(resume: str) -> dict:
    low = resume.lower()
    present, absent = [], []
    for name, pat in SECTION_PATTERNS.items():
        ok = (
            bool(re.search(r"[\w.+-]+@[\w-]+\.\w+", resume) or re.search(r"\+?\d[\d\s-]{8,}\d", resume))
            if pat is None
            else bool(re.search(rf"(?m)^\W*({pat})\b", low)) or (name == "Education" and re.search(pat, low))
        )
        (present if ok else absent).append(name)
    score = round(100 * len(present) / len(SECTION_PATTERNS))
    tip = f"Add a clear '{absent[0]}' heading." if absent else "All the standard sections are there."
    return {
        "id": "sections",
        "name": "Standard sections",
        "score": score,
        "detail": f"Found: {', '.join(present) or 'none'}.",
        "tip": tip,
    }


def check_achievements(resume: str) -> dict:
    bullets = _bullets(resume)
    with_numbers = [b for b in bullets if NUMBER.search(b.lower())]
    ratio = len(with_numbers) / len(bullets) if bullets else 0
    score = min(100, round(ratio / 0.4 * 100))  # 40% of bullets with a number counts as full marks
    return {
        "id": "achievements",
        "name": "Results with numbers",
        "score": score,
        "detail": f"{len(with_numbers)} of {len(bullets)} experience lines include a number or result.",
        "tip": "Add numbers where you can: how many, how much, how fast, how often."
        if score < 75
        else "Good use of measurable results.",
    }


def check_verbs(resume: str) -> dict:
    bullets = _bullets(resume)
    strong = [b for b in bullets if b.split() and b.split()[0].lower().strip(",.:") in VERBS]
    ratio = len(strong) / len(bullets) if bullets else 0
    score = min(100, round(ratio / 0.6 * 100))
    return {
        "id": "verbs",
        "name": "Lines start with action verbs",
        "score": score,
        "detail": f"{len(strong)} of {len(bullets)} lines start with a strong verb.",
        "tip": "Start each line with a verb such as Built, Led, Reduced or Automated."
        if score < 75
        else "Lines lead with action.",
    }


def check_length(resume: str) -> dict:
    words = len(resume.split())
    if 350 <= words <= 900:
        score, tip = 100, "A good length for one to two pages."
    elif words < 350:
        score, tip = (
            max(20, round(words / 350 * 100)),
            "Your resume is short. Add detail to your experience and projects.",
        )
    else:
        score, tip = max(40, round(100 - (words - 900) / 15)), "Your resume is long. Cut older or less relevant lines."
    return {"id": "length", "name": "Length", "score": score, "detail": f"About {words} words.", "tip": tip}


def ats_report(resume: str, requirements: list[dict]) -> dict:
    checks = [
        check_keywords(resume, requirements),
        check_sections(resume),
        check_achievements(resume),
        check_verbs(resume),
        check_length(resume),
    ]
    for c in checks:
        c["status"] = _status(c["score"])
    score = round(sum(WEIGHTS[c["id"]] * c["score"] for c in checks) / sum(WEIGHTS.values()))
    return {"score": score, "checks": checks}
