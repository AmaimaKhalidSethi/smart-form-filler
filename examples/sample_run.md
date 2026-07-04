# Sample Run (illustrative -- against the real Groq API)

```
$ python -m smart_form_filler --form job_application \
    --text "Applying for the Data Scientist role. Skills: Python, SQL, machine learning. Looking for a fully remote position." -v

I still need a few details to complete the form:
  - full name: Applicant's full legal name
  - email: Applicant's contact email address
Please provide this information (you can answer in one sentence).
> My name is Sam Okafor, sam.okafor@mail.com

--- result ---
{
  "form_type": "job_application",
  "complete": true,
  "clarification_rounds_used": 1,
  "data": {
    "full_name": "Sam Okafor",
    "email": "sam.okafor@mail.com",
    "phone": null,
    "position_applied_for": "Data Scientist",
    "years_of_experience": null,
    "key_skills": ["Python", "SQL", "machine learning"],
    "earliest_start_date": null,
    "desired_salary_usd": null,
    "remote_preference": "remote"
  }
}
```
