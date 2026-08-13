"""File-format/compression detection for the import CLI.

Builds the right `RaceDataProvider` for a bare file path — CSV, JSON, or
JSON Lines, each optionally gzip-compressed (`.csv.gz`, `.jsonl.gz`, ...).
Both `CsvRaceDataProvider` and `GenericJsonRaceDataProvider` already accept
any text file-like object, so all this module does is open the file with
the right decompression and hand it off — no format-specific logic here.
"""

from __future__ import annotations

import gzip
from pathlib import Path
from typing import IO

from racingedge_data.providers.base import RaceDataProvider
from racingedge_data.providers.csv_provider import CsvRaceDataProvider
from racingedge_data.providers.generic_json_provider import GenericJsonRaceDataProvider

CSV_SUFFIXES = (".csv",)
JSON_SUFFIXES = (".json", ".jsonl", ".ndjson")


def open_text_auto(path: str | Path) -> IO[str]:
    """Opens a file in text mode, transparently decompressing `.gz`."""

    path = Path(path)
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return open(path, "r", encoding="utf-8", newline="")


def build_race_provider_from_path(path: str | Path) -> RaceDataProvider:
    """Builds a `CsvRaceDataProvider` or `GenericJsonRaceDataProvider` for
    `path` based on its extension (ignoring a trailing `.gz`)."""

    path = Path(path)
    inner_suffix = Path(path.stem).suffix if path.suffix == ".gz" else path.suffix
    handle = open_text_auto(path)

    if inner_suffix in CSV_SUFFIXES:
        return CsvRaceDataProvider(handle)
    if inner_suffix in JSON_SUFFIXES:
        jsonl = inner_suffix in (".jsonl", ".ndjson")
        return GenericJsonRaceDataProvider(handle, jsonl=jsonl)

    handle.close()
    raise ValueError(
        f"Unrecognized file type for {path}: expected one of "
        f"{CSV_SUFFIXES + JSON_SUFFIXES} (optionally .gz-compressed)"
    )
