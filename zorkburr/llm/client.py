"""LLM client factory using Instructor for structured output."""
# ABOUTME: Creates instructor-wrapped OpenAI clients with total request timeout.
# ABOUTME: Wraps all LLM calls in a thread-based timeout to catch streaming hangs.
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

import httpx
import instructor
from openai import OpenAI

from zorkburr.config import GameConfig

logger = logging.getLogger(__name__)

THINKING_ACTIONS = frozenset({"generate_action", "update_objectives", "update_knowledge"})


class _TimedInstructor:
    """Proxy that adds a total wall-clock timeout to instructor's create() calls.

    httpx per-operation timeouts reset with each streamed chunk, so a server that
    streams one token every 30s will never trigger a 180s read timeout.  This wrapper
    runs the call in a thread and enforces a hard wall-clock limit.
    """

    def __init__(self, client: instructor.Instructor, timeout_seconds: int):
        self._client = client
        self._timeout = timeout_seconds

    def create(self, **kwargs):
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self._client.create, **kwargs)
            try:
                return future.result(timeout=self._timeout)
            except FuturesTimeout:
                raise TimeoutError(
                    f"LLM request timed out after {self._timeout}s (total wall-clock)"
                )

    @property
    def client(self):
        """Expose the underlying OpenAI client (used by knowledge.py for raw calls)."""
        return self._client.client

    def __getattr__(self, name):
        return getattr(self._client, name)


def thinking_kwargs(config: GameConfig, use_thinking: bool) -> dict:
    """Return extra_body for Qwen3 think toggle on local runs; empty dict on OpenRouter."""
    if config.use_local_models:
        return {"extra_body": {"thinking": use_thinking}}
    return {}


def nothink_prefix(config: GameConfig, use_thinking: bool) -> str:
    """Prepend /nothink to system prompts for local Qwen3 when thinking is disabled."""
    if config.use_local_models and not use_thinking:
        return "/nothink\n\n"
    return ""


def effective_model(config: GameConfig, role_model: str) -> str:
    """Return local_model when using local inference, otherwise the role-specific model."""
    return config.local_model if config.use_local_models else role_model


def create_llm_client(config: GameConfig) -> _TimedInstructor:
    timeout = httpx.Timeout(60.0, connect=10.0)
    if config.use_local_models:
        raw = instructor.from_openai(
            OpenAI(base_url=config.local_base_url, api_key="local", timeout=timeout),
            mode=instructor.Mode.JSON,
        )
    else:
        raw = instructor.from_openai(
            OpenAI(base_url=config.openrouter_base_url, api_key=config.openrouter_api_key, timeout=timeout),
            mode=instructor.Mode.JSON,
        )
    return _TimedInstructor(raw, timeout_seconds=config.llm_request_timeout)
