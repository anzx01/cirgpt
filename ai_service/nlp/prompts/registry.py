"""
System prompt registry. Use PROMPT_REGISTRY to look up a prompt by name,
or get_active_system_prompt() to read which one is currently active.
"""
from __future__ import annotations

import os

from nlp.prompts.v1_strict import LEGACY_V1_SYSTEM_PROMPT
from nlp.prompts.v2_freeform import FREE_FORM_V2_SYSTEM_PROMPT


PROMPT_REGISTRY = {
    "v1_strict": LEGACY_V1_SYSTEM_PROMPT,
    "v2_freeform": FREE_FORM_V2_SYSTEM_PROMPT,
}


def get_active_system_prompt() -> str:
    """Read the active system prompt from the DEEPSEEK_PROMPT_VERSION env var.

    Defaults to v2_freeform. Allowed values: v1_strict, v2_freeform.
    """
    name = os.getenv("DEEPSEEK_PROMPT_VERSION", "v2_freeform").lower().strip()
    if name not in PROMPT_REGISTRY:
        name = "v2_freeform"
    return PROMPT_REGISTRY[name]


def active_prompt_name() -> str:
    return os.getenv("DEEPSEEK_PROMPT_VERSION", "v2_freeform").lower().strip() or "v2_freeform"
