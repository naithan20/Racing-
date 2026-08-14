"""Generic streaming-download adapter — Phase 3D.

Backs the DIRECT_DOWNLOAD, GITHUB_RELEASE, and USER_URL source-catalog
mechanisms: any legitimate data file reachable over a plain HTTP(S) GET,
without a provider-specific API contract. Deliberately generic and
provider-agnostic, unlike `racing_api.py` (which speaks one vendor's REST
contract) — this module knows nothing about racing data at all, only how to
fetch a file safely.

**Safety.** Only a fixed allowlist of data-file extensions may be
downloaded (`ALLOWED_EXTENSIONS`) — this exists specifically so a pasted
URL (the USER_URL mechanism, "Add data source from URL" in the UI) can
never be used to fetch and store an executable or script.

**Resilience.** Every retryable failure (connection error, 5xx, 429) is
retried with exponential backoff, mirroring `racing_api.py`'s
`_RacingApiHttpClient`. A partial download resumes via an HTTP Range
request when the destination file already has bytes on disk; if the server
doesn't honour the Range header (no 206 response), the download restarts
from zero rather than silently producing a truncated/corrupt file.

**Environment note.** This module makes real HTTP requests and is tested
entirely against a MOCKED `requests` module (see `test_download_adapter.py`)
— this development sandbox's network egress policy blocks most external
hosts, which is a property of THIS coding environment, not of the download
mechanism itself. Do not read "network blocked in development" as "this
feature doesn't work" — see FREE_DATA_SOURCES.md / REAL_FREE_BASELINE.md.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

# Only these extensions may ever be downloaded by this module — the
# concrete implementation of "do not download arbitrary executable files."
ALLOWED_EXTENSIONS = {
    ".csv",
    ".json",
    ".jsonl",
    ".ndjson",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".zip",
    ".gz",
    ".gzip",
}

DEFAULT_CHUNK_SIZE = 256 * 1024


class UnsupportedFileTypeError(ValueError):
    """The URL's extension isn't in `ALLOWED_EXTENSIONS`."""


class DownloadHttpError(RuntimeError):
    """Raised after retries are exhausted, or for a non-retryable HTTP status."""


@dataclass(frozen=True)
class UrlPreview:
    url: str
    hostname: str
    scheme: str
    file_extension: Optional[str]
    content_length: Optional[int]
    content_type: Optional[str]
    is_allowed_extension: bool


@dataclass(frozen=True)
class DownloadProgress:
    bytes_downloaded: int
    total_bytes: Optional[int]
    percent: Optional[float]


@dataclass(frozen=True)
class DownloadResult:
    path: Path
    bytes_downloaded: int
    sha256: str
    resumed: bool


def _extension_of(url: str) -> Optional[str]:
    path = urlparse(url).path
    name = path.rsplit("/", 1)[-1]
    if "." not in name:
        return None
    return "." + name.rsplit(".", 1)[-1].lower()


def _parse_int(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def preview_url(url: str, *, timeout: float = 15.0) -> UrlPreview:
    """A best-effort HEAD request used by the UI to show hostname/expected
    size BEFORE the user confirms a download (Phase 3D section 6). Never
    raises on a network failure — an unreachable HEAD just means the size
    and content-type stay unknown; `download_file` performs the real
    validation."""

    import requests

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Only http/https URLs are supported, got: {url!r}")

    extension = _extension_of(url)
    is_allowed = extension in ALLOWED_EXTENSIONS

    content_length: Optional[int] = None
    content_type: Optional[str] = None
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        if response.status_code < 400:
            content_length = _parse_int(response.headers.get("Content-Length"))
            content_type = response.headers.get("Content-Type")
    except requests.RequestException:
        pass

    return UrlPreview(
        url=url,
        hostname=parsed.hostname or "",
        scheme=parsed.scheme,
        file_extension=extension,
        content_length=content_length,
        content_type=content_type,
        is_allowed_extension=is_allowed,
    )


def download_file(
    url: str,
    dest_path: Path | str,
    *,
    expected_sha256: Optional[str] = None,
    max_retries: int = 5,
    backoff_base_seconds: float = 1.0,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    on_progress: Optional[Callable[[DownloadProgress], None]] = None,
    timeout: float = 30.0,
) -> DownloadResult:
    """Streams `url` to `dest_path`, resuming a partial download if
    `dest_path` already has bytes on disk. Raises `UnsupportedFileTypeError`
    before making any request if the extension isn't allowlisted.
    `expected_sha256`, if given, is verified against the FULL downloaded
    file (including any resumed bytes) — a mismatch raises rather than
    silently keeping an untrusted file."""

    import requests

    extension = _extension_of(url)
    if extension not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"Refusing to download {url!r}: extension {extension!r} is not in the allowed "
            f"data-file list {sorted(ALLOWED_EXTENSIONS)}."
        )

    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    resume_from = dest_path.stat().st_size if dest_path.exists() else 0
    resumed = resume_from > 0

    last_exception: Optional[BaseException] = None
    for attempt in range(max_retries):
        headers = {"Range": f"bytes={resume_from}-"} if resume_from > 0 else {}
        try:
            response = requests.get(url, headers=headers, stream=True, timeout=timeout)
        except requests.RequestException as exc:
            last_exception = exc
            time.sleep(backoff_base_seconds * (2**attempt))
            continue

        if response.status_code == 429 or response.status_code >= 500:
            last_exception = DownloadHttpError(f"{response.status_code} from {url}")
            time.sleep(backoff_base_seconds * (2**attempt))
            continue

        if response.status_code in (401, 403):
            raise DownloadHttpError(
                f"{response.status_code} from {url} — this source requires authentication, "
                "or access was denied."
            )
        if response.status_code == 404:
            raise DownloadHttpError(f"404 from {url} — file not found.")

        server_supports_resume = response.status_code == 206
        write_mode = "ab" if (resume_from > 0 and server_supports_resume) else "wb"
        if resume_from > 0 and not server_supports_resume:
            # Server ignored the Range header — never silently append to a
            # file that's about to receive the response from byte 0.
            resume_from = 0

        total_bytes = _parse_int(response.headers.get("Content-Length"))
        if total_bytes is not None and write_mode == "ab":
            total_bytes += resume_from

        hasher = hashlib.sha256()
        if write_mode == "ab" and dest_path.exists():
            with open(dest_path, "rb") as existing:
                for block in iter(lambda: existing.read(chunk_size), b""):
                    hasher.update(block)

        bytes_downloaded = resume_from
        try:
            with open(dest_path, write_mode) as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if not chunk:
                        continue
                    f.write(chunk)
                    hasher.update(chunk)
                    bytes_downloaded += len(chunk)
                    if on_progress is not None:
                        percent = (100.0 * bytes_downloaded / total_bytes) if total_bytes else None
                        on_progress(DownloadProgress(bytes_downloaded, total_bytes, percent))
        except requests.RequestException as exc:
            last_exception = exc
            resume_from = dest_path.stat().st_size if dest_path.exists() else 0
            time.sleep(backoff_base_seconds * (2**attempt))
            continue

        digest = hasher.hexdigest()
        if expected_sha256 is not None and digest.lower() != expected_sha256.lower():
            raise DownloadHttpError(
                f"Checksum mismatch for {url}: expected {expected_sha256}, got {digest}. "
                "The downloaded file is not trusted and was not imported."
            )

        return DownloadResult(path=dest_path, bytes_downloaded=bytes_downloaded, sha256=digest, resumed=resumed)

    raise DownloadHttpError(f"Exhausted {max_retries} retries downloading {url}") from last_exception
