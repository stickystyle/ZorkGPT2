"""Lifecycle manager for a local llama-server (llama.cpp) subprocess."""
# ABOUTME: Context manager that starts/stops llama-server for local LLM inference.
# ABOUTME: Checks for existing server, starts with Metal GPU offload, waits for health.
from __future__ import annotations

import json
import logging
import subprocess
import time
import urllib.request
from urllib.parse import urlparse

from zorkburr.config import GameConfig

logger = logging.getLogger(__name__)

_STARTUP_TIMEOUT = 300  # seconds
_POLL_INTERVAL = 2  # seconds


class LlamaServer:
    """Context manager that owns the llama-server process for the duration of a run."""

    def __init__(self, config: GameConfig):
        self._config = config
        self._process: subprocess.Popen | None = None

    def __enter__(self) -> "LlamaServer":
        url = self._config.local_base_url.rstrip("/").removesuffix("/v1") + "/health"
        try:
            resp = urllib.request.urlopen(url, timeout=2)
            data = json.loads(resp.read())
            if data.get("status") == "ok":
                logger.info("llama-server already running — skipping subprocess start")
                self._process = None
                return self
        except Exception:
            pass

        parsed = urlparse(self._config.local_base_url)
        port = parsed.port or 8080

        cmd = [
            self._config.llama_server_path,
            "--model", self._config.local_model,
            "--port", str(port),
            "--n-gpu-layers", str(self._config.n_gpu_layers),
            "--ctx-size", str(self._config.context_size),
            "--parallel", str(self._config.n_parallel),
            "--flash-attn", "on",
        ]
        logger.info(f"Starting llama-server: model={self._config.local_model} port={port}")
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._wait_for_ready()
        logger.info("llama-server is ready")
        return self

    def __exit__(self, *args) -> None:
        if self._process is not None:
            logger.info("Stopping llama-server")
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
            self._process = None

    def _wait_for_ready(self) -> None:
        url = self._config.local_base_url.rstrip("/").removesuffix("/v1") + "/health"
        deadline = time.monotonic() + _STARTUP_TIMEOUT
        while time.monotonic() < deadline:
            if self._process is not None and self._process.poll() is not None:
                raise RuntimeError(
                    f"llama-server exited unexpectedly (returncode={self._process.returncode})"
                )
            try:
                resp = urllib.request.urlopen(url, timeout=2)
                data = json.loads(resp.read())
                if data.get("status") == "ok":
                    return
            except Exception:
                time.sleep(_POLL_INTERVAL)
        raise TimeoutError(
            f"llama-server did not respond at {url} within {_STARTUP_TIMEOUT}s"
        )
