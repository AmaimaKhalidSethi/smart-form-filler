"""
Form schemas for the Smart Form Filler.

Written for: pydantic 2.13.4

Design notes
------------
Every field is declared `Optional[...] = None` because Groq's strict
structured-outputs mode (json_schema, strict=True) requires *every* property
to appear in the JSON Schema's "required" list -- it cannot omit a key, it
can only fill it with `null` (see build_strict_schema() in groq_client.py).

So "required" in the JSON-Schema sense just means "the key will always be
present in the model's output." Whether a field is required for the *form to
be considered complete* is a separate, business-level concept -- that's what
`required_for_submission=True` in `json_schema_extra` marks. The clarification
agent reads that flag, not the JSON Schema's `required` list, to decide what
to ask the user about.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


def required_field(**kwargs) -> dict:
    """Marks a field as required for the form to be considered submittable."""
    extra = kwargs.pop("json_schema_extra", {})
    extra["required_for_submission"] = True
    kwargs["json_schema_extra"] = extra
    return kwargs


class JobApplicationForm(BaseModel):
    """Structured data extracted from a natural-language job application."""

    full_name: Optional[str] = Field(
        None,
        description="Applicant's full legal name",
        **required_field(),
    )
    email: Optional[str] = Field(
        None,
        description="Applicant's contact email address",
        **required_field(),
    )
    phone: Optional[str] = Field(
        None,
        description="Applicant's contact phone number, digits and standard separators only",
    )
    position_applied_for: Optional[str] = Field(
        None,
        description="Job title or position the applicant is applying for",
        **required_field(),
    )
    years_of_experience: Optional[float] = Field(
        None,
        description="Total years of relevant professional experience, as a number",
        ge=0,
    )
    key_skills: Optional[list[str]] = Field(
        None,
        description="List of key skills or technologies relevant to the position",
    )
    earliest_start_date: Optional[str] = Field(
        None,
        description="Earliest date the applicant can start, in ISO 8601 (YYYY-MM-DD) if determinable",
    )
    desired_salary_usd: Optional[float] = Field(
        None,
        description="Desired annual salary in US dollars, as a number with no currency symbol",
        ge=0,
    )
    remote_preference: Optional[Literal["remote", "hybrid", "onsite", "no_preference"]] = Field(
        None,
        description="Applicant's work-location preference",
    )

    @field_validator("email")
    @classmethod
    def _basic_email_shape(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and "@" not in v:
            raise ValueError("email must contain '@'")
        return v


class EventRegistrationForm(BaseModel):
    """Structured data extracted from a natural-language event registration."""

    full_name: Optional[str] = Field(
        None,
        description="Registrant's full name",
        **required_field(),
    )
    email: Optional[str] = Field(
        None,
        description="Registrant's contact email address",
        **required_field(),
    )
    event_name: Optional[str] = Field(
        None,
        description="Name of the event the person wants to register for",
        **required_field(),
    )
    number_of_attendees: Optional[int] = Field(
        None,
        description="Total number of people attending, including the registrant",
        ge=1,
    )
    dietary_restrictions: Optional[list[str]] = Field(
        None,
        description="List of dietary restrictions or allergies, if any were mentioned",
    )
    ticket_type: Optional[Literal["general", "vip", "student", "virtual"]] = Field(
        None,
        description="Type of ticket requested",
    )
    company_or_affiliation: Optional[str] = Field(
        None,
        description="Company, school, or organization the registrant is affiliated with",
    )

    @field_validator("email")
    @classmethod
    def _basic_email_shape(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and "@" not in v:
            raise ValueError("email must contain '@'")
        return v


# Registry pattern: add a new form type by defining a model above and
# registering it here. Nothing else in the pipeline needs to change.
FORM_REGISTRY: dict[str, type[BaseModel]] = {
    "job_application": JobApplicationForm,
    "event_registration": EventRegistrationForm,
}
