# Smart Form Filler -- Validation Report

Mode: MOCK (offline pipeline check, not real LLM accuracy)

| Test | Form Type | Fields Match | Clarification Behaved As Expected | Result |
|------|-----------|--------------|-----------------------------------|--------|
| TC-01 | job_application | True | True | PASS |
| TC-02 | job_application | True | True | PASS |
| TC-03 | job_application | True | True | PASS |
| TC-04 | job_application | True | True | PASS |
| TC-05 | job_application | True | True | PASS |
| TC-06 | event_registration | True | True | PASS |
| TC-07 | event_registration | True | True | PASS |
| TC-08 | event_registration | True | True | PASS |
| TC-09 | event_registration | True | True | PASS |
| TC-10 | job_application | True | True | PASS |

**Score: 10/10 passed (100%)**

> Note: mock mode replays each test case's `expected` dict directly through the pipeline to validate the clarification-loop and Pydantic-validation logic. It does not exercise the real Groq model. Run without `--mock` (with `GROQ_API_KEY` set) to measure actual extraction accuracy.