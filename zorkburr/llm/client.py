"""LLM client factory using Instructor for structured output."""
# ABOUTME: Creates instructor-wrapped OpenAI clients with total request timeout.
# ABOUTME: Supports hybrid routing: per-role local/remote model selection via prefix convention.
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

import os

import httpx
import instructor

from zorkburr.config import GameConfig

logger = logging.getLogger(__name__)


def _openai_cls(use_local: bool = False):
    """Return the OpenAI class at runtime so .env/config is already loaded."""
    if not use_local and os.environ.get("LANGFUSE_PUBLIC_KEY"):
        from langfuse.openai import OpenAI
    else:
        from openai import OpenAI
    return OpenAI


# ---------------------------------------------------------------------------
# Routing helpers — prefix convention for per-role model routing
# ---------------------------------------------------------------------------

def is_remote_model(role_model: str, config: GameConfig) -> bool:
    """Check if a model routes to OpenRouter.

    Models prefixed with 'remote/' always route to OpenRouter.
    Models prefixed with 'local/' always route to local llama-server.
    Unprefixed models follow the use_local_models config flag.
    """
    if role_model.startswith("remote/"):
        return True
    if role_model.startswith("local/"):
        return False
    return not config.use_local_models


def _strip_model_prefix(model_name: str) -> str:
    """Strip local/ or remote/ routing prefix, returning the actual model identifier."""
    if model_name.startswith("remote/"):
        return model_name[7:]
    if model_name.startswith("local/"):
        return model_name[6:]
    return model_name


def _has_remote_roles(config: GameConfig) -> bool:
    """Check if any role model requires the OpenRouter client."""
    models = [
        config.agent_model, config.critic_model, config.extractor_model,
        config.objective_model, config.memory_model, config.knowledge_model,
    ]
    return any(is_remote_model(m, config) for m in models)


# ---------------------------------------------------------------------------
# Thinking / structured output helpers
# ---------------------------------------------------------------------------

def thinking_kwargs(config: GameConfig, role_model: str, use_thinking: bool) -> dict:
    """Return extra_body kwargs to control thinking/reasoning mode.

    For remote models (OpenRouter), uses the reasoning API parameter.
    For local Ministral models, returns empty dict (native reasoning_content).
    For other local models, passes chat_template_kwargs.enable_thinking via extra_body.
    """
    if is_remote_model(role_model, config):
        if use_thinking:
            return {"extra_body": {"reasoning": {"enabled": True}}}
        return {}
    # Ministral uses native reasoning_content — no chat_template control needed
    if "ministral" in (config.local_model or "").lower():
        return {}
    return {"extra_body": {"chat_template_kwargs": {"enable_thinking": use_thinking}}}


# ---------------------------------------------------------------------------
# Dual-client _TimedInstructor
# ---------------------------------------------------------------------------

class _TimedInstructor:
    """Proxy that adds a total wall-clock timeout to instructor's create() calls.

    Supports dual clients (local + remote) for hybrid model routing.
    Routes each request based on the model name's prefix convention.
    """

    def __init__(self, *, local_client: instructor.Instructor | None = None,
                 remote_client: instructor.Instructor | None = None,
                 timeout_seconds: int, config: GameConfig):
        self._local = local_client
        self._remote = remote_client
        self._timeout = timeout_seconds
        self._config = config

    def _parse_and_route(self, model_spec: str):
        """Parse model spec, select client. Returns (instructor_client, actual_model_name)."""
        actual_model = _strip_model_prefix(model_spec)
        if is_remote_model(model_spec, self._config):
            if self._remote is None:
                raise RuntimeError(
                    f"Model '{actual_model}' needs OpenRouter but no API key is configured. "
                    f"Set OPENROUTER_API_KEY in .env."
                )
            return self._remote, actual_model
        if self._local is None:
            raise RuntimeError(
                f"Model '{actual_model}' needs local server but no local client is configured."
            )
        return self._local, actual_model

    def create(self, **kwargs):
        model_spec = kwargs.get("model", "")
        client, actual_model = self._parse_and_route(model_spec)
        kwargs["model"] = actual_model
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(client.create, **kwargs)
            try:
                return future.result(timeout=self._timeout)
            except FuturesTimeout:
                self._reset_connection(model_spec)
                raise TimeoutError(
                    f"LLM request timed out after {self._timeout}s (total wall-clock)"
                )

    def raw_client_for(self, model_spec: str):
        """Return (raw_openai_client, stripped_model_name) for direct API calls."""
        client, actual_model = self._parse_and_route(model_spec)
        return client.client, actual_model

    def _reset_connection(self, model_spec: str = ""):
        """Close and recreate the underlying OpenAI client after a timeout."""
        try:
            is_remote = model_spec and is_remote_model(model_spec, self._config)
            timeout = httpx.Timeout(60.0, connect=10.0)
            if is_remote and self._remote is not None:
                self._remote.client.close()
                new_openai = _openai_cls()(
                    base_url=self._config.openrouter_base_url,
                    api_key=self._config.openrouter_api_key, timeout=timeout,
                )
                self._remote = instructor.from_openai(new_openai, mode=instructor.Mode.JSON)
            elif self._local is not None:
                self._local.client.close()
                http_client = httpx.Client(
                    timeout=timeout,
                    limits=httpx.Limits(max_keepalive_connections=0),
                )
                new_openai = _openai_cls(use_local=True)(
                    base_url=self._config.local_base_url, api_key="local",
                    http_client=http_client,
                )
                self._local = instructor.from_openai(new_openai, mode=instructor.Mode.JSON)
            logger.warning("Reset LLM client connection after timeout")
        except Exception as e:
            logger.error(f"Failed to reset LLM client: {e}")

    def __getattr__(self, name):
        return getattr(self._local or self._remote, name)


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------

def create_llm_client(config: GameConfig) -> _TimedInstructor:
    timeout = httpx.Timeout(60.0, connect=10.0)
    local_client = None
    remote_client = None

    if config.use_local_models:
        # Disable keep-alive for local models — llama-server can deadlock on
        # reused connections.  Fresh TCP connection per request avoids this.
        http_client = httpx.Client(
            timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=0),
        )
        local_client = instructor.from_openai(
            _openai_cls(use_local=True)(
                base_url=config.local_base_url, api_key="local",
                http_client=http_client,
            ),
            mode=instructor.Mode.JSON,
        )

    if not config.use_local_models or _has_remote_roles(config):
        remote_client = instructor.from_openai(
            _openai_cls()(
                base_url=config.openrouter_base_url,
                api_key=config.openrouter_api_key, timeout=timeout,
            ),
            mode=instructor.Mode.JSON,
        )

    return _TimedInstructor(
        local_client=local_client, remote_client=remote_client,
        timeout_seconds=config.llm_request_timeout, config=config,
    )
