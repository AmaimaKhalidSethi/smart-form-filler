"""
Smart Form Filler agent pipeline.

Architecture (matches the project brief):
NL Input -> Intent Classifier -> Clarification Agent (if needed) ->
Form Filler -> Pydantic Validator -> JSON Output

This module has no CLI/IO concerns baked in -- `answer_callback` is injected
so the same pipeline can run non-interactively in tests (feeding canned
answers) or interactively in the CLI (prompting a real user).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional, Type

from pydantic import BaseModel

from .clarify import build_clarifying_question, get_missing_required_fields
from .groq_client import GroqFormExtractor
from .schemas import FORM_REGISTRY

logger = logging.getLogger("smart_form_filler")

SYSTEM_PROMPT_TEMPLATE = (
    "You extract structured data from a user's natural-language description "
    "to fill out a form. Only extract information that is explicitly stated "
    "or can be directly and confidently inferred. If a piece of information "
    "is not present in the text, output null for that field rather than "
    "guessing. Do not invent values."
)

MAX_CLARIFICATION_ROUNDS = 3


@dataclass
class FillResult:
    form_type: str
    data: BaseModel
    rounds_used: int
    fully_complete: bool
    transcript: list[str] = field(default_factory=list)


def run_form_filler(
    description: str,
    form_type: Optional[str],
    extractor: GroqFormExtractor,
    answer_callback: Optional[Callable[[str], str]] = None,
) -> FillResult:
    """
    Run the full pipeline. `form_type` may be None to trigger auto-detection
    via the intent classifier. `answer_callback`, if given, is called with
    the clarifying question text and must return the user's answer as a
    string; if omitted, the loop stops after the first extraction pass and
    reports whatever is missing.
    """
    transcript: list[str] = []

    if form_type is None:
        form_type = extractor.classify_form_type(description, list(FORM_REGISTRY.keys()))
        transcript.append(f"[intent classifier] detected form_type={form_type}")
    if form_type not in FORM_REGISTRY:
        raise ValueError(f"Unknown form_type '{form_type}'. Known types: {list(FORM_REGISTRY)}")

    model_cls: Type[BaseModel] = FORM_REGISTRY[form_type]
    working_text = description
    rounds_used = 0
    instance: Optional[BaseModel] = None

    for round_num in range(MAX_CLARIFICATION_ROUNDS + 1):
        instance = extractor.extract(model_cls, SYSTEM_PROMPT_TEMPLATE, working_text)
        transcript.append(f"[round {round_num}] extracted={instance.model_dump()}")

        missing = get_missing_required_fields(model_cls, instance)
        if not missing:
            transcript.append(f"[round {round_num}] all required fields present")
            return FillResult(
                form_type=form_type,
                data=instance,
                rounds_used=rounds_used,
                fully_complete=True,
                transcript=transcript,
            )

        if round_num == MAX_CLARIFICATION_ROUNDS or answer_callback is None:
            transcript.append(f"[round {round_num}] stopping with missing fields={missing}")
            return FillResult(
                form_type=form_type,
                data=instance,
                rounds_used=rounds_used,
                fully_complete=False,
                transcript=transcript,
            )

        question = build_clarifying_question(model_cls, missing)
        transcript.append(f"[round {round_num}] clarifying question:\n{question}")
        answer = answer_callback(question)
        transcript.append(f"[round {round_num}] user answer: {answer}")
        working_text = f"{working_text}\n\nAdditional details: {answer}"
        rounds_used += 1

    # Unreachable, but keeps type checkers happy.
    assert instance is not None
    return FillResult(form_type, instance, rounds_used, False, transcript)
