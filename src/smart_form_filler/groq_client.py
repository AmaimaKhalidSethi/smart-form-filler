"""
Groq API wrapper for structured-output form filling.

Written for: groq==1.1.1

Key research findings baked into this file (see README for sources/date):
- llama-3.3-70b-versatile / llama-3.1-8b-instant are DEPRECATED on Groq.
  Use openai/gpt-oss-120b (or the smaller openai/gpt-oss-20b) instead.
- Strict structured outputs (response_format={"type": "json_schema", ...,
  "strict": True}) are currently only honored on the openai/gpt-oss-* models.
  Strict mode requires every property in "required" and
  "additionalProperties": false at every object level.
- The Python SDK moved to a stable v1.x line (GA Dec 2025); client
  construction and chat.completions.create() signatures used below match
  that v1 API.
"""
from __future__ import annotations

import json
import logging
import os
import random
import time
from typing import Type, TypeVar

from groq import Groq, APIConnectionError, APIStatusError, RateLimitError
from pydantic import BaseModel, ValidationError

logger = logging.getLogger("smart_form_filler")

DEFAULT_MODEL = "openai/gpt-oss-120b"

ModelT = TypeVar("ModelT", bound=BaseModel)


def build_strict_schema(model: Type[BaseModel]) -> dict:
    """
    Convert a Pydantic v2 model's JSON Schema into the shape Groq's strict
    structured-outputs mode requires: every property listed in "required"
    (nullability is expressed via type unions, not by omission) and
    "additionalProperties": false.
    """
    schema = model.model_json_schema()
    schema.pop("title", None)
    schema.pop("description", None)
    properties = schema.get("properties", {})
    for prop in properties.values():
        prop.pop("default", None)
        prop.pop("title", None)
        # app-level metadata, not a JSON Schema keyword -- strip before sending to Groq
        prop.pop("required_for_submission", None)
    schema["required"] = list(properties.keys())
    schema["additionalProperties"] = False
    return schema


class GroqFormExtractor:
    """Wraps Groq chat completions with structured outputs + retry logic."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ):
        self.client = Groq(api_key=api_key or os.environ.get("GROQ_API_KEY"))
        self.model = model
        self.max_retries = max_retries
        self.base_delay = base_delay

    def _call_with_backoff(self, **create_kwargs):
        """
        Exponential backoff with jitter. Retries on rate limits and
        transient connection/5xx errors; logs every attempt and outcome
        (Lab 2.3 requirement). Does not retry on 4xx client errors other
        than 429, since those won't succeed on retry.
        """
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info("groq_call attempt=%d model=%s", attempt, self.model)
                response = self.client.chat.completions.create(**create_kwargs)
                logger.info("groq_call attempt=%d outcome=success", attempt)
                return response
            except RateLimitError as exc:
                last_exc = exc
                delay = self.base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                logger.warning(
                    "groq_call attempt=%d outcome=rate_limited retry_in=%.2fs", attempt, delay
                )
                time.sleep(delay)
            except (APIConnectionError, APIStatusError) as exc:
                last_exc = exc
                status = getattr(exc, "status_code", None)
                if status is not None and 400 <= status < 500 and status != 429:
                    logger.error("groq_call attempt=%d outcome=client_error status=%s", attempt, status)
                    raise
                delay = self.base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                logger.warning(
                    "groq_call attempt=%d outcome=transient_error retry_in=%.2fs err=%s",
                    attempt, delay, exc,
                )
                time.sleep(delay)
        logger.error("groq_call outcome=exhausted_retries")
        raise last_exc  # type: ignore[misc]

    def extract(self, model: Type[ModelT], system_prompt: str, user_text: str) -> ModelT:
        """
        Run one structured-extraction call and validate the result against
        the Pydantic model. Raises pydantic.ValidationError if the model
        (despite strict mode) returns something invalid, e.g. a value that
        fails a field_validator.
        """
        schema = build_strict_schema(model)
        response = self._call_with_backoff(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": model.__name__,
                    "strict": True,
                    "schema": schema,
                },
            },
        )
        raw = response.choices[0].message.content
        data = json.loads(raw)
        try:
            return model.model_validate(data)
        except ValidationError:
            logger.error("extract outcome=validation_failed raw=%s", raw)
            raise

    def classify_form_type(self, user_text: str, form_names: list[str]) -> str:
        """
        Intent classification: pick which registered form type best matches
        the free-text description. Falls back to the first registered type
        if the model returns something unrecognized.
        """
        options = ", ".join(form_names)
        response = self._call_with_backoff(
            model=self.model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"Classify the user's text into exactly one of these form types: "
                        f"{options}. Reply with only the form type name, nothing else."
                    ),
                },
                {"role": "user", "content": user_text},
            ],
        )
        choice = response.choices[0].message.content.strip().lower()
        for name in form_names:
            if name in choice:
                return name
        return form_names[0]
