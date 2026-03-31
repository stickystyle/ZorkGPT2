"""Lifecycle manager for a local mlx_lm.server subprocess."""
from __future__ import annotations

import logging
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlparse

from zorkburr.config import GameConfig

logger = logging.getLogger(__name__)

_STARTUP_TIMEOUT = 300  # seconds
_POLL_INTERVAL = 2  # seconds


class MlxServer:
    """Context manager that owns the mlx_lm.server process for the duration of a run."""

    def __init__(self, config: GameConfig):
        self._config = config
        self._process: subprocess.Popen | None = None

    def __enter__(self) -> "MlxServer":
        url = self._config.local_base_url.rstrip("/") + "/models"
        try:
            urllib.request.urlopen(url, timeout=2)
            logger.info("mlx_lm.server already running — skipping subprocess start")
            self._process = None
            return self
        except Exception:
            pass

        port = urlparse(self._config.local_base_url).port or 8080
        logger.info(f"Starting mlx_lm.server: model={self._config.local_model} port={port}")
        self._process = subprocess.Popen(
            [sys.executable, "-m", "mlx_lm.server", "--model", self._config.local_model, "--port", str(port),
             "--prompt-cache-bytes", "4294967296"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._wait_for_ready()
        logger.info("mlx_lm.server is ready")
        return self

    def __exit__(self, *args) -> None:
        if self._process is not None:
            logger.info("Stopping mlx_lm.server")
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
            self._process = None

    def _wait_for_ready(self) -> None:
        url = self._config.local_base_url.rstrip("/") + "/models"
        deadline = time.monotonic() + _STARTUP_TIMEOUT
        while time.monotonic() < deadline:
            if self._process is not None and self._process.poll() is not None:
                raise RuntimeError(
                    f"mlx_lm.server exited unexpectedly (returncode={self._process.returncode})"
                )
            try:
                urllib.request.urlopen(url, timeout=2)
                return
            except Exception:
                time.sleep(_POLL_INTERVAL)
        raise TimeoutError(
            f"mlx_lm.server did not respond at {url} within {_STARTUP_TIMEOUT}s"
        )
