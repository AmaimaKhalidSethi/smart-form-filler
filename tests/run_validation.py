"""
Runs all 10 test cases and produces validation_report.md.

By default this uses the real Groq API (requires GROQ_API_KEY + network
access to api.groq.com). Pass --mock to run against MockExtractor instead
-- useful for CI environments or sandboxes without network access to Groq;
it validates the *pipeline* (schema building, missing-field detection,
clarification loop, Pydantic validation) but does not measure real
extraction accuracy.

Usage:
    python tests/run_validation.py             # live, needs GROQ_API_KEY
    python tests/run_validation.py --mock       # offline pipeline check
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from smart_form_filler.agent import run_form_filler
from smart_form_filler.groq_client import GroqFormExtractor
from mock_extractor import MockExtractor

TEST_CASES = json.loads((Path(__file__).parent / "test_cases.json").read_text())


def run(mock: bool) -> str:
    lines = ["# Smart Form Filler -- Validation Report", ""]
    lines.append(f"Mode: {'MOCK (offline pipeline check, not real LLM accuracy)' if mock else 'LIVE (real Groq API)'}")
    lines.append("")
    lines.append("| Test | Form Type | Fields Match | Clarification Behaved As Expected | Result |")
    lines.append("|------|-----------|--------------|-----------------------------------|--------|")

    passed = 0
    for case in TEST_CASES:
        extractor = MockExtractor(case) if mock else GroqFormExtractor()

        def answer_callback(_q: str) -> str:
            return "here are the missing details"

        try:
            result = run_form_filler(
                description=case["description"],
                form_type=case["form_type"],
                extractor=extractor,
                answer_callback=answer_callback,
            )
            dumped = result.data.model_dump()
            fields_match = all(dumped.get(k) == v for k, v in case["expected"].items())
            expected_rounds_gt_zero = not case["expect_complete_without_clarification"]
            clarify_ok = (result.rounds_used > 0) == expected_rounds_gt_zero
            ok = fields_match and clarify_ok
        except Exception as exc:  # noqa: BLE001
            fields_match, clarify_ok, ok = False, False, False
            result = None
            error = str(exc)
        else:
            error = None

        if ok:
            passed += 1
        status = "PASS" if ok else "FAIL"
        lines.append(
            f"| {case['id']} | {case['form_type']} | {fields_match} | {clarify_ok} | {status} |"
        )
        if error:
            lines.append(f"|  |  |  |  | error: {error} |")

    total = len(TEST_CASES)
    lines.append("")
    lines.append(f"**Score: {passed}/{total} passed ({passed / total:.0%})**")
    if mock:
        lines.append("")
        lines.append(
            "> Note: mock mode replays each test case's `expected` dict directly through "
            "the pipeline to validate the clarification-loop and Pydantic-validation logic. "
            "It does not exercise the real Groq model. Run without `--mock` (with "
            "`GROQ_API_KEY` set) to measure actual extraction accuracy."
        )
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--out", default=str(Path(__file__).parent.parent / "validation_report.md"))
    args = parser.parse_args()

    report = run(mock=args.mock)
    Path(args.out).write_text(report)
    print(report)
