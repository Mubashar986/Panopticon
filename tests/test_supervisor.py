"""Unit and integration tests for EngineSupervisor process lifecycle management."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.core.supervisor import (
    EngineSupervisor,
    get_platform_binary_name,
    get_platform_download_asset,
)


def test_platform_binary_name_and_asset() -> None:
    """Verify platform detection returns valid binary and asset names."""
    bin_name = get_platform_binary_name()
    asset_name = get_platform_download_asset()

    assert "meilisearch" in bin_name
    assert "meilisearch" in asset_name


def test_supervisor_attach_to_existing_instance() -> None:
    """Verify supervisor attaches without spawning if Meilisearch is already healthy."""
    supervisor = EngineSupervisor()

    with patch.object(supervisor, "is_healthy", return_value=True):
        started = supervisor.start(timeout_seconds=1.0)
        assert started is True
        assert supervisor.is_managed is False
        assert supervisor.process_pid is None


def test_supervisor_spawns_process_when_offline() -> None:
    """Verify supervisor auto-spawns Meilisearch process when offline."""
    supervisor = EngineSupervisor()
    mock_process = MagicMock(spec=subprocess.Popen)
    mock_process.pid = 12345
    mock_process.poll.return_value = None

    with (
        patch.object(supervisor, "is_healthy", side_effect=[False, True]),
        patch.object(supervisor, "ensure_binary_exists", return_value=Path("bin/meilisearch.exe")),
        patch("subprocess.Popen", return_value=mock_process),
    ):
        started = supervisor.start(timeout_seconds=2.0)
        assert started is True
        assert supervisor.is_managed is True
        assert supervisor.process_pid == 12345

        # Verify stop terminates child process
        supervisor.stop(timeout_seconds=1.0)
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once()
        assert supervisor.is_managed is False


def test_supervisor_status_info() -> None:
    """Verify status dictionary structure."""
    supervisor = EngineSupervisor()
    with patch.object(supervisor, "is_healthy", return_value=True):
        status = supervisor.get_status_info()
        assert "is_running" in status
        assert "is_managed_process" in status
        assert "process_pid" in status
        assert "binary_path" in status
        assert status["is_running"] is True
