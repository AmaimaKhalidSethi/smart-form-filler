"""
Clarification-loop logic.

Deliberately template-based rather than another LLM call: the set of
missing fields is already known exactly (from the Pydantic model + the
`required_for_submission` marker), so generating the question
deterministically is faster, free, and testable -- there's nothing an LLM
call would add here except latency and non-determinism. This is the kind of
"tools vs. chains" tradeoff the Friday architecture discussion in the
syllabus asks about: use a tool call for extraction (genuinely open-ended),
skip it for a task that's really just string templating.
"""
from __future__ import annotations

from typing import Type

from pydantic import BaseModel


def get_missing_required_fields(model_cls: Type[BaseModel], instance: BaseModel) -> list[str]:
    """Return field names marked required_for_submission whose value is still None."""
    missing = []
    for name, field_info in model_cls.model_fields.items():
        extra = field_info.json_schema_extra or {}
        is_required = isinstance(extra, dict) and extra.get("required_for_submission")
        if is_required and getattr(instance, name) is None:
            missing.append(name)
    return missing


def build_clarifying_question(model_cls: Type[BaseModel], missing_fields: list[str]) -> str:
    """Combine all missing fields into one clarifying question/prompt for the user."""
    if not missing_fields:
        return ""
    lines = ["I still need a few details to complete the form:"]
    for name in missing_fields:
        description = model_cls.model_fields[name].description or name.replace("_", " ")
        lines.append(f"  - {name.replace('_', ' ')}: {description}")
    lines.append("Please provide this information (you can answer in one sentence).")
    return "\n".join(lines)
