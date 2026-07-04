"""
Unit tests for the agent pipeline. These deliberately do NOT call the real
Groq API (no network needed, no API key needed, fully deterministic) --
they use MockExtractor to verify the pipeline logic itself: field-level
validation, missing-required-field detection, and the clarification loop.

Run with: pytest tests/test_agent.py -v
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from smart_form_filler.agent import run_form_filler
from smart_form_filler.schemas import FORM_REGISTRY
from mock_extractor import MockExtractor

TEST_CASES = json.loads((Path(__file__).parent / "test_cases.json").read_text())


@pytest.mark.parametrize("case", TEST_CASES, ids=[c["id"] for c in TEST_CASES])
def test_case(case):
    extractor = MockExtractor(case)
    answers_given = {"count": 0}

    def answer_callback(question: str) -> str:
        answers_given["count"] += 1
        return "here are the missing details"

    result = run_form_filler(
        description=case["description"],
        form_type=case["form_type"],
        extractor=extractor,
        answer_callback=answer_callback,
    )

    model_cls = FORM_REGISTRY[case["form_type"]]
    dumped = result.data.model_dump()

    # Every expected field/value must appear in the final output.
    for key, value in case["expected"].items():
        assert dumped[key] == value, f"{case['id']}: field {key} mismatch"

    if case["expect_complete_without_clarification"]:
        assert result.rounds_used == 0, f"{case['id']}: expected no clarification rounds"
        assert result.fully_complete is True
        assert answers_given["count"] == 0
    else:
        assert result.rounds_used >= 1, f"{case['id']}: expected clarification to trigger"
        assert answers_given["count"] >= 1
        assert result.fully_complete is True  # mock always resolves by round 2

    # Result must always be a validated instance of the right model.
    assert isinstance(result.data, model_cls)
