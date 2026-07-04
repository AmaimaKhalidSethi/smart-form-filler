# Smart Form Filler

Project 2-I-A from CalderR's Agentic AI Engineering Internship, Week 2
(Prompt Engineering & Tool Calling).

An AI agent that reads a natural-language description and fills out a
structured JSON form, asks clarifying questions for missing required
information, and validates the result against a Pydantic v2 schema.

```
NL Input -> Intent Classifier -> Clarification Agent (if needed)
         -> Form Filler -> Pydantic Validator -> JSON Output
```

## Research Findings (per research-before-code workflow, run 2026-07-05)

**Versions used:**
- `pydantic` 2.13.4 (current stable)
- `groq` 1.1.1 (Python SDK, stable v1.x line, GA'd Dec 2025)
- `langchain` / `langchain-groq` were evaluated but **not used** -- see
  "Why plain Groq SDK instead of LangChain" below.

**Breaking changes / deprecations to note:**
- Groq deprecated `llama-3.3-70b-versatile` and `llama-3.1-8b-instant`.
  This project defaults to `openai/gpt-oss-120b` instead.
- The Groq Python SDK reached a stable v1.0.0 in December 2025 (previously
  0.x); client construction and `chat.completions.create()` used here match
  the current v1 API, not older 0.x examples you may find online.

**Gotchas found:**
- Groq's *strict* structured-outputs mode (`response_format.json_schema.strict
  = true`) is currently only honored on `openai/gpt-oss-20b` and
  `openai/gpt-oss-120b`. On other models `strict: true` is silently ignored,
  so extraction becomes best-effort rather than guaranteed-valid JSON. This
  project pins `DEFAULT_MODEL = "openai/gpt-oss-120b"` for that reason.
- Strict mode requires **every** property to be listed under `"required"`
  in the JSON Schema -- optionality is expressed by adding `"null"` to the
  type union, not by leaving the key out of `required`. Pydantic's default
  `model_json_schema()` output doesn't do this for `Optional[x] = None`
  fields, so `groq_client.build_strict_schema()` patches the schema before
  it's sent (see that file's docstring for the specifics).
- Strict mode also requires `"additionalProperties": false` at the object
  level, which `build_strict_schema()` also adds.

### Why plain Groq SDK instead of LangChain

The Week 2 syllabus lists LangChain in the primary stack, and
`with_structured_output()` on `ChatGroq` is a real option here. This project
uses the Groq SDK directly instead, for one concrete reason: Groq's
constrained-decoding strict mode is a Groq-specific guarantee, and calling
it directly keeps that guarantee visible and controllable (model choice,
`strict: true`, schema shape) rather than behind an abstraction layer that
also has to support OpenAI/Anthropic/etc. and therefore treats structured
output as best-effort by default. For a single-provider, correctness-critical
extraction task, the extra abstraction cost of LangChain wasn't buying
anything back. (This is exactly the "tools vs. chains" question the Friday
standup template asks about.)

## Architecture

- `schemas.py` -- Pydantic v2 models for each form type, registered in
  `FORM_REGISTRY`. Fields that must be filled in before the form is
  considered submittable are marked with `required_for_submission=True`
  in `json_schema_extra` (a separate concept from JSON Schema's own
  `required`, which strict mode forces to include everything).
- `groq_client.py` -- `GroqFormExtractor`: builds the strict JSON Schema,
  calls Groq with retry/exponential backoff (rate limits + transient
  5xx/connection errors; 4xx client errors fail fast), and validates the
  response against the Pydantic model.
- `clarify.py` -- Deterministic, template-based clarifying-question
  generation from whatever fields are still `None` after extraction. No
  extra LLM call here on purpose -- see the module docstring.
- `agent.py` -- `run_form_filler()`: the actual pipeline. Runs the
  intent classifier if no form type was specified, then loops
  extract -> check missing -> ask -> re-extract, up to
  `MAX_CLARIFICATION_ROUNDS` (3).
- `cli.py` -- Interactive/non-interactive command-line entry point.

## Usage

```bash
pip install -r requirements.txt
export GROQ_API_KEY=your_key_here

# Explicit form type, one-shot text, with clarification loop
python -m smart_form_filler --form job_application \
  --text "I'm Jane Doe, jane@example.com, applying for Backend Engineer."

# Auto-detect form type, fully interactive
python -m smart_form_filler --auto-detect --interactive -v

# Single extraction pass only, no clarification loop, write to file
python -m smart_form_filler --form event_registration --no-clarify \
  --text "Register me for DevConf, VIP ticket." --out result.json
```

Exit code is `0` if the form ended up complete, `2` if it's still missing
required fields (e.g. clarification was disabled or exhausted).

## Testing & Validation

```bash
pip install -r requirements.txt
pytest tests/test_agent.py -v            # pipeline logic, no network needed

python tests/run_validation.py --mock    # regenerate validation_report.md offline
python tests/run_validation.py           # regenerate it against the real API
```

`tests/test_cases.json` holds the 10 required test cases (5 per form type),
each with an expected extraction and whether it should trigger the
clarification loop. `tests/mock_extractor.py` is a network-free stand-in
used by both the pytest suite and the `--mock` validation run -- it
replays each case's `expected` dict through the real pipeline logic
(missing-field detection, Pydantic validation, the clarification loop
itself), so CI and offline sandboxes can verify the *pipeline* is correct
without needing `GROQ_API_KEY` or network access to `api.groq.com`. It does
not measure real extraction accuracy -- run `run_validation.py` without
`--mock` for that. See `validation_report.md` for the current mock-mode
report (10/10) and `examples/sample_run.md` for an illustrative live
transcript.

## Extending with a new form type

1. Add a `BaseModel` subclass to `schemas.py`, marking business-required
   fields with `required_field()`.
2. Add it to `FORM_REGISTRY`.
3. Add a couple of test cases to `tests/test_cases.json`.

No changes needed anywhere else -- extraction, clarification, and CLI
selection are all driven off the registry.
