"""Shared DeepSeek client and ontology CURIE helpers for the LLM stages."""

from __future__ import annotations

import json
import os
import re

import anthropic
from opentelemetry import trace

from .config import load_dotenv
from .models import CSG_NS, EX_NS, GAMING_NS, TECH_NS, Usage
from .tracing import record_io

# Make DEEPSEEK_API_KEY (from a `.env` file) available to get_client().
load_dotenv()

DEEPSEEK_BASE_URL = "https://api.deepseek.com/anthropic"
_PREFIXES = {"csg": CSG_NS, "tech": TECH_NS, "gaming": GAMING_NS, "ex": EX_NS}


def get_client() -> anthropic.Anthropic:
    """A DeepSeek client against its Anthropic-compatible endpoint, auth from env."""
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set; cannot call a model")
    return anthropic.Anthropic(base_url=DEEPSEEK_BASE_URL, auth_token=key)


def call_model(
    model: str,
    system: str,
    prompt: str,
    max_tokens: int,
    temperature: float | None = None,
) -> tuple[str, Usage]:
    """One single-turn model call. Returns (raw text, usage), and records the full input
    and raw output on the current span so the trace shows what went in and came out."""
    kwargs = {}
    if temperature is not None:
        kwargs["temperature"] = temperature
    messages = [{"role": "user", "content": prompt}]
    response = get_client().messages.create(
        model=model,
        max_tokens=max_tokens,
        thinking={"type": "disabled"},
        system=system,
        messages=messages,
        **kwargs,
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    input_tokens = response.usage.input_tokens or 0
    output_tokens = response.usage.output_tokens or 0
    usage = Usage(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
    )
    record_io(trace.get_current_span(), json.dumps({"system": system, "messages": messages}), text)
    return text, usage


def expand_curie(curie: str) -> str:
    """Expand a CURIE (e.g. ``tech:Product``) to its full ontology IRI."""
    if ":" in curie:
        prefix, local = curie.split(":", 1)
        if prefix in _PREFIXES:
            return _PREFIXES[prefix] + local
    return curie


def extract_json(text: str) -> str:
    """Extract a JSON object/array from a model response, stripping markdown fences
    and surrounding prose."""
    text = text.strip()
    fence = re.match(r"^```[a-zA-Z]*\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    if text.startswith("{") or text.startswith("["):
        return text
    start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1)
    end = max(text.rfind("}"), text.rfind("]"))
    if start >= 0 and end >= start:
        return text[start : end + 1]
    return text
