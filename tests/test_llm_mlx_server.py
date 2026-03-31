import subprocess
from unittest.mock import MagicMock, patch
import pytest
from zorkburr.config import GameConfig
from zorkburr.llm.mlx_server import MlxServer


def test_mlx_server_starts_with_correct_args():
    config = GameConfig(use_local_models=True)
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # process still running

    with patch("zorkburr.llm.mlx_server.subprocess.Popen", return_value=mock_proc) as mock_popen, \
         patch("zorkburr.llm.mlx_server.urllib.request.urlopen"):
        with MlxServer(config):
            mock_popen.assert_called_once_with(
                ["mlx_lm.server", "--model", config.local_model, "--port", "8080"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


def test_mlx_server_terminates_subprocess_on_exit():
    config = GameConfig(use_local_models=True)
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # process still running

    with patch("zorkburr.llm.mlx_server.subprocess.Popen", return_value=mock_proc), \
         patch("zorkburr.llm.mlx_server.urllib.request.urlopen"):
        with MlxServer(config):
            pass

    mock_proc.terminate.assert_called_once()
    mock_proc.wait.assert_called_once()


def test_mlx_server_terminates_on_exception():
    config = GameConfig(use_local_models=True)
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # process still running

    with patch("zorkburr.llm.mlx_server.subprocess.Popen", return_value=mock_proc), \
         patch("zorkburr.llm.mlx_server.urllib.request.urlopen"):
        with pytest.raises(RuntimeError):
            with MlxServer(config):
                raise RuntimeError("game crashed")

    mock_proc.terminate.assert_called_once()


def test_mlx_server_timeout_raises():
    config = GameConfig(use_local_models=True)
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # process still running

    with patch("zorkburr.llm.mlx_server.subprocess.Popen", return_value=mock_proc), \
         patch("zorkburr.llm.mlx_server.urllib.request.urlopen", side_effect=Exception("refused")), \
         patch("zorkburr.llm.mlx_server.time.sleep"), \
         patch("zorkburr.llm.mlx_server.time.monotonic", side_effect=[0.0, 0.0, 999.0]):
        with pytest.raises(TimeoutError, match="mlx_lm.server"):
            with MlxServer(config):
                pass


def test_mlx_server_raises_if_process_exits_early():
    config = GameConfig(use_local_models=True)
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 1  # process already exited with code 1
    mock_proc.returncode = 1

    with patch("zorkburr.llm.mlx_server.subprocess.Popen", return_value=mock_proc), \
         patch("zorkburr.llm.mlx_server.urllib.request.urlopen", side_effect=Exception("refused")):
        with pytest.raises(RuntimeError, match="exited unexpectedly"):
            with MlxServer(config):
                pass


def test_mlx_server_kills_on_wait_timeout():
    config = GameConfig(use_local_models=True)
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # process still running
    mock_proc.wait.side_effect = [subprocess.TimeoutExpired(cmd="mlx_lm.server", timeout=10), None]

    with patch("zorkburr.llm.mlx_server.subprocess.Popen", return_value=mock_proc), \
         patch("zorkburr.llm.mlx_server.urllib.request.urlopen"):
        with MlxServer(config):
            pass

    mock_proc.kill.assert_called_once()
