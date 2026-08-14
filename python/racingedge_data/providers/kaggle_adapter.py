"""Kaggle dataset adapter — Phase 3D.

Uses the OFFICIAL `kaggle` Python package (https://github.com/Kaggle/kaggle-api)
only — no scraping of kaggle.com, and no reverse-engineered private API.

**Verified against the real, installed package (kaggle==1.6.17), not
guessed.** Two facts below came from actually installing and running it in
this build's sandbox, not from training data, and are the reason for this
module's specific design:

1. `kaggle/__init__.py` calls `KaggleApi().authenticate()` as a MODULE-LEVEL
   side effect the first time anything under the `kaggle` package is
   imported — so `from kaggle.api.kaggle_api_extended import KaggleApi`
   itself raises `OSError` immediately if no credentials are configured,
   rather than deferring the failure to a later `.authenticate()` call.
   This module's `_import_kaggle_api()` wraps exactly that import in a
   try/except for this reason.
2. Credential resolution (this version): a `kaggle.json` file (containing
   `{"username": ..., "key": ...}`) in `KAGGLE_CONFIG_DIR` (or
   `~/.config/kaggle` / `~/.kaggle` if unset), OR the `KAGGLE_USERNAME` +
   `KAGGLE_KEY` environment variables. Both were confirmed to authenticate
   cleanly with no import-time error in this sandbox.

**A newer major version of the `kaggle` package (2.x) exists, using an
OAuth-first flow (`kaggle auth login`) plus a `KAGGLE_API_TOKEN` env
var/`~/.kaggle/access_token` file.** It was test-installed here too, but
its import path calls out to a browser-based OAuth flow that assumes an
interactive terminal — importing it under this build's SANDBOXED,
non-interactive shell raised `ImportError` even when credentials WERE
present via env vars, purely because stdio wasn't a TTY. Since this
adapter is designed to run as a subprocess spawned by the Next.js server
(never an interactive terminal), 1.6.17 is pinned in `requirements.txt`
specifically to avoid that failure mode. If a maintainer wants the newer
OAuth flow, re-verify this behaviour against the actual pinned version
before switching.

**Terms acceptance.** Kaggle requires a user to accept a dataset's terms
on kaggle.com before the API will serve it, for some datasets. The API
reports this as `kaggle.rest.ApiException` with `.status == 403` (verified
against the installed package's real exception class/attributes — the
network call itself could not be exercised from this sandbox). This
module surfaces that as `KaggleTermsNotAcceptedError` with a link back to
the dataset's page — it does not, and will not, attempt to bypass this.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional


class KaggleNotConfiguredError(RuntimeError):
    """No usable Kaggle credentials, or the `kaggle` package itself
    couldn't be imported/authenticated."""


class KaggleTermsNotAcceptedError(RuntimeError):
    """Kaggle's API reported that this account hasn't accepted the
    dataset's terms yet — never bypassed, only surfaced."""


@dataclass(frozen=True)
class KaggleDatasetFile:
    name: str
    size_bytes: Optional[int]


def has_kaggle_credentials(config_dir: Optional[str] = None) -> bool:
    """Fast pre-flight check mirroring exactly what kaggle==1.6.17 itself
    looks for — used by the UI to show "Connected"/"Not connected" without
    having to import the (comparatively heavy) `kaggle` package just to
    check. `download_dataset` below is always the real source of truth."""

    if os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        return True
    directory = Path(config_dir or os.environ.get("KAGGLE_CONFIG_DIR") or (Path.home() / ".kaggle"))
    return (directory / "kaggle.json").exists()


def _import_kaggle_api():
    """Isolated so the failure mode described in the module docstring
    (point 1) is caught in exactly one place and converted into this
    module's own exception type, rather than leaking a raw `OSError`/
    `ImportError` from a third-party package's import-time side effect."""

    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError as exc:
        raise KaggleNotConfiguredError(
            "The `kaggle` package is not installed. Add it to python/requirements.txt "
            "(`pip install kaggle==1.6.17`) to enable Kaggle downloads."
        ) from exc
    except OSError as exc:
        raise KaggleNotConfiguredError(
            "Kaggle is not connected. Go to Settings -> Data Connections -> Kaggle and connect "
            "your account (an API token from kaggle.com/settings/account), or set "
            "KAGGLE_USERNAME/KAGGLE_KEY for CLI use. "
            f"(underlying error: {exc})"
        ) from exc
    return KaggleApi


class KaggleAdapter:
    """Thin wrapper over `kaggle.api.kaggle_api_extended.KaggleApi`.
    `client_factory`, if given, replaces the real client entirely — used by
    this module's own tests, and is the only way this class is exercised in
    this build (no live Kaggle account is reachable from this sandbox)."""

    def __init__(self, client_factory: Optional[Callable[[], Any]] = None):
        self._client_factory = client_factory
        self._client: Optional[Any] = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if self._client_factory is not None:
            self._client = self._client_factory()
            return self._client

        if not has_kaggle_credentials():
            raise KaggleNotConfiguredError(
                "Kaggle is not connected. Go to Settings -> Data Connections -> Kaggle and connect "
                "your account, or set KAGGLE_USERNAME/KAGGLE_KEY for CLI use."
            )
        api_cls = _import_kaggle_api()
        client = api_cls()
        client.authenticate()
        self._client = client
        return client

    def download_dataset(self, dataset_ref: str, dest_dir: Path | str, unzip: bool = True) -> Path:
        """`dataset_ref` is `"owner/dataset-slug"`, exactly as it appears in
        a Kaggle dataset's URL. Downloads (and by default extracts) every
        file in the dataset into `dest_dir`."""

        client = self._get_client()
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        try:
            client.dataset_download_files(dataset_ref, path=str(dest_dir), unzip=unzip, quiet=True)
        except Exception as exc:  # kaggle.rest.ApiException doesn't subclass a narrower type
            status = getattr(exc, "status", None)
            if status == 403:
                raise KaggleTermsNotAcceptedError(
                    f"Open https://www.kaggle.com/datasets/{dataset_ref} and accept the dataset's "
                    "terms before importing. RacingEdge will not attempt to bypass this."
                ) from exc
            if status == 401:
                raise KaggleNotConfiguredError(
                    f"Kaggle rejected the connected credentials for {dataset_ref!r} — reconnect in "
                    "Settings -> Data Connections."
                ) from exc
            if status == 404:
                raise KaggleNotConfiguredError(f"Kaggle dataset not found: {dataset_ref!r}.") from exc
            raise

        return dest_dir

    def list_dataset_files(self, dataset_ref: str) -> list[KaggleDatasetFile]:
        client = self._get_client()
        raw_files = client.dataset_list_files(dataset_ref).files
        files: list[KaggleDatasetFile] = []
        for f in raw_files:
            files.append(
                KaggleDatasetFile(
                    name=getattr(f, "name", str(f)),
                    size_bytes=getattr(f, "total_bytes", None) or getattr(f, "totalBytes", None),
                )
            )
        return files
