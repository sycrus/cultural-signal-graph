"""Shared DeepSeek client and ontology CURIE helpers for the LLM stages."""

from __future__ import annotations

import os

import anthropic

from .models import CSG_NS, EX_NS, GAMING_NS, TECH_NS

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
