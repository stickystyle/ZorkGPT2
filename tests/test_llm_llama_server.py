import json
import subprocess
from unittest.mock import MagicMock, patch
import pytest
from zorkburr.config import GameConfig
from zorkburr.llm.llama_server import LlamaServer


def _health_ok(*args, **kwargs):
    """Mock urlopen that returns a healthy llama-server response."""
    resp = MagicMock()
    resp.read.return_value = json.dumps({"status": "ok"}).encode()
    return resp


def _health_fail(*args, **kwargs):
    raise Exception("refused")


def test_llama_server_starts_with_correct_args():
    config = GameConfig(use_local_models=True, local_model="models/test.gguf", local_base_url="http://localhost:8080/v1")
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None

    with patch("zorkburr.llm.llama_server.subprocess.Popen", return_value=mock_proc) as mock_popen, \
         patch("zorkburr.llm.llama_server.urllib.request.urlopen", side_effect=[Exception("refused"), _health_ok()]):
        with LlamaServer(config):
            mock_popen.assert_called_once()
            cmd = mock_popen.call_args[0][0]
            assert cmd[0] == "llama-server"
            assert "--model" in cmd
            assert "models/test.gguf" in cmd
            assert "--port" in cmd
            assert "8080" in cmd
            assert "--n-gpu-layers" in cmd
            assert "--ctx-size" in cmd


def test_llama_server_terminates_subprocess_on_exit():
    config = GameConfig(use_local_models=True)
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None

    with patch("zorkburr.llm.llama_server.subprocess.Popen", return_value=mock_proc), \
         patch("zorkburr.llm.llama_server.urllib.request.urlopen", side_effect=[Exception("refused"), _health_ok()]):
        with LlamaServer(config):
            pass

    mock_proc.terminate.assert_called_once()
    mock_proc.wait.assert_called_once()


def test_llama_server_terminates_on_exception():
    config = GameConfig(use_local_models=True)
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None

    with patch("zorkburr.llm.llama_server.subprocess.Popen", return_value=mock_proc), \
         patch("zorkburr.llm.llama_server.urllib.request.urlopen", side_effect=[Exception("refused"), _health_ok()]):
        with pytest.raises(RuntimeError):
            with LlamaServer(config):
                raise RuntimeError("game crashed")

    mock_proc.terminate.assert_called_once()


def test_llama_server_timeout_raises():
    config = GameConfig(use_local_models=True)
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None

    with patch("zorkburr.llm.llama_server.subprocess.Popen", return_value=mock_proc), \
         patch("zorkburr.llm.llama_server.urllib.request.urlopen", side_effect=Exception("refused")), \
         patch("zorkburr.llm.llama_server.time.sleep"), \
         patch("zorkburr.llm.llama_server.time.monotonic", side_effect=[0.0, 0.0, 999.0]):
        with pytest.raises(TimeoutError, match="llama-server"):
            with LlamaServer(config):
                pass


def test_llama_server_raises_if_process_exits_early():
    config = GameConfig(use_local_models=True)
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 1
    mock_proc.returncode = 1

    with patch("zorkburr.llm.llama_server.subprocess.Popen", return_value=mock_proc), \
         patch("zorkburr.llm.llama_server.urllib.request.urlopen", side_effect=Exception("refused")):
        with pytest.raises(RuntimeError, match="exited unexpectedly"):
            with LlamaServer(config):
                pass


def test_llama_server_kills_on_wait_timeout():
    config = GameConfig(use_local_models=True)
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.wait.side_effect = [subprocess.TimeoutExpired(cmd="llama-server", timeout=10), None]

    with patch("zorkburr.llm.llama_server.subprocess.Popen", return_value=mock_proc), \
         patch("zorkburr.llm.llama_server.urllib.request.urlopen", side_effect=[Exception("refused"), _health_ok()]):
        with LlamaServer(config):
            pass

    mock_proc.kill.assert_called_once()


def test_llama_server_skips_start_if_already_running():
    config = GameConfig(use_local_models=True)

    with patch("zorkburr.llm.llama_server.subprocess.Popen") as mock_popen, \
         patch("zorkburr.llm.llama_server.urllib.request.urlopen", return_value=_health_ok()):
        with LlamaServer(config):
            mock_popen.assert_not_called()
