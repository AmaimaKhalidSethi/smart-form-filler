"""
A fake stand-in for GroqFormExtractor used in tests and offline validation
runs. It never touches the network. It duck-types the two methods
`agent.run_form_filler` actually calls (`classify_form_type`, `extract`),
so it doesn't need to subclass GroqFormExtractor at all.

Round 1 returns exactly the test case's `expected` dict (which, for cases
designed to be incomplete, will leave some Pydantic fields as None and
correctly trigger the clarification loop). Round 2+ simulates the user's
clarification answer having filled in the missing pieces, so the loop can
be exercised end-to-end without a live model.
"""
from __future__ import annotations

from typing import Type

from pydantic import BaseModel

_FILLER_VALUES = {
    "full_name": "Clarified User",
    "email": "clarified.user@example.com",
    "position_applied_for": "Unspecified Role",
    "event_name": "Unspecified Event",
}


class MockExtractor:
    def __init__(self, test_case: dict):
        self.test_case = test_case
        self.call_count = 0

    def classify_form_type(self, user_text: str, form_names: list[str]) -> str:
        return self.test_case["form_type"]

    def extract(self, model_cls: Type[BaseModel], system_prompt: str, user_text: str) -> BaseModel:
        self.call_count += 1
        data = dict(self.test_case["expected"])
        if self.call_count > 1:
            for field_name in self.test_case.get("expected_missing_fields", []):
                data.setdefault(field_name, _FILLER_VALUES.get(field_name, "N/A"))
        return model_cls(**data)
