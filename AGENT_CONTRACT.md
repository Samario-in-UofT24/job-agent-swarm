# JobSwarm Agent Contract

## Team Setup

This contract is designed for a **2-person team** working on JobSwarm with the loop-based LangGraph design.

The project uses:

- **LangGraph** for workflow orchestration
- **Qwen** as the LLM backend
- **Streamlit** for the user interface
- **SQLite** for the tracker
- **Generator–Verifier loops** for resume customization and follow-up email writing

---

# 1. Core Workflow

## Final Planned Graph

```text
parse_job
   ↓
parse_resume
   ↓
match
   ↓
customize_resume
   ↓
verify_resume
   ↓
if resume fails:
    go back to customize_resume with review_feedback
if resume passes:
    go to write_followup
   ↓
write_followup
   ↓
verify_followup
   ↓
if email fails:
    go back to write_followup with writer_feedback
if email passes:
    END
```

More compactly:

```text
parse_job → parse_resume → match → customize_resume → verify_resume
                                      ↑                  ↓
                                      └──── fail ─────────┘
                                                         pass
                                                          ↓
                                                  write_followup → verify_followup
                                                        ↑              ↓
                                                        └── fail ──────┘
                                                                       pass
                                                                        ↓
                                                                       END
```

---

# 2. Shared State

Each LangGraph node receives the current `ApplicationState`.

Each node should return **only the fields it writes**.

## `models/schemas.py`

```python
from typing import TypedDict, Any


class ApplicationState(TypedDict, total=False):
    # Raw user inputs
    raw_resume: str
    raw_job_posting: str

    # Parsed structured data
    parsed_job: dict[str, Any]
    parsed_resume: dict[str, Any]

    # Matching result
    match_result: dict[str, Any]

    # Resume customization
    customized_resume: dict[str, Any]

    # Resume verifier loop
    review_passed: bool
    review_feedback: str | None
    resume_revision_count: int

    # Follow-up email writer
    followup_email: dict[str, Any]

    # Email verifier loop
    writer_passed: bool
    writer_feedback: str | None
    email_revision_count: int

    # Error handling
    error: str | None
```

---

# 3. General Node Rule

Every node should look like this:

```python
def some_node(state: ApplicationState) -> dict:
    ...
    return {
        "some_field": some_value
    }
```

Do **not** directly mutate unrelated state fields.

Good:

```python
def parse_job_node(state: ApplicationState) -> dict:
    parsed_job = posting_parser_agent(state["raw_job_posting"])
    return {"parsed_job": parsed_job}
```

Avoid:

```python
def parse_job_node(state: ApplicationState) -> ApplicationState:
    state["parsed_job"] = parsed_job
    return state
```

---

# 4. Node Contracts

## Node 1: Job Posting Parser

### Purpose

Extract structured job information from raw job posting text.

### Reads

```text
raw_job_posting
```

### Writes

```text
parsed_job
```

### Output Shape

```json
{
  "company": "string or null",
  "role": "string or null",
  "location": "string or null",
  "employment_type": "string or null",
  "required_skills": ["string"],
  "preferred_skills": ["string"],
  "responsibilities": ["string"],
  "keywords": ["string"],
  "deadline": "string or null"
}
```

### Rules

- Do not invent missing information.
- If the company, role, or deadline is not given, use `null`.
- Return valid JSON only.

---

## Node 2: Resume Parser

### Purpose

Extract structured candidate information from raw resume text.

### Reads

```text
raw_resume
```

### Writes

```text
parsed_resume
```

### Output Shape

```json
{
  "skills": ["string"],
  "projects": [
    {
      "name": "string",
      "bullets": ["string"],
      "technologies": ["string"]
    }
  ],
  "experience": [
    {
      "title": "string",
      "company": "string",
      "bullets": ["string"],
      "technologies": ["string"]
    }
  ],
  "education": ["string"],
  "certifications": ["string"]
}
```

### Rules

- Extract only information present in the resume.
- Do not infer or invent skills.
- If a section does not exist, return an empty list.

---

## Node 3: Matcher

### Purpose

Compare the parsed resume with the parsed job posting.

### Reads

```text
parsed_job
parsed_resume
```

### Writes

```text
match_result
```

### Output Shape

```json
{
  "fit_score": 0,
  "strong_matches": ["string"],
  "weak_matches": ["string"],
  "missing_keywords": ["string"],
  "recommended_strategy": ["string"],
  "reasoning": "string"
}
```

### Rules

- `fit_score` should be an integer from 0 to 100.
- Strong matches must be supported by the parsed resume.
- Missing keywords should come from the job posting.
- The reasoning should be concise and practical.

---

## Node 4: Resume Customizer

### Purpose

Rewrite or suggest improvements to resume bullets based on the job posting and match result.

This node is the **generator** in the first generator–verifier loop.

### Reads

```text
raw_resume
parsed_resume
parsed_job
match_result
review_feedback
resume_revision_count
```

### Writes

```text
customized_resume
resume_revision_count
```

### Output Shape

```json
{
  "rewrites": [
    {
      "original": "string",
      "rewritten": "string",
      "why": "string",
      "evidence_used": ["string"]
    }
  ],
  "warnings": ["string"]
}
```

### Rules

- Do not fabricate experience.
- Do not invent companies, tools, numbers, awards, courses, or projects.
- Every rewritten bullet must be grounded in the original resume.
- If `review_feedback` exists, revise according to that feedback.
- Increment `resume_revision_count` when this node runs.

---

## Node 5: Resume Integrity Verifier

### Purpose

Check whether the customized resume contains hallucinated or unsupported claims.

This node is the **verifier** in the first generator–verifier loop.

### Reads

```text
raw_resume
parsed_resume
parsed_job
customized_resume
resume_revision_count
```

### Writes

```text
review_passed
review_feedback
```

### Output Shape

```json
{
  "review_passed": true,
  "review_feedback": "string or null"
}
```

### Pass Criteria

The resume customization passes only if:

- It does not invent skills.
- It does not invent tools.
- It does not invent companies.
- It does not invent numerical impact.
- It does not invent work experience.
- It does not contradict the original resume.
- It is relevant to the target job.

### Fail Criteria

The verifier should fail the result if:

- A rewritten bullet includes unsupported tools or technologies.
- A rewritten bullet exaggerates beyond the original resume.
- A rewritten bullet adds fake metrics.
- The customization is too generic or not useful.

### Loop Rule

If `review_passed == false` and `resume_revision_count < MAX_RESUME_REVISIONS`, the graph goes back to `customize_resume`.

If `review_passed == true`, the graph continues to `write_followup`.

If `resume_revision_count >= MAX_RESUME_REVISIONS`, the graph continues, but the UI should show the latest `review_feedback` as a warning.

Recommended value:

```python
MAX_RESUME_REVISIONS = 2
```

---

## Node 6: Follow-up Writer

### Purpose

Generate a concise follow-up email or recruiter message.

This node is the **generator** in the second generator–verifier loop.

### Reads

```text
parsed_job
parsed_resume
match_result
customized_resume
writer_feedback
email_revision_count
```

### Writes

```text
followup_email
email_revision_count
```

### Output Shape

```json
{
  "subject": "string",
  "body": "string"
}
```

### Rules

- Keep the email concise.
- Make it specific to the company and role when possible.
- Mention only skills or experience supported by the resume.
- Do not sound desperate, exaggerated, or overly casual.
- If `writer_feedback` exists, revise according to that feedback.
- Increment `email_revision_count` when this node runs.

---

## Node 7: Follow-up Email Verifier

### Purpose

Check whether the generated follow-up email is professional, specific, and grounded.

This node is the **verifier** in the second generator–verifier loop.

### Reads

```text
parsed_job
parsed_resume
match_result
customized_resume
followup_email
email_revision_count
```

### Writes

```text
writer_passed
writer_feedback
```

### Output Shape

```json
{
  "writer_passed": true,
  "writer_feedback": "string or null"
}
```

### Pass Criteria

The follow-up email passes only if:

- It is professional.
- It is concise.
- It is specific to the role.
- It does not fabricate experience.
- It does not overstate qualifications.
- It has a clear subject and body.
- It is suitable to send after human review.

### Fail Criteria

The verifier should fail the result if:

- The email is too long.
- The tone is too pushy.
- The email is too generic.
- The email claims unsupported experience.
- The subject is missing or weak.
- The body has unclear purpose.

### Loop Rule

