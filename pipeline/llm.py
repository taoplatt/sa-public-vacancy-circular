"""Provider-agnostic LLM helper, backed by OpenRouter.

The deterministic parse fills every field; the LLM stages (``extract.py`` and
``translate.py``) only *refine* a handful, so this helper is deliberately thin
and best-effort. Both stages call :func:`chat_json` and, for the many-request
work, :func:`map_concurrent`.

Why OpenRouter
--------------
OpenRouter exposes an OpenAI-compatible ``/chat/completions`` endpoint in front
of hundreds of models, so the model is a single env var (``PSVC_MODEL``) rather
than a hard-coded provider. There is **no batch endpoint**, so the weekly run
issues ordinary synchronous requests, fanned out over a small thread pool.

Design invariants (mirrors the old Anthropic path)
--------------------------------------------------
* **Deterministic-first:** with no ``OPENROUTER_API_KEY`` the whole step is
  skipped and callers keep their deterministic values, so the site still builds.
* **Best-effort:** any failed/invalid response returns ``None``; the caller
  keeps the English/deterministic fallback. A bad model or a rate limit never
  degrades the site beyond the deterministic parse.
* **Structured output** is requested via ``response_format: json_schema``; if a
  model or provider does not support it we transparently retry without it and
  fall back to tolerant JSON extraction, since we always ask for JSON anyway.
"""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Optional, Sequence, TypeVar

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Default model. Override per-deployment with PSVC_MODEL (any OpenRouter slug,
# e.g. "anthropic/claude-haiku-4.5", "google/gemini-2.5-flash", "z-ai/glm-5.2").
DEFAULT_MODEL = "z-ai/glm-5.2"

# How many requests to keep in flight at once for the fan-out stages.
DEFAULT_CONCURRENCY = 8

T = TypeVar("T")
R = TypeVar("R")


def model_name() -> str:
    # `or` (not a get default) so an empty env var -- e.g. an unset CI repo
    # variable expanding to "" -- still falls back to the default slug.
    return os.environ.get("PSVC_MODEL", "").strip() or DEFAULT_MODEL


def concurrency() -> int:
    try:
        return max(1, int(os.environ.get("PSVC_LLM_CONCURRENCY", str(DEFAULT_CONCURRENCY))))
    except ValueError:
        return DEFAULT_CONCURRENCY


def _reasoning_config() -> dict:
    """OpenRouter ``reasoning`` param for these calls.

    Enrichment and translation are mechanical transformations -- chain-of-thought
    adds cost and latency and, worse, eats the ``max_tokens`` budget on reasoning
    models (GLM 5.2, etc.) so the actual JSON answer truncates to nothing. So we
    **disable reasoning by default**. Opt back in per-deployment with
    ``PSVC_REASONING_EFFORT=low|medium|high``. For non-reasoning models OpenRouter
    simply ignores this field.
    """
    effort = os.environ.get("PSVC_REASONING_EFFORT", "").strip().lower()
    if effort in ("low", "medium", "high"):
        return {"effort": effort}
    return {"enabled": False}


def have_credentials() -> bool:
    """True if an OpenRouter key is available (the only thing this helper needs)."""
    return bool(os.environ.get("OPENROUTER_API_KEY"))


def _headers() -> dict:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    headers = {
        "Authorization": "Bearer %s" % key,
        "Content-Type": "application/json",
    }
    # Optional attribution headers OpenRouter surfaces on its dashboard.
    referer = os.environ.get("OPENROUTER_REFERER")
    if referer:
        headers["HTTP-Referer"] = referer
    title = os.environ.get("OPENROUTER_TITLE")
    if title:
        headers["X-Title"] = title
    return headers


def _extract_json(text: str) -> Optional[dict]:
    """Best-effort parse of a JSON object from a model's text reply.

    Tolerates ```json fences and leading/trailing prose (reasoning models can
    prepend a sentence even when asked not to).
    """
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _post(body: dict, *, timeout: int, retries: int) -> Optional[dict]:
    """POST to OpenRouter with simple backoff on transient failures.

    Returns the parsed response JSON, or ``None`` after exhausting retries.
    """
    for attempt in range(retries):
        try:
            resp = requests.post(OPENROUTER_URL, headers=_headers(), json=body, timeout=timeout)
        except requests.RequestException:
            resp = None
        if resp is not None:
            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError:
                    return None
            # 400 usually means an unsupported parameter (e.g. response_format);
            # let the caller decide, don't burn retries on a deterministic error.
            if resp.status_code == 400:
                return {"_http_400": resp.text[:300]}
            # 429 / 5xx are worth retrying; anything else, give up.
            if resp.status_code not in (408, 409, 429) and resp.status_code < 500:
                return None
        # Backoff: 2s, 4s, 6s ... (bounded; best-effort, never blocks the build).
        time.sleep(2 * (attempt + 1))
    return None


def chat_json(
    system: str,
    user: str,
    schema: dict,
    *,
    model: Optional[str] = None,
    max_tokens: int = 1024,
    schema_name: str = "result",
    timeout: int = 120,
    retries: int = 3,
) -> Optional[dict]:
    """One chat completion that should return a JSON object matching ``schema``.

    Returns the parsed dict, or ``None`` on any failure (caller keeps its
    fallback). Requests structured output; if the model/provider rejects the
    ``response_format`` parameter we retry once without it and parse leniently.
    """
    model = model or model_name()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    base = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
        "reasoning": _reasoning_config(),
    }

    structured = dict(base)
    structured["response_format"] = {
        "type": "json_schema",
        "json_schema": {"name": schema_name, "strict": True, "schema": schema},
    }
    data = _post(structured, timeout=timeout, retries=retries)

    # Retry without response_format if the provider rejected it.
    if isinstance(data, dict) and "_http_400" in data:
        data = _post(base, timeout=timeout, retries=retries)
    if not isinstance(data, dict) or "_http_400" in data:
        return None

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    return _extract_json(content or "")


def chat_text(
    system: str,
    user: str,
    *,
    model: Optional[str] = None,
    max_tokens: int = 1024,
    timeout: int = 120,
    retries: int = 3,
) -> Optional[str]:
    """One chat completion returning the raw reply text (no structured output).

    Used where the expected shape is dynamic -- e.g. translating a whole UI
    catalog whose keys mirror the input. Returns ``None`` on failure.
    """
    model = model or model_name()
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "reasoning": _reasoning_config(),
    }
    data = _post(body, timeout=timeout, retries=retries)
    if not isinstance(data, dict) or "_http_400" in data:
        return None
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None


def map_concurrent(
    fn: Callable[[int, T], R],
    items: Sequence[T],
    *,
    workers: Optional[int] = None,
) -> List[Optional[R]]:
    """Run ``fn(index, item)`` over ``items`` concurrently, preserving order.

    A task that raises resolves to ``None`` in that slot; the batch never fails
    as a whole. Used by the enrich/translate fan-outs in place of the old
    Message Batches API.
    """
    workers = workers or concurrency()
    results: List[Optional[R]] = [None] * len(items)
    if not items:
        return results
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fn, i, item): i for i, item in enumerate(items)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception:  # best-effort: a single failure never sinks the run
                results[idx] = None
    return results
