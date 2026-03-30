"""Shared utilities: text processing, token estimation."""
from __future__ import annotations
import re

def clean_action(raw: str) -> str:
    text = raw.strip().lower()
    text = re.sub(r"^```\w*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    text = text.strip("\"'`")
    text = re.sub(r"\s+", " ", text).strip()
    return text

def estimate_tokens(text: str) -> int:
    return len(text) // 4
