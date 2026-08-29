"""Subprocess supervisor and binary bootstrap for the local Meilisearch search engine."""

from __future__ import annotations

import logging
import platform
import socket
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.core.config import get_settings

logger = logging.getLogger("panopticon.core.supervisor")

MEILI_RELEASE_VERSION = "v1.12.0"


def get_platform_binary_name() -> str:
    """Return the executable name for the current OS."""
    return "meilisearch.exe" if platform.system().lower() == "windows" else "meilisearch"


def get_platform_download_asset() -> str:
    """Return the GitHub release asset filename based on current OS and architecture."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "windows":
        return "meilisearch-windows-amd64.exe"
    elif system == "darwin":
        if "arm" in machine or "aarch64" in machine:
            return "meilisearch-macos-apple-silicon"
        return "meilisearch-macos-amd64"
    elif system == "linux":
        if "arm" in machine or "aarch64" in machine:
            return "meilisearch-linux-aarch64"
        return "meilisearch-linux-amd64"
    else:
        raise OSError(f"Unsupported operating system: {system} ({machine})")


class EngineSupervisor:
    """Manages the lifecycle, auto-download, health checking, and shutdown of Meilisearch."""

    _instance: EngineSupervisor | None = None
    _singleton_lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[Any] | None = None
        self._is_managed: bool = False
        self._binary_path: Path | None = None

    @classmethod
    def get_instance(cls) -> EngineSupervisor:
        """Return the singleton instance of EngineSupervisor."""
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def is_managed(self) -> bool:
        """Return whether the running Meilisearch process is supervised by this instance."""
        with self._lock:
            return self._is_managed and self._process is not None and self._process.poll() is None

    @property
    def process_pid(self) -> int | None:
        """Return PID of the managed child process, if any."""
        with self._lock:
            if self._process and self._process.poll() is None:
                return self._process.pid
            return None

    def ensure_binary_exists(self, bin_dir: Path | None = None) -> Path:
        """Verify the Meilisearch binary exists locally, or download it from GitHub releases.

        Returns:
            Resolved Path to the executable binary.
        """
        directory = (bin_dir or Path("bin")).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        binary_name = get_platform_binary_name()
        target_binary = directory / binary_name

        if target_binary.exists() and target_binary.stat().st_size > 5_000_000:
            self._binary_path = target_binary
            return target_binary

        asset_name = get_platform_download_asset()
        download_url = f"https://github.com/meilisearch/meilisearch/releases/download/{MEILI_RELEASE_VERSION}/{asset_name}"
        temp_file = directory / f"{binary_name}.tmp"

        logger.info(
            "Meilisearch binary missing. Downloading %s from %s...",
            MEILI_RELEASE_VERSION,
            download_url,
        )

        try:
            urllib.request.urlretrieve(download_url, temp_file)
            if target_binary.exists():
                target_binary.unlink()
            temp_file.rename(target_binary)

            # Ensure executable permissions on POSIX systems
            if platform.system().lower() != "windows":
                target_binary.chmod(0o755)

            logger.info("Meilisearch binary ready at %s", target_binary)
            self._binary_path = target_binary
            return target_binary
        except Exception as exc:
            if temp_file.exists():
                temp_file.unlink()
            raise RuntimeError(
                f"Failed to auto-download Meilisearch binary: {exc}"
            ) from exc

    def is_port_listening(self, host: str, port: int, timeout: float = 0.5) -> bool:
        """Check whether a TCP socket is listening at host:port."""
        target_host = "127.0.0.1" if host in ("localhost", "0.0.0.0") else host
        try:
            with socket.create_connection((target_host, port), timeout=timeout):
                return True
        except (OSError, ConnectionRefusedError, TimeoutError):
            return False

    def is_healthy(self, host_url: str | None = None, timeout: float = 1.0) -> bool:
        """Check if Meilisearch /health responds with HTTP 200."""
        settings = get_settings()
        url = host_url or settings.MEILI_HOST
        health_url = f"{url.rstrip('/')}/health"
        try:
            req = urllib.request.Request(
                health_url,
                headers={"Authorization": f"Bearer {settings.MEILI_MASTER_KEY}"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return bool(resp.status == 200)
        except (urllib.error.URLError, OSError, TimeoutError):
            return False
        except Exception:  # noqa: BLE001
            return False

    def start(self, timeout_seconds: float = 10.0) -> bool:
        """Start the supervised Meilisearch daemon or attach to an existing instance.

        Args:
            timeout_seconds: Maximum seconds to wait for engine to become healthy.

        Returns:
            True if engine is healthy and ready.
        """
        settings = get_settings()
        parsed_url = urlparse(settings.MEILI_HOST)
        host = parsed_url.hostname or "127.0.0.1"
        port = parsed_url.port or 7700

        with self._lock:
            # 1. Check if an instance is already running
            if self.is_healthy(settings.MEILI_HOST, timeout=0.5):
                logger.info(
                    "Meilisearch is already running at %s. Attached to external instance.",
                    settings.MEILI_HOST,
                )
                self._is_managed = False
                return True

            # 2. Ensure binary exists locally
            binary_path = self.ensure_binary_exists()

            # 3. Prepare data directory
            data_dir = Path("data/meili_data").resolve()
            data_dir.mkdir(parents=True, exist_ok=True)

            # 4. Build command arguments
            cmd = [
                str(binary_path),
                "--db-path",
                str(data_dir),
                "--master-key",
                settings.MEILI_MASTER_KEY,
                "--http-addr",
                f"{host}:{port}",
            ]
            if settings.MEILI_NO_ANALYTICS:
                cmd.append("--no-analytics")

            # 5. Spawn background process
            creation_flags = 0
            if platform.system().lower() == "windows":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

            logger.info("Spawning managed Meilisearch child process on port %d...", port)
            try:
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=creation_flags,
                )
                self._is_managed = True
                logger.info("Meilisearch spawned with PID %d", self._process.pid)
            except Exception:
                logger.exception("Failed to spawn Meilisearch child process")
                return False

        # 6. Wait for health check confirmation
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if self.is_healthy(settings.MEILI_HOST, timeout=0.5):
                logger.info("Managed Meilisearch successfully initialized and healthy.")
                return True
            time.sleep(0.2)

        logger.warning(
            "Meilisearch failed to report healthy within %.1fs timeout.",
            timeout_seconds,
        )
        return False

    def stop(self, timeout_seconds: float = 5.0) -> None:
        """Gracefully shut down the managed child process."""
        with self._lock:
            if not self._is_managed or self._process is None:
                return

            pid = self._process.pid
            logger.info("Initiating graceful shutdown for Meilisearch (PID: %d)...", pid)

            try:
                if platform.system().lower() == "windows":
                    self._process.terminate()
                else:
                    self._process.terminate()

                self._process.wait(timeout=timeout_seconds)
                logger.info("Meilisearch (PID: %d) terminated cleanly.", pid)
            except subprocess.TimeoutExpired:
                logger.warning(
                    "Meilisearch (PID: %d) did not terminate within %.1fs. Sending SIGKILL...",
                    pid,
                    timeout_seconds,
                )
                self._process.kill()
                self._process.wait()
            except (OSError, subprocess.SubprocessError) as exc:
                logger.warning("Error stopping Meilisearch child process: %s", exc)
            finally:
                self._process = None
                self._is_managed = False

    def get_status_info(self) -> dict[str, Any]:
        """Return runtime status dictionary for health/diagnostics responses."""
        with self._lock:
            is_running = self.is_healthy()
            managed = self._is_managed and self._process is not None and self._process.poll() is None
            pid = self._process.pid if managed and self._process else None
            bin_path = str(self._binary_path) if self._binary_path else None

            return {
                "is_running": is_running,
                "is_managed_process": managed,
                "process_pid": pid,
                "binary_path": bin_path,
            }


def get_engine_supervisor() -> EngineSupervisor:
    """Return the global EngineSupervisor singleton."""
    return EngineSupervisor.get_instance()
