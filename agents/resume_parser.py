import json
from pathlib import Path
from typing import Any


PROMPT_PATH = Path("prompts/resume_parser_prompt.txt")


def load_prompt() -> str:
    """
    Load the resume parser prompt template from the prompts folder.
    """
    return PROMPT_PATH.read_text(encoding="utf-8")


def build_resume_parser_prompt(raw_resume: str) -> str:
    """
    Insert the raw resume into the resume parser prompt template.
    """ 
    prompt_template = load_prompt()
    return prompt_template.format(raw_resume=raw_resume)


def extract_json_from_response(response: str) -> dict[str, Any]:
    """
    Parse the LLM response as JSON.

    First version assumes the model returns pure JSON.
    Later, this can be replaced with a more robust JSON extractor.
    """
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON:\n{response}") from e


def ensure_list(value: Any) -> list:
    """
    Guarantee that a field is returned as a list.
    """
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def normalize_project(project: Any) -> dict[str, Any]:
    """
    Normalize one project item to match the contract.
    """
    if not isinstance(project, dict):
        return {
            "name": "",
            "bullets": [],
            "technologies": [],
        }

    return {
        "name": project.get("name") or "",
        "bullets": ensure_list(project.get("bullets")),
        "technologies": ensure_list(project.get("technologies")),
    }


def normalize_experience(experience: Any) -> dict[str, Any]:
    """
    Normalize one experience item to match the contract.
    """
    if not isinstance(experience, dict):
        return {
            "title": "",
            "company": "",
            "bullets": [],
            "technologies": [],
        }

    return {
        "title": experience.get("title") or "",
        "company": experience.get("company") or "",
        "bullets": ensure_list(experience.get("bullets")),
        "technologies": ensure_list(experience.get("technologies")),
    }


def normalize_parsed_resume(parsed: dict[str, Any]) -> dict[str, Any]:
    """
    Make sure the parser output always follows the resume parser contract.
    """
    projects = ensure_list(parsed.get("projects"))
    experience = ensure_list(parsed.get("experience"))

    return {
        "skills": ensure_list(parsed.get("skills")),
        "projects": [normalize_project(project) for project in projects],
        "experience": [normalize_experience(item) for item in experience],
        "education": ensure_list(parsed.get("education")),
        "certifications": ensure_list(parsed.get("certifications")),
    }


def fake_llm_call(prompt: str) -> str:
    """
    Temporary fake LLM call.
    """
    return json.dumps({
        "skills": ["Python", "SQL", "Git", "Pandas"],
        "projects": [
            {
                "name": "Urban Metro Review Analysis",
                "bullets": [
                    "Analyzed urban metro review data using SQL and Python.",
                    "Created visualizations to identify passenger satisfaction patterns."
                ],
                "technologies": ["Python", "SQL", "Pandas", "Matplotlib"]
            }
        ],
        "experience": [],
        "education": [
            "Undergraduate Computer Science student, University of Toronto"
        ],
        "certifications": []
    })


def resume_parser_agent(raw_resume: str) -> dict[str, Any]:
    """
    Main resume parser function.

    Other files should call this function.
    """
    prompt = build_resume_parser_prompt(raw_resume)

    # Later replace this line with:
    # response = call_llm(prompt)
    response = fake_llm_call(prompt)

    parsed = extract_json_from_response(response)
    normalized = normalize_parsed_resume(parsed)

    return normalized


if __name__ == "__main__":
    sample_resume = """
    Samario Zhang
    Undergraduate Computer Science Student, University of Toronto

    Skills: Python, SQL, Git, Pandas, Matplotlib

    Projects:
    Urban Metro Review Analysis
    - Analyzed urban metro review data using SQL and Python.
    - Created visualizations to identify passenger satisfaction patterns.
    """

    result = resume_parser_agent(sample_resume)
    print(json.dumps(result, indent=2))