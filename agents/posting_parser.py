import json
from pathlib import Path
from typing import Any


PROMPT_PATH = Path("prompts/posting_parser_prompt.txt")


def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def build_posting_parser_prompt(raw_job_posting: str) -> str:
    prompt_template = load_prompt()
    return prompt_template.format(raw_job_posting=raw_job_posting)


def extract_json_from_response(response: str) -> dict[str, Any]:
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON:\n{response}") from e


def normalize_parsed_job(parsed: dict[str, Any]) -> dict[str, Any]:
    return {
        "company": parsed.get("company"),
        "role": parsed.get("role"),
        "location": parsed.get("location"),
        "employment_type": parsed.get("employment_type"),
        "required_skills": parsed.get("required_skills", []),
        "preferred_skills": parsed.get("preferred_skills", []),
        "responsibilities": parsed.get("responsibilities", []),
        "keywords": parsed.get("keywords", []),
        "deadline": parsed.get("deadline"),
    }


def fake_llm_call(prompt: str) -> str:
    # Hard coded response
    return json.dumps({
        "company": None,
        "role": "Software Engineer Intern",
        "location": "Toronto, ON",
        "employment_type": "Internship",
        "required_skills": ["Python", "Git", "Data structures"],
        "preferred_skills": ["React", "SQL"],
        "responsibilities": [
            "Build software features",
            "Collaborate with engineers"
        ],
        "keywords": [
            "Python",
            "Git",
            "software engineering",
            "data structures"
        ],
        "deadline": None,
    })


def posting_parser_agent(raw_job_posting: str) -> dict[str, Any]:
    prompt = build_posting_parser_prompt(raw_job_posting)

    # Later: 
    # response = call_llm(prompt)
    response = fake_llm_call(prompt)

    parsed = extract_json_from_response(response)
    return normalize_parsed_job(parsed)


if __name__ == "__main__":
    sample_job_posting = """
    Software Engineer Intern

    We are looking for a Software Engineer Intern in Toronto, ON.
    Required skills: Python, Git, and data structures.
    Preferred skills: React and SQL.
    """

    result = posting_parser_agent(sample_job_posting)
    print(json.dumps(result, indent=2))