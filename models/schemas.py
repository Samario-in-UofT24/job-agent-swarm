from typing import TypedDict, Any


class ApplicationState(TypedDict, total=False):
    """_summary_

    Args:
        TypedDict (_type_): _description_
        total (bool, optional): _description_. Defaults to False.
        
    Each node receives the current states, and then return the update they are responsible for.
    Nodes should only WRITE the fields they own.
    """
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