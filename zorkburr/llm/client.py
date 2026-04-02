"""LLM client factory using Instructor for structured output."""
# ABOUTME: Creates instructor-wrapped OpenAI clients with total request timeout.
# ABOUTME: Wraps all LLM calls in a thread-based timeout to catch streaming hangs.
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

import os

import httpx
import instructor

from zorkburr.config import GameConfig

logger = logging.getLogger(__name__)


def _openai_cls():
    """Return the OpenAI class at runtime so .env/config is already loaded."""
    if os.environ.get("LANGFUSE_PUBLIC_KEY"):
        from langfuse.openai import OpenAI
    else:
        from openai import OpenAI
    return OpenAI


class _TimedInstructor:
    """Proxy that adds a total wall-clock timeout to instructor's create() calls.

    httpx per-operation timeouts reset with each streamed chunk, so a server that
    streams one token every 30s will never trigger a 180s read timeout.  This wrapper
    runs the call in a thread and enforces a hard wall-clock limit.

    On timeout, closes the underlying httpx connection pool so the next request
    gets a fresh TCP connection (avoids the MLX server staying stuck on a stale one).
    """

    def __init__(self, client: instructor.Instructor, timeout_seconds: int, config: GameConfig):
        self._client = client
        self._timeout = timeout_seconds
        self._config = config

    def create(self, **kwargs):
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self._client.create, **kwargs)
            try:
                return future.result(timeout=self._timeout)
            except FuturesTimeout:
                self._reset_connection()
                raise TimeoutError(
                    f"LLM request timed out after {self._timeout}s (total wall-clock)"
                )

    def _reset_connection(self):
        """Close and recreate the underlying OpenAI client after a timeout."""
        try:
            self._client.client.close()
            timeout = httpx.Timeout(60.0, connect=10.0)
            if self._config.use_local_models:
                http_client = httpx.Client(
                    timeout=timeout,
                    limits=httpx.Limits(max_keepalive_connections=0),
                )
                new_openai = _openai_cls()(
                    base_url=self._config.local_base_url, api_key="local",
                    http_client=http_client,
                )
            else:
                new_openai = _openai_cls()(
                    base_url=self._config.openrouter_base_url,
                    api_key=self._config.openrouter_api_key, timeout=timeout,
                )
            self._client = instructor.from_openai(new_openai, mode=instructor.Mode.JSON)
            logger.warning("Reset LLM client connection after timeout")
        except Exception as e:
            logger.error(f"Failed to reset LLM client: {e}")

    @property
    def client(self):
        """Expose the underlying OpenAI client (used by knowledge.py for raw calls)."""
        return self._client.client

    def __getattr__(self, name):
        return getattr(self._client, name)


def nothink_prefix(config: GameConfig, use_thinking: bool) -> str:
    """Deprecated: use thinking_kwargs() instead for llama-server compatibility."""
    return ""


def thinking_kwargs(config: GameConfig, use_thinking: bool) -> dict:
    """Return extra_body kwargs to control thinking for local llama-server.

    For local models, passes chat_template_kwargs.enable_thinking via extra_body.
    For remote models, returns empty dict (no-op).
    """
    if config.use_local_models:
        return {"extra_body": {"chat_template_kwargs": {"enable_thinking": use_thinking}}}
    return {}


def effective_model(config: GameConfig, role_model: str) -> str:
    """Return local_model when using local inference, otherwise the role-specific model."""
    return config.local_model if config.use_local_models else role_model


def create_llm_client(config: GameConfig) -> _TimedInstructor:
    timeout = httpx.Timeout(60.0, connect=10.0)
    if config.use_local_models:
        # Disable keep-alive for local models — the MLX server can deadlock on
        # reused connections.  Fresh TCP connection per request avoids this.
        http_client = httpx.Client(
            timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=0),
        )
        raw = instructor.from_openai(
            _openai_cls()(base_url=config.local_base_url, api_key="local", http_client=http_client),
            mode=instructor.Mode.JSON,
        )
    else:
        raw = instructor.from_openai(
            _openai_cls()(base_url=config.openrouter_base_url, api_key=config.openrouter_api_key, timeout=timeout),
            mode=instructor.Mode.JSON,
        )
    return _TimedInstructor(raw, timeout_seconds=config.llm_request_timeout, config=config)
