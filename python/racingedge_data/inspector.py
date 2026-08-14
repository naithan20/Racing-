"""Dataset schema inspector — Phase 3C's £0-data-cost entry point.

Given an arbitrary user-supplied SQLite (`.db`/`.sqlite`), CSV, or
JSON/JSONL file of historical horse-racing data — of UNKNOWN exact shape,
e.g. a Kaggle download — this module inspects its structure and PROPOSES a
column-role mapping onto RacingEdge's canonical schema, without ever
hard-coding against one exact dataset's column names.

**This module never imports anything.** It only reports what it found and
proposes a mapping. A human must review the mapping report (written to
disk as JSON) and explicitly confirm any column whose proposed role has
`confidence != "high"` before `racingedge_data.importers.free_dataset_importer`
will use it — see that module's `require_confirmation` parameter.

Nothing here fabricates or infers a MISSING field's value — it only
proposes which EXISTING column, if any, plausibly corresponds to a
canonical field. A canonical field with no plausible source column is left
unmapped, and the importer will simply leave that field `None` for every
imported row rather than guessing.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Column-role heuristics
# ---------------------------------------------------------------------------

# For each canonical role: (exact_names, contains_names, abbreviation_names).
# exact_names -> "high" confidence if the normalized column name matches
#   exactly.
# contains_names -> "medium" confidence if the normalized name CONTAINS one
#   of these as a substring, but isn't an exact match.
# abbreviation_names -> "low" confidence — short/ambiguous codes that are
#   plausible but genuinely uncertain (e.g. "or", "sp", "pos") and MUST be
#   confirmed by a human regardless of how confident the match looks.
ROLE_RULES: dict[str, dict[str, list[str]]] = {
    "race_id": {"exact": ["race_id", "raceid", "event_id"], "contains": ["race_id"], "abbrev": ["rid"]},
    "race_date": {"exact": ["race_date", "date", "meeting_date"], "contains": ["race_date", "off_date"], "abbrev": []},
    "race_time": {"exact": ["race_time", "off_time"], "contains": ["race_time", "off_time"], "abbrev": ["off"]},
    "course": {"exact": ["course", "track", "venue"], "contains": ["course", "track", "venue"], "abbrev": []},
    "country": {"exact": ["country", "region"], "contains": ["country"], "abbrev": []},
    "race_name": {"exact": ["race_name"], "contains": ["race_name"], "abbrev": []},
    "race_type": {"exact": ["race_type", "type"], "contains": ["race_type"], "abbrev": []},
    "race_class": {"exact": ["race_class", "class"], "contains": ["race_class"], "abbrev": ["rclass"]},
    "distance": {
        "exact": ["distance", "distance_f", "distance_furlongs", "distance_yards", "distance_m"],
        "contains": ["distance", "dist_"],
        "abbrev": ["dist"],
    },
    "going": {"exact": ["going", "ground"], "contains": ["going"], "abbrev": []},
    "flat_jumps": {"exact": ["flat_jumps", "discipline", "code"], "contains": ["flat_jumps"], "abbrev": []},
    "field_size": {
        "exact": ["field_size", "number_of_runners", "num_runners"],
        "contains": ["field_size", "num_runners"],
        "abbrev": ["nr"],
    },
    "horse_name": {"exact": ["horse_name", "horse", "runner_name", "runner"], "contains": ["horse"], "abbrev": []},
    "horse_id": {"exact": ["horse_id", "horseid"], "contains": ["horse_id"], "abbrev": []},
    "draw": {"exact": ["draw", "stall_number"], "contains": ["draw"], "abbrev": ["stall"]},
    "weight": {"exact": ["weight", "weight_lbs"], "contains": ["weight"], "abbrev": ["lbs", "wgt"]},
    "age": {"exact": ["age"], "contains": ["age"], "abbrev": []},
    "sex": {"exact": ["sex", "gender"], "contains": ["sex"], "abbrev": []},
    "official_rating": {
        "exact": ["official_rating", "rating"],
        "contains": ["official_rating", "rating"],
        "abbrev": ["or", "ofr"],
    },
    "jockey": {"exact": ["jockey", "jockey_name"], "contains": ["jockey"], "abbrev": []},
    "trainer": {"exact": ["trainer", "trainer_name"], "contains": ["trainer"], "abbrev": []},
    "sire": {"exact": ["sire", "sire_name"], "contains": ["sire"], "abbrev": []},
    "dam": {"exact": ["dam", "dam_name"], "contains": ["dam"], "abbrev": []},
    "damsire": {"exact": ["damsire"], "contains": ["damsire"], "abbrev": []},
    "headgear": {"exact": ["headgear", "equipment"], "contains": ["headgear"], "abbrev": ["hg"]},
    "finishing_position": {
        "exact": ["finishing_position", "finish_position", "position"],
        "contains": ["finish_pos", "finishing_position"],
        "abbrev": ["pos", "place"],
    },
    "beaten_distance": {
        "exact": ["beaten_distance", "distance_beaten"],
        "contains": ["beaten_distance", "beaten"],
        "abbrev": ["btn"],
    },
    "starting_price": {
        "exact": ["starting_price", "starting_price_decimal", "sp_decimal"],
        "contains": ["starting_price"],
        "abbrev": ["sp", "odds", "price"],
    },
    "bsp": {"exact": ["bsp", "betfair_sp"], "contains": ["bsp"], "abbrev": []},
    "comment": {"exact": ["comment", "comments"], "contains": ["comment"], "abbrev": ["note"]},
    "sectional": {"exact": ["sectional", "sectionals", "sectional_times"], "contains": ["sectional"], "abbrev": ["split"]},
    "non_runner": {"exact": ["non_runner", "withdrawn"], "contains": ["non_runner"], "abbrev": ["nr_flag"]},
}


def normalize_column_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def propose_role(column_name: str) -> tuple[Optional[str], str]:
    """Returns `(role, confidence)`. `confidence` is one of
    `"high"|"medium"|"low"|"unmapped"`. A role can be proposed with "low"
    confidence — the importer still requires explicit confirmation for
    anything below "high"."""

    normalized = normalize_column_name(column_name)
    if not normalized:
        return None, "unmapped"

    for role, rules in ROLE_RULES.items():
        if normalized in rules["exact"]:
            return role, "high"

    # Among "contains" matches, prefer the LONGEST matching token — e.g.
    # "horse_id_number" should resolve to horse_id (token "horse_id"), not
    # horse_name (token "horse"), even though both are substrings.
    best_match: Optional[tuple[str, str]] = None  # (role, token)
    for role, rules in ROLE_RULES.items():
        for token in rules["contains"]:
            if token in normalized and (best_match is None or len(token) > len(best_match[1])):
                best_match = (role, token)
    if best_match is not None:
        return best_match[0], "medium"

    for role, rules in ROLE_RULES.items():
        if normalized in rules["abbrev"]:
            return role, "low"

    return None, "unmapped"


# ---------------------------------------------------------------------------
# Profiling
# ---------------------------------------------------------------------------


@dataclass
class ColumnProfile:
    name: str
    dtype: str
    non_null_pct: float
    sample_values: list[str]
    proposed_role: Optional[str]
    confidence: str


@dataclass
class TableProfile:
    name: str
    row_count: int
    columns: list[ColumnProfile]
    likely_kind: str  # "race_and_runner_level" | "race_level" | "runner_level" | "unknown"
    date_column: Optional[str] = None
    date_range: Optional[tuple[str, str]] = None


@dataclass
class InspectionReport:
    source_path: str
    source_format: str  # "sqlite" | "csv" | "json" | "jsonl"
    generated_at: str
    tables: list[TableProfile] = field(default_factory=list)

    def ambiguous_columns(self) -> list[tuple[str, str]]:
        """`(table_name, column_name)` pairs whose proposed role is not
        "high" confidence — these MUST be confirmed by a human."""

        out = []
        for table in self.tables:
            for col in table.columns:
                if col.proposed_role is not None and col.confidence != "high":
                    out.append((table.name, col.name))
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "source_format": self.source_format,
            "generated_at": self.generated_at,
            "tables": [
                {
                    "name": t.name,
                    "row_count": t.row_count,
                    "likely_kind": t.likely_kind,
                    "date_column": t.date_column,
                    "date_range": list(t.date_range) if t.date_range else None,
                    "columns": [asdict(c) for c in t.columns],
                }
                for t in self.tables
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def write_mapping_template(self, path: str | Path) -> None:
        """Writes a REVIEWABLE mapping file: one entry per table, listing
        every column's proposed role/confidence, with a `confirmed: false`
        flag on every non-high-confidence proposal that a human must flip
        to `true` (or correct the `role`) before the importer will use it.
        High-confidence proposals default `confirmed: true` since they're
        unambiguous — still fully editable/overridable before import."""

        mapping: dict[str, Any] = {"source_path": self.source_path, "source_format": self.source_format, "tables": {}}
        for table in self.tables:
            mapping["tables"][table.name] = {
                "likely_kind": table.likely_kind,
                "columns": {
                    col.name: {
                        "role": col.proposed_role,
                        "confidence": col.confidence,
                        "confirmed": col.confidence == "high",
                    }
                    for col in table.columns
                    if col.proposed_role is not None
                },
            }
        Path(path).write_text(json.dumps(mapping, indent=2))


def _sample_values(series: pd.Series, n: int = 3) -> list[str]:
    non_null = series.dropna()
    return [str(v)[:60] for v in non_null.head(n).tolist()]


def _guess_date_column(df: pd.DataFrame) -> Optional[str]:
    for candidate in ("race_date", "date", "off_date", "meeting_date", "event_dt"):
        for col in df.columns:
            if normalize_column_name(col) == candidate:
                return col
    return None


def _profile_dataframe(name: str, df: pd.DataFrame, full_row_count: Optional[int] = None) -> TableProfile:
    columns = []
    for col in df.columns:
        role, confidence = propose_role(col)
        non_null_pct = round(100.0 * df[col].notna().mean(), 1) if len(df) > 0 else 0.0
        columns.append(
            ColumnProfile(
                name=col,
                dtype=str(df[col].dtype),
                non_null_pct=non_null_pct,
                sample_values=_sample_values(df[col]),
                proposed_role=role,
                confidence=confidence,
            )
        )

    roles_found = {c.proposed_role for c in columns if c.proposed_role}
    has_race_fields = bool(roles_found & {"course", "race_date", "race_name"})
    has_runner_fields = bool(roles_found & {"horse_name", "jockey", "trainer", "finishing_position"})
    if has_race_fields and has_runner_fields:
        likely_kind = "race_and_runner_level"
    elif has_race_fields:
        likely_kind = "race_level"
    elif has_runner_fields:
        likely_kind = "runner_level"
    else:
        likely_kind = "unknown"

    date_column = _guess_date_column(df)
    date_range = None
    if date_column is not None:
        try:
            parsed = pd.to_datetime(df[date_column], errors="coerce", utc=True).dropna()
            if len(parsed) > 0:
                date_range = (str(parsed.min().date()), str(parsed.max().date()))
        except Exception:
            date_range = None

    return TableProfile(
        name=name,
        row_count=full_row_count if full_row_count is not None else len(df),
        columns=columns,
        likely_kind=likely_kind,
        date_column=date_column,
        date_range=date_range,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

SQLITE_EXTENSIONS = {".db", ".sqlite", ".sqlite3"}


def inspect_file(path: str | Path, sample_rows: int = 5000) -> InspectionReport:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No such file: {path}")

    suffix = path.suffix.lower()
    generated_at = datetime.now(timezone.utc).isoformat()

    if suffix in SQLITE_EXTENSIONS:
        return _inspect_sqlite(path, sample_rows, generated_at)
    if suffix == ".csv" or suffix == ".gz" and path.stem.endswith(".csv"):
        return _inspect_csv(path, sample_rows, generated_at)
    if suffix in (".json", ".jsonl", ".ndjson"):
        return _inspect_json(path, sample_rows, generated_at)

    raise ValueError(f"Unrecognized file type for inspection: {path} (expected .db/.sqlite/.csv/.json/.jsonl)")


def _inspect_sqlite(path: Path, sample_rows: int, generated_at: str) -> InspectionReport:
    conn = sqlite3.connect(str(path))
    try:
        table_names = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        tables = []
        for table_name in table_names:
            row_count = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
            sample_df = pd.read_sql_query(f'SELECT * FROM "{table_name}" LIMIT {sample_rows}', conn)
            tables.append(_profile_dataframe(table_name, sample_df, full_row_count=row_count))
        return InspectionReport(source_path=str(path), source_format="sqlite", generated_at=generated_at, tables=tables)
    finally:
        conn.close()


def _inspect_csv(path: Path, sample_rows: int, generated_at: str) -> InspectionReport:
    sample_df = pd.read_csv(path, nrows=sample_rows, low_memory=False)
    with (pd.io.common.get_handle(path, "r", compression="infer").handle) as f:
        full_row_count = sum(1 for _ in f) - 1  # minus header
    table = _profile_dataframe(path.stem, sample_df, full_row_count=max(full_row_count, 0))
    return InspectionReport(source_path=str(path), source_format="csv", generated_at=generated_at, tables=[table])


def _inspect_json(path: Path, sample_rows: int, generated_at: str) -> InspectionReport:
    suffix = path.suffix.lower()
    if suffix in (".jsonl", ".ndjson"):
        records = []
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= sample_rows:
                    break
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        with open(path, "r", encoding="utf-8") as f:
            full_row_count = sum(1 for line in f if line.strip())
        sample_df = pd.DataFrame(records)
        fmt = "jsonl"
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload if isinstance(payload, list) else payload.get("records", payload.get("races", []))
        full_row_count = len(records)
        sample_df = pd.DataFrame(records[:sample_rows])
        fmt = "json"

    table = _profile_dataframe(path.stem, sample_df, full_row_count=full_row_count)
    return InspectionReport(source_path=str(path), source_format=fmt, generated_at=generated_at, tables=[table])
