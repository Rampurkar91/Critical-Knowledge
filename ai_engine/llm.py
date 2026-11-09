"""Optional OpenAI-compatible LLM adapter.

Disabled unless LLM_BASE_URL, LLM_API_KEY and LLM_MODEL are configured. The
adapter receives ONLY authorised evidence already filtered by the retrieval
layer. The deterministic engine is the default and no key is required.
"""
from __future__ import annotations

from typing import Any

import httpx

from backend.app.config import settings


class LLMUnavailable(RuntimeError):
    pass


def llm_configured() -> bool:
    return bool(settings.llm_base_url and settings.llm_api_key and settings.llm_model)


def grounded_answer(question: str, evidence: list[dict[str, Any]]) -> str:
    if not llm_configured():
        raise LLMUnavailable("No LLM adapter is configured")
    context_lines = []
    for index, item in enumerate(evidence, start=1):
        context_lines.append(
            f"[{index}] source={item.get('source_ref')} claim={item.get('external_ref')} "
            f"quote={item.get('quote')}"
        )
    context = "\n".join(context_lines)
    system = (
        "Answer using only the supplied authorised evidence. If the evidence is "
        "insufficient or conflicting, say so explicitly. Do not invent facts, "
        "sources, confidence values or citations. Keep the answer under 180 words."
    )
    payload = {
        "model": settings.llm_model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Question: {question}\n\nAuthorised evidence:\n{context}"},
        ],
    }
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    try:
        response = httpx.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            timeout=20.0,
        )
        response.raise_for_status()
        data = response.json()
        return str(data["choices"][0]["message"]["content"]).strip()
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise LLMUnavailable(f"LLM request failed: {exc}") from exc
