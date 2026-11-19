"""AI quality check.

For each golden case we run the real pipeline and measure:
  * requirement recall : did we find the requirements a human expects?
  * status accuracy    : are the expected skills marked matched / missing correctly?

Exits with code 1 if the average drops below the threshold, so CI fails when quality regresses.

    python -m evals.run_eval              # uses whatever LLM is configured (demo mode without a key)
    python -m evals.run_eval --min 0.8
"""

import argparse
import json
import sys
from pathlib import Path

from app.analysis import compare
from app.db import Document, SessionLocal, init_db
from app.ingest import create_document
from app.llm import get_llm
from app.samples import SAMPLE_JOB, SAMPLE_RESUME

ALIASES = {"@sample_resume": SAMPLE_RESUME, "@sample_job": SAMPLE_JOB}


def _find(results: list[dict], name: str) -> dict | None:
    n = name.lower()
    return next((r for r in results if n in r["skill"].lower() or r["skill"].lower() in n), None)


def evaluate(case: dict, session) -> dict:
    resume = create_document(
        session, kind="resume", text=ALIASES.get(case["resume"], case["resume"]), title=f"eval:{case['name']}"
    )
    job = create_document(session, kind="job", text=ALIASES.get(case["job"], case["job"]), title=f"eval:{case['name']}")
    try:
        results = compare(session, resume, job)["results"]
        found = [s for s in case["expect_requirements"] if _find(results, s)]
        checks = [(s, "matched") for s in case["expect_matched"]] + [(s, "missing") for s in case["expect_missing"]]
        correct = [
            s
            for s, want in checks
            if (r := _find(results, s)) and (r["status"] == want or (want == "matched" and r["status"] == "partial"))
        ]
        return {
            "name": case["name"],
            "recall": len(found) / len(case["expect_requirements"]),
            "accuracy": len(correct) / len(checks),
            "missed_requirements": sorted(set(case["expect_requirements"]) - set(found)),
            "wrong_status": sorted({s for s, _ in checks} - set(correct)),
        }
    finally:
        for d in (resume, job):
            session.delete(session.get(Document, d.id))
        session.commit()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min", type=float, default=0.7, help="minimum average score to pass")
    args = parser.parse_args()

    init_db()
    cases = json.loads((Path(__file__).parent / "golden.json").read_text())
    session = SessionLocal()
    rows = [evaluate(c, session) for c in cases]
    session.close()

    print(f"Model: {get_llm().name}\n")
    print(f"{'case':<18}{'recall':>8}{'accuracy':>10}   notes")
    for r in rows:
        notes = ", ".join(
            filter(
                None,
                [
                    r["missed_requirements"] and f"missed {r['missed_requirements']}",
                    r["wrong_status"] and f"wrong {r['wrong_status']}",
                ],
            )
        )
        print(f"{r['name']:<18}{r['recall']:>8.0%}{r['accuracy']:>10.0%}   {notes}")
    avg = sum((r["recall"] + r["accuracy"]) / 2 for r in rows) / len(rows)
    print(f"\nOverall: {avg:.0%} (threshold {args.min:.0%})")
    return 0 if avg >= args.min else 1


if __name__ == "__main__":
    sys.exit(main())
