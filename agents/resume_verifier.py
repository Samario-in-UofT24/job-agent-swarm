"""Resume Integrity Verifier — LangGraph Node 5. See AGENT_CONTRACT.md § Node 5."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError

__all__ = ["resume_verifier", "MAX_RESUME_REVISIONS"]

MAX_RESUME_REVISIONS = 2

T = TypeVar("T", bound=BaseModel)


class ResumeVerifierModel(BaseModel):
    review_passed: bool
    review_feedback: str | None


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_prompt(filename: str) -> str:
    return (_repo_root() / "prompts" / filename).read_text(encoding="utf-8")


def _llm() -> ChatOpenAI:
    kwargs: dict[str, Any] = {
        "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
        "temperature": float(os.getenv("LLM_TEMPERATURE", "0.2")),
    }
    key = os.getenv("OPENAI_API_KEY")
    if key:
        kwargs["api_key"] = key
    base = os.getenv("OPENAI_BASE_URL")
    if base:
        kwargs["base_url"] = base
    return ChatOpenAI(**kwargs)


def _invoke_structured(
    model_cls: type[T],
    system: str,
    human_obj: dict[str, Any],
    *,
    retries: int = 2,
) -> T:
    llm = _llm().with_structured_output(model_cls)
    human_text = json.dumps(human_obj, ensure_ascii=False, indent=2)
    messages: list[Any] = [
        SystemMessage(content=system),
        HumanMessage(
            content=(
                "Context JSON:\n"
                f"{human_text}\n\n"
                "Return only the structured object matching the schema."
            )
        ),
    ]
    repair = (
        "Your previous reply could not be parsed into the required schema. "
        "Respond again with output that satisfies the schema exactly (no markdown)."
    )
    last_err: BaseException | None = None
    for _ in range(retries + 1):
        try:
            out = llm.invoke(messages)
            if isinstance(out, model_cls):
                return out
            if isinstance(out, dict):
                return model_cls.model_validate(out)
            raise TypeError(f"unexpected structured output type: {type(out)!r}")
        except (ValidationError, TypeError, ValueError) as e:
            last_err = e
            messages.append(HumanMessage(content=f"{repair}\nParse error: {e!s}"))
        except Exception as e:
            last_err = e
            messages.append(HumanMessage(content=f"{repair}\nError: {e!s}"))
    raise RuntimeError(
        f"structured LLM output failed after {retries + 1} attempts"
    ) from last_err


def resume_verifier(state: dict[str, Any]) -> dict[str, Any]:
    """Writes review_passed, review_feedback."""
    required = ("raw_resume", "parsed_resume", "parsed_job", "customized_resume")
    missing = [k for k in required if k not in state]
    if missing:
        raise ValueError(f"missing required state keys: {missing}")

    payload = {
        "raw_resume": state["raw_resume"],
        "parsed_resume": state["parsed_resume"],
        "parsed_job": state["parsed_job"],
        "customized_resume": state["customized_resume"],
        "resume_revision_count": state.get("resume_revision_count"),
    }

    system = _load_prompt("resume_verifier_prompt.txt")
    result = _invoke_structured(ResumeVerifierModel, system, payload)
    return {
        "review_passed": result.review_passed,
        "review_feedback": result.review_feedback,
    }
