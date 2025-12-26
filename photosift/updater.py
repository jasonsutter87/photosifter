"""Update checker for PhotoSifter."""

import json
import threading
import urllib.request
import urllib.error
from typing import Optional, Callable

from . import __version__

# Configure your GitHub repo here
GITHUB_REPO = "jasonsutter87/photosifter"
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def parse_version(version_str: str) -> tuple[int, ...]:
    """Parse version string into comparable tuple."""
    # Remove 'v' prefix if present
    version_str = version_str.lstrip("v")
    try:
        return tuple(int(x) for x in version_str.split("."))
    except ValueError:
        return (0, 0, 0)


def is_newer_version(latest: str, current: str) -> bool:
    """Check if latest version is newer than current."""
    return parse_version(latest) > parse_version(current)


def check_for_updates() -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Check GitHub for new releases.

    Returns:
        Tuple of (latest_version, download_url, release_notes) or (None, None, None) if no update
    """
    try:
        request = urllib.request.Request(
            RELEASES_URL,
            headers={"User-Agent": f"PhotoSifter/{__version__}"}
        )

        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

            latest_version = data.get("tag_name", "").lstrip("v")

            if is_newer_version(latest_version, __version__):
                # Get download URL (prefer .dmg for Mac, .exe for Windows)
                download_url = data.get("html_url", "")

                # Try to find platform-specific asset
                assets = data.get("assets", [])
                for asset in assets:
                    name = asset.get("name", "").lower()
                    if name.endswith(".dmg") or name.endswith(".exe") or name.endswith(".zip"):
                        download_url = asset.get("browser_download_url", download_url)
                        break

                release_notes = data.get("body", "")
                return latest_version, download_url, release_notes

    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, KeyError):
        pass
    except Exception:
        pass

    return None, None, None


def check_for_updates_async(callback: Callable[[Optional[str], Optional[str], Optional[str]], None]):
    """
    Check for updates in a background thread.

    Args:
        callback: Function to call with (version, url, notes) when check completes
    """
    def run_check():
        result = check_for_updates()
        callback(*result)

    thread = threading.Thread(target=run_check, daemon=True)
    thread.start()
