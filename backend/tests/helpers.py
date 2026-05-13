"""Helpers for E2E matching tests: retry loop and sample image download."""
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")


def retry_loop(
    fn: Callable[[], T],
    max_attempts: int = 3,
    delay_sec: float = 1,
) -> T:
    """Call fn(); on exception wait delay_sec and retry up to max_attempts. Raise last exception if all fail."""
    last_exc = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if attempt < max_attempts - 1:
                time.sleep(delay_sec)
    raise last_exc


# Same Pexels URLs as in scripts/download-sample-images.sh (free-to-use portraits)
SAMPLE_IMAGE_URLS = [
    ("portrait-man-1.jpeg", "https://images.pexels.com/photos/2379004/pexels-photo-2379004.jpeg?auto=compress&cs=tinysrgb&w=600"),
    ("portrait-woman-1.jpeg", "https://images.pexels.com/photos/314548/pexels-photo-314548.jpeg?auto=compress&cs=tinysrgb&w=600"),
]


def download_samples(
    dest_dir: Path,
    urls: list[tuple] = None,
    max_attempts: int = 3,
) -> list[Path]:
    """
    Download sample images into dest_dir. Each item in urls is (filename, url).
    Returns list of Paths to downloaded files. Uses retry_loop per URL.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    urls = urls or SAMPLE_IMAGE_URLS
    paths = []
    for filename, url in urls:
        path = dest_dir / filename

        def _get(_url=url, _path=path):
            urllib.request.urlretrieve(_url, _path)
            return _path

        retry_loop(_get, max_attempts=max_attempts, delay_sec=1)
        paths.append(path)
    return paths
