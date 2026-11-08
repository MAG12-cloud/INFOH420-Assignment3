"""Generate and validate paper metadata with a locally served LLM.

The local server must expose an OpenAI-compatible chat-completions endpoint.
Both Ollama and LM Studio can provide such an endpoint. Configuration is read
when the client is created, rather than at import time, so Airflow can discover
the DAG even when the LLM server is temporarily unavailable.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_API_KEY = "ollama"
DEFAULT_MAX_DOCUMENT_CHARS = 60_000
REQUIRED_FIELDS = ("title", "summary", "keywords", "category")


class MetadataValidationError(ValueError):
    """Raised when an LLM response does not match the metadata contract."""


class MetadataGenerationError(RuntimeError):
    """Raised after the LLM returns invalid metadata twice."""


def create_local_llm_client(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
):
    """Create an OpenAI client configured for the local model server.

    ``openai`` is imported lazily to keep validation and database tests usable
    without loading the full runtime dependency stack.
    """
    from openai import OpenAI

    return OpenAI(
        base_url=base_url or os.getenv("LOCAL_LLM_BASE_URL", DEFAULT_BASE_URL),
        api_key=api_key or os.getenv("LOCAL_LLM_API_KEY", DEFAULT_API_KEY),
    )


def validate_metadata(value: Any) -> Dict[str, Any]:
    """Validate and normalize the four fields required by the assignment."""
    if not isinstance(value, Mapping):
        raise MetadataValidationError("Metadata must be a JSON object")

    missing = [field for field in REQUIRED_FIELDS if field not in value]
    if missing:
        raise MetadataValidationError(
            "Missing required field(s): " + ", ".join(missing)
        )

    normalized: Dict[str, Any] = {}
    for field in ("title", "summary", "category"):
        field_value = value[field]
        if not isinstance(field_value, str) or not field_value.strip():
            raise MetadataValidationError(
                f"'{field}' must be a non-empty string"
            )
        normalized[field] = field_value.strip()

    keywords = value["keywords"]
    if not isinstance(keywords, list) or not keywords:
        raise MetadataValidationError("'keywords' must be a non-empty list")
    if any(
        not isinstance(keyword, str) or not keyword.strip()
        for keyword in keywords
    ):
        raise MetadataValidationError(
            "Every item in 'keywords' must be a non-empty string"
        )

    # Preserve order while removing case-insensitive duplicates.
    seen = set()
    normalized_keywords = []
    for keyword in keywords:
        clean_keyword = keyword.strip()
        key = clean_keyword.casefold()
        if key not in seen:
            seen.add(key)
            normalized_keywords.append(clean_keyword)
    normalized["keywords"] = normalized_keywords

    return normalized


def _json_mode_enabled() -> bool:
    value = os.getenv("LOCAL_LLM_JSON_MODE", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _build_prompt(markdown: str) -> str:
    return f"""Analyze the research paper below and return only one JSON object.

The object must use exactly this structure:
{{
  "title": "Paper title",
  "summary": "A concise summary of the paper",
  "keywords": ["keyword one", "keyword two"],
  "category": "A short academic category"
}}

All four fields are required. title, summary, and category must be non-empty
strings. keywords must be a non-empty array of non-empty strings. Do not use a
Markdown code fence and do not include commentary outside the JSON object.

PAPER MARKDOWN:
{markdown}
"""


def generate_metadata(
    markdown_path: str,
    client=None,
    model: Optional[str] = None,
    max_document_chars: Optional[int] = None,
) -> Dict[str, Any]:
    """Generate validated metadata for a Markdown paper.

    A malformed or structurally invalid response is retried exactly once, as
    required by the assignment. Transport/API errors are allowed to propagate
    so Airflow can record and retry the actual service failure.
    """
    source = Path(markdown_path).expanduser()
    if not source.is_file():
        raise FileNotFoundError(f"Markdown file not found: {source}")

    markdown = source.read_text(encoding="utf-8").strip()
    if not markdown:
        raise ValueError(f"Markdown file is empty: {source}")

    if max_document_chars is None:
        raw_limit = os.getenv(
            "LOCAL_LLM_MAX_DOCUMENT_CHARS", str(DEFAULT_MAX_DOCUMENT_CHARS)
        )
        try:
            max_document_chars = int(raw_limit)
        except ValueError as error:
            raise ValueError(
                "LOCAL_LLM_MAX_DOCUMENT_CHARS must be an integer"
            ) from error

    if max_document_chars <= 0:
        raise ValueError("max_document_chars must be greater than zero")

    if len(markdown) > max_document_chars:
        markdown = markdown[:max_document_chars]

    selected_model = model or os.getenv("LOCAL_LLM_MODEL")
    if not selected_model:
        raise ValueError("LOCAL_LLM_MODEL is not configured")

    llm_client = client or create_local_llm_client()
    request = {
        "model": selected_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You extract structured metadata from academic papers. "
                    "Return valid JSON only."
                ),
            },
            {"role": "user", "content": _build_prompt(markdown)},
        ],
        "temperature": 0,
    }
    if _json_mode_enabled():
        request["response_format"] = {"type": "json_object"}

    last_error: Optional[Exception] = None
    for _attempt in range(2):
        response = llm_client.chat.completions.create(**request)
        content = response.choices[0].message.content

        try:
            if not isinstance(content, str) or not content.strip():
                raise MetadataValidationError("LLM returned an empty response")
            return validate_metadata(json.loads(content))
        except (json.JSONDecodeError, MetadataValidationError) as error:
            last_error = error

    raise MetadataGenerationError(
        "The local LLM returned invalid metadata on both attempts"
    ) from last_error
