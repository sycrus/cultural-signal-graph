"""Shared DeepSeek client and ontology CURIE helpers for the LLM stages."""

from __future__ import annotations

import os
import re

import anthropic

from .config import load_dotenv
from .models import CSG_NS, EX_NS, GAMING_NS, TECH_NS

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
