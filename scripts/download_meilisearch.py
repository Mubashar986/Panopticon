"""Helper script to download official standalone Meilisearch binary for Windows."""

import os
from pathlib import Path
import urllib.request
import sys

MEILI_VERSION = "v1.12.0"
DOWNLOAD_URL = (
    f"https://github.com/meilisearch/meilisearch/releases/download/{MEILI_VERSION}/meilisearch-windows-amd64.exe"
)


def download_meilisearch() -> Path:
    bin_dir = Path("bin")
    bin_dir.mkdir(parents=True, exist_ok=True)
    target_exe = bin_dir / "meilisearch.exe"
    temp_exe = bin_dir / "meilisearch.exe.tmp"

    if target_exe.exists() and target_exe.stat().st_size > 10_000_000:
        print(f"Meilisearch binary already present ({target_exe.stat().st_size / (1024*1024):.1f} MB) at {target_exe.resolve()}")
        return target_exe

    print(f"Downloading Meilisearch {MEILI_VERSION} from {DOWNLOAD_URL}...")
    
    def reporthook(count: int, block_size: int, total_size: int) -> None:
        if total_size > 0:
            percent = int(count * block_size * 100 / total_size)
            downloaded_mb = count * block_size / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)
            sys.stdout.write(f"\rDownloading: {percent}% ({downloaded_mb:.1f}/{total_mb:.1f} MB)")
            sys.stdout.flush()

    try:
        urllib.request.urlretrieve(DOWNLOAD_URL, temp_exe, reporthook)
        print("\nDownload complete.")
        if target_exe.exists():
            target_exe.unlink()
        temp_exe.rename(target_exe)
        print(f"Meilisearch executable ready at {target_exe.resolve()}")
        return target_exe
    except Exception as e:
        if temp_exe.exists():
            temp_exe.unlink()
        raise RuntimeError(f"Failed to download Meilisearch: {e}") from e


if __name__ == "__main__":
    download_meilisearch()