If `writer_passed == false` and `email_revision_count < MAX_EMAIL_REVISIONS`, the graph goes back to `write_followup`.

If `writer_passed == true`, the graph ends.

If `email_revision_count >= MAX_EMAIL_REVISIONS`, the graph ends, but the UI should show the latest `writer_feedback` as a warning.

Recommended value:

```python
MAX_EMAIL_REVISIONS = 2
```

---

# 5. Suggested File Ownership for a 2-Person Team

## Person A: Agent Logic

Responsible files:

```text
agents/posting_parser.py
agents/resume_parser.py
agents/matcher.py
agents/resume_customizer.py
agents/resume_verifier.py
agents/followup_writer.py
agents/followup_verifier.py
prompts/
utils/json_parser.py
```

Main responsibility:

- Write prompts.
- Implement agent functions.
- Make sure each agent returns the agreed JSON shape.
- Test each agent individually with sample input.

## Person B: Workflow, UI, and Integration

Responsible files:

```text
models/schemas.py
utils/llm.py
graph.py
workflow.py
app.py
database/db.py
database/schema.sql
README.md
```

Main responsibility:

- Define shared state.
- Build LangGraph nodes and conditional edges.
- Connect agent functions to the graph.
- Build Streamlit UI.
- Add tracker storage.
- Prepare demo instructions.

## Shared Responsibility

Both people should review:

```text
AGENT_CONTRACT.md
sample_data/sample_resume.txt
sample_data/sample_job_posting.txt
```

These files define what the system should do.

---

# 6. Suggested Git Workflow

Use feature branches.

## Main branch

```text
main
```

Only stable code should be merged into `main`.

## Example branches

Person A:

```bash
git checkout -b agents/parser-matcher
```

Person B:

```bash
git checkout -b graph-ui-integration
```

## Basic workflow

Before starting work:

```bash
git pull origin main
```

Create branch:

```bash
git checkout -b your-branch-name
```

After making changes:

```bash
git add .
git commit -m "Short description of change"
git push origin your-branch-name
```

Then open a pull request on GitHub.

---

# 7. Minimal Integration Strategy

Do not wait until every agent is perfect.

The recommended order is:

## Stage 1: Fake Agents

Each agent returns hard-coded fake JSON in the correct format.

Goal:

```text
Make LangGraph and Streamlit work first.
```

## Stage 2: One Real Agent

Replace only `posting_parser.py` with a real LLM call.

Goal:

```text
Test LLM output and JSON parsing.
```

## Stage 3: All Real Agents

Replace the remaining fake agents one by one.

Goal:

```text
Complete real workflow.
```

## Stage 4: Add Loops

Turn on conditional edges for:

```text
customize_resume ↔ verify_resume
write_followup ↔ verify_followup
```

Goal:

```text
Show real agentic feedback loops.
```

---

# 8. Minimum Testing Requirement

Each agent file should have a small manual test block during development.

Example:

```python
if __name__ == "__main__":
    sample_input = "Paste sample text here"
    result = some_agent(sample_input)
    print(result)
```

Before merging, each person should confirm:

- The file runs without syntax errors.
- The output follows the contract.
- The node returns only the fields it writes.
- No `.env` file is committed.
- No API keys are committed.

---

# 9. Environment Variables

Use a `.env` file locally.

Example:

```env
LLM_API_KEY=EMPTY
LLM_BASE_URL=http://localhost:8000/v1
LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
```

The `.env` file must be ignored by Git.

Add this to `.gitignore`:

```text
.env
__pycache__/
*.pyc
.venv/
venv/
.DS_Store
*.sqlite
*.db
```

---

# 10. Final Demo Goal

The final demo should show:

1. Paste resume.
2. Paste job posting.
3. Click Analyze.
4. LangGraph runs parser, matcher, customizer, verifier, writer, and writer verifier.
5. Display fit score.
6. Display customized resume suggestions.
7. Display verifier feedback if any.
8. Display follow-up email.
9. Display email verifier feedback if any.
10. Save result to tracker.

---

# 11. Key Design Principle

The team should prioritize a working vertical slice:

```text
resume + job posting
    ↓
LangGraph workflow
    ↓
structured JSON outputs
    ↓
Streamlit display
```

Only after this works should the team polish prompts, database tracking, and UI styling.
