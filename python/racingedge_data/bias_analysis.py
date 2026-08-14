"""Dataset bias analysis.

Free/community racing datasets are never a random sample of UK/Ireland
racing — they skew towards particular years, tracks, or race types
depending on how and when they were scraped or exported. Phase 3C requires
this skew to be reported, not discovered by surprise after a model is
trained on it. This module answers "what is under- or over-represented in
this dataset?", not "is this dataset good?" — no verdict is rendered here,
only distributions and gaps for a human to judge.

Every figure here is computed live from the same rows the training
pipeline reads, scoped to an explicit `race_ids` list (typically a
`DatasetVersion`'s races) or, if omitted, every race currently in the
database. Nothing is cached, inferred, or extrapolated.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class YearBreakdown:
    year: int
    race_count: int
    runner_count: int
    avg_field_size: Optional[float]
    flat_pct: Optional[float]
    favourite_win_rate: Optional[float]
    going_good_or_faster_pct: Optional[float]


@dataclass
class BiasAnalysisReport:
    race_count: int
    runner_count: int

    years_present: list[int] = field(default_factory=list)
    missing_years_in_range: list[int] = field(default_factory=list)

    track_race_counts: dict[str, int] = field(default_factory=dict)
    tracks_with_under_10_races: list[str] = field(default_factory=list)

    class_race_counts: dict[str, int] = field(default_factory=dict)
    missing_class_pct: Optional[float] = None

    flat_jumps_counts: dict[str, int] = field(default_factory=dict)

    favourite_outsider_buckets: dict[str, dict[str, float]] = field(default_factory=dict)

    avg_field_size: Optional[float] = None
    median_field_size: Optional[float] = None
    min_field_size: Optional[int] = None
    max_field_size: Optional[int] = None

    odds_distribution_buckets: dict[str, int] = field(default_factory=dict)
    missing_sp_pct: Optional[float] = None

    non_runner_count: int = 0
    non_runner_pct: Optional[float] = None

    dnf_status_counts: dict[str, int] = field(default_factory=dict)
    dnf_pct: Optional[float] = None

    by_year: list[YearBreakdown] = field(default_factory=list)

    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["by_year"] = [asdict(y) for y in self.by_year]
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


# Standard SP buckets. Deliberately coarse and fixed (not data-derived
# quantiles) so distributions are comparable across dataset versions.
_ODDS_BUCKETS = [
    ("<=2.0 (odds-on)", 0.0, 2.0),
    ("2.01-4.0", 2.0, 4.0),
    ("4.01-8.0", 4.0, 8.0),
    ("8.01-16.0", 8.0, 16.0),
    ("16.01-33.0", 16.0, 33.0),
    (">33.0", 33.0, float("inf")),
]

_DNF_STATUSES = {"PU", "UR", "F", "BD", "DSQ"}


def _race_id_filter(race_ids: Optional[list[str]]) -> tuple[str, list[str]]:
    if race_ids is None:
        return "", []
    if not race_ids:
        return " WHERE 1=0", []
    placeholders = ",".join("?" for _ in race_ids)
    return f" WHERE r.id IN ({placeholders})", list(race_ids)


def compute_bias_report(
    conn: sqlite3.Connection, race_ids: Optional[list[str]] = None
) -> BiasAnalysisReport:
    """Computes the full bias report. `race_ids=None` scopes to every race
    currently stored; pass a `DatasetVersion`'s race list to scope the
    report to exactly that dataset."""

    where_clause, params = _race_id_filter(race_ids)

    race_count = conn.execute(
        f'SELECT COUNT(*) as c FROM "Race" r{where_clause}', params
    ).fetchone()["c"]

    if race_count == 0:
        return BiasAnalysisReport(
            race_count=0,
            runner_count=0,
            warnings=["No races in scope — nothing to analyse."],
        )

    runner_where, runner_params = _runner_join_filter(race_ids)

    runner_count = conn.execute(
        f'SELECT COUNT(*) as c FROM "Runner" ru JOIN "Race" r ON r.id = ru.raceId{runner_where}',
        runner_params,
    ).fetchone()["c"]

    report = BiasAnalysisReport(race_count=race_count, runner_count=runner_count)

    _fill_year_coverage(conn, where_clause, params, report)
    _fill_track_coverage(conn, where_clause, params, report)
    _fill_class_coverage(conn, where_clause, params, report)
    _fill_flat_jumps(conn, where_clause, params, report)
    _fill_field_size(conn, where_clause, params, report)
    _fill_favourite_outsider(conn, runner_where, runner_params, report)
    _fill_odds_distribution(conn, runner_where, runner_params, report)
    _fill_non_runners(conn, runner_where, runner_params, report)
    _fill_dnf(conn, race_ids, report)
    _fill_by_year(conn, race_ids, report)
    _fill_warnings(report)

    return report


def _runner_join_filter(race_ids: Optional[list[str]]) -> tuple[str, list[str]]:
    if race_ids is None:
        return "", []
    if not race_ids:
        return " WHERE 1=0", []
    placeholders = ",".join("?" for _ in race_ids)
    return f" WHERE r.id IN ({placeholders})", list(race_ids)


def _fill_year_coverage(conn, where_clause, params, report: BiasAnalysisReport) -> None:
    rows = conn.execute(
        f"SELECT DISTINCT CAST(strftime('%Y', r.date) AS INTEGER) as yr "
        f'FROM "Race" r{where_clause}',
        params,
    ).fetchall()
    years = sorted(row["yr"] for row in rows if row["yr"] is not None)
    report.years_present = years
    if years:
        full_range = set(range(years[0], years[-1] + 1))
        report.missing_years_in_range = sorted(full_range - set(years))


def _fill_track_coverage(conn, where_clause, params, report: BiasAnalysisReport) -> None:
    rows = conn.execute(
        f'SELECT r.racecourse as track, COUNT(*) as c FROM "Race" r{where_clause} '
        "GROUP BY r.racecourse ORDER BY c DESC",
        params,
    ).fetchall()
    report.track_race_counts = {row["track"]: row["c"] for row in rows}
    report.tracks_with_under_10_races = [row["track"] for row in rows if row["c"] < 10]


def _fill_class_coverage(conn, where_clause, params, report: BiasAnalysisReport) -> None:
    rows = conn.execute(
        f'SELECT r.raceClass as cls, COUNT(*) as c FROM "Race" r{where_clause} '
        "GROUP BY r.raceClass",
        params,
    ).fetchall()
    counts: dict[str, int] = {}
    missing = 0
    for row in rows:
        if row["cls"] is None:
            missing = row["c"]
        else:
            counts[f"Class {row['cls']}"] = row["c"]
    report.class_race_counts = counts
    report.missing_class_pct = round(100.0 * missing / report.race_count, 2) if report.race_count else None


def _fill_flat_jumps(conn, where_clause, params, report: BiasAnalysisReport) -> None:
    rows = conn.execute(
        f'SELECT r.flatJumps as fj, COUNT(*) as c FROM "Race" r{where_clause} GROUP BY r.flatJumps',
        params,
    ).fetchall()
    report.flat_jumps_counts = {row["fj"]: row["c"] for row in rows}


def _fill_field_size(conn, where_clause, params, report: BiasAnalysisReport) -> None:
    rows = conn.execute(
        f'SELECT r.numberOfRunners as n FROM "Race" r{where_clause} ORDER BY r.numberOfRunners',
        params,
    ).fetchall()
    sizes = [row["n"] for row in rows if row["n"] is not None]
    if not sizes:
        return
    report.avg_field_size = round(sum(sizes) / len(sizes), 2)
    report.min_field_size = min(sizes)
    report.max_field_size = max(sizes)
    mid = len(sizes) // 2
    report.median_field_size = float(sizes[mid]) if len(sizes) % 2 == 1 else (sizes[mid - 1] + sizes[mid]) / 2.0


def _fill_favourite_outsider(conn, runner_where, runner_params, report: BiasAnalysisReport) -> None:
    """Favourite/outsider buckets, keyed by declared `favouriteRank` (1 =
    favourite). Win rate is computed against `ResultEntry.finishingPosition
    = 1` — POST-RACE data used only for retrospective bucket description,
    never as a training feature (see POINT_IN_TIME_ARCHITECTURE.md)."""

    rows = conn.execute(
        f'SELECT ru.favouriteRank as rank, res.finishingPosition as pos '
        f'FROM "Runner" ru JOIN "Race" r ON r.id = ru.raceId '
        f'LEFT JOIN "ResultEntry" res ON res.runnerId = ru.id{runner_where}',
        runner_params,
    ).fetchall()

    buckets: dict[str, list[int]] = {"Favourite (rank 1)": [], "2nd/3rd favourite (rank 2-3)": [],
                                      "Outsider (rank 4+)": [], "No favourite rank recorded": []}
    for row in rows:
        rank = row["rank"]
        won = 1 if row["pos"] == 1 else 0
        if rank is None:
            buckets["No favourite rank recorded"].append(won)
        elif rank == 1:
            buckets["Favourite (rank 1)"].append(won)
        elif rank <= 3:
            buckets["2nd/3rd favourite (rank 2-3)"].append(won)
        else:
            buckets["Outsider (rank 4+)"].append(won)

    result: dict[str, dict[str, float]] = {}
    for label, wins in buckets.items():
        n = len(wins)
        result[label] = {
            "runner_count": n,
            "win_rate_pct": round(100.0 * sum(wins) / n, 2) if n else None,
        }
    report.favourite_outsider_buckets = result


def _fill_odds_distribution(conn, runner_where, runner_params, report: BiasAnalysisReport) -> None:
    rows = conn.execute(
        f'SELECT ru.startingPriceDecimal as sp FROM "Runner" ru JOIN "Race" r ON r.id = ru.raceId'
        f"{runner_where}",
        runner_params,
    ).fetchall()
    total = len(rows)
    missing = sum(1 for row in rows if row["sp"] is None)
    report.missing_sp_pct = round(100.0 * missing / total, 2) if total else None

    counts = {label: 0 for label, _, _ in _ODDS_BUCKETS}
    for row in rows:
        sp = row["sp"]
        if sp is None:
            continue
        for label, low, high in _ODDS_BUCKETS:
            if low < sp <= high:
                counts[label] += 1
                break
    report.odds_distribution_buckets = counts


def _fill_non_runners(conn, runner_where, runner_params, report: BiasAnalysisReport) -> None:
    rows = conn.execute(
        f'SELECT ru.nonRunner as nr FROM "Runner" ru JOIN "Race" r ON r.id = ru.raceId{runner_where}',
        runner_params,
    ).fetchall()
    total = len(rows)
    non_runners = sum(1 for row in rows if row["nr"])
    report.non_runner_count = non_runners
    report.non_runner_pct = round(100.0 * non_runners / total, 2) if total else None


def _fill_dnf(conn, race_ids: Optional[list[str]], report: BiasAnalysisReport) -> None:
    where_clause, params = _race_id_filter(race_ids)
    rows = conn.execute(
        f'SELECT res.finishStatus as status, COUNT(*) as c '
        f'FROM "ResultEntry" res '
        f'JOIN "Runner" ru ON ru.id = res.runnerId '
        f'JOIN "Race" r ON r.id = ru.raceId{where_clause} '
        "GROUP BY res.finishStatus",
        params,
    ).fetchall()
    counts = {(row["status"] or "(none recorded)"): row["c"] for row in rows}
    report.dnf_status_counts = counts
    total = sum(counts.values())
    dnf_total = sum(c for status, c in counts.items() if status in _DNF_STATUSES)
    report.dnf_pct = round(100.0 * dnf_total / total, 2) if total else None


def _fill_by_year(conn, race_ids: Optional[list[str]], report: BiasAnalysisReport) -> None:
    for year in report.years_present:
        year_where, year_params = _race_id_filter(race_ids)
        year_clause = f"{year_where}{' AND' if year_where else ' WHERE'} strftime('%Y', r.date) = ?"
        year_params = [*year_params, str(year)]

        race_row = conn.execute(
            f'SELECT COUNT(*) as c, AVG(r.numberOfRunners) as avg_n FROM "Race" r{year_clause}',
            year_params,
        ).fetchone()

        flat_row = conn.execute(
            f'SELECT r.flatJumps as fj, COUNT(*) as c FROM "Race" r{year_clause} GROUP BY r.flatJumps',
            year_params,
        ).fetchall()
        flat_total = sum(row["c"] for row in flat_row)
        flat_count = next((row["c"] for row in flat_row if row["fj"] == "FLAT"), 0)
        flat_pct = round(100.0 * flat_count / flat_total, 2) if flat_total else None

        going_row = conn.execute(
            f'SELECT r.going as going, COUNT(*) as c FROM "Race" r{year_clause} GROUP BY r.going',
            year_params,
        ).fetchall()
        going_total = sum(row["c"] for row in going_row)
        good_or_faster = {"Good to Firm", "Firm", "Good", "Standard", "Standard to Fast", "Fast"}
        good_count = sum(row["c"] for row in going_row if row["going"] in good_or_faster)
        going_pct = round(100.0 * good_count / going_total, 2) if going_total else None

        runner_year_where, runner_year_params = _runner_join_filter(race_ids)
        runner_year_clause = (
            f"{runner_year_where}{' AND' if runner_year_where else ' WHERE'} strftime('%Y', r.date) = ?"
        )
        runner_year_params = [*runner_year_params, str(year)]
        fav_row = conn.execute(
            f'SELECT ru.favouriteRank as rank, res.finishingPosition as pos '
            f'FROM "Runner" ru JOIN "Race" r ON r.id = ru.raceId '
            f'LEFT JOIN "ResultEntry" res ON res.runnerId = ru.id{runner_year_clause}',
            runner_year_params,
        ).fetchall()
        fav_rows = [row for row in fav_row if row["rank"] == 1]
        fav_win_rate = (
            round(100.0 * sum(1 for row in fav_rows if row["pos"] == 1) / len(fav_rows), 2)
            if fav_rows
            else None
        )

        runner_count_row = conn.execute(
            f'SELECT COUNT(*) as c FROM "Runner" ru JOIN "Race" r ON r.id = ru.raceId{runner_year_clause}',
            runner_year_params,
        ).fetchone()

        report.by_year.append(
            YearBreakdown(
                year=year,
                race_count=race_row["c"],
                runner_count=runner_count_row["c"],
                avg_field_size=round(race_row["avg_n"], 2) if race_row["avg_n"] is not None else None,
                flat_pct=flat_pct,
                favourite_win_rate=fav_win_rate,
                going_good_or_faster_pct=going_pct,
            )
        )


def _fill_warnings(report: BiasAnalysisReport) -> None:
    """Descriptive flags only — never a pass/fail verdict. A missing signal
    here means "look at this before trusting the dataset", not "this
    dataset is invalid"."""

    warnings: list[str] = []

    if report.missing_years_in_range:
        warnings.append(
            f"{len(report.missing_years_in_range)} year(s) inside the dataset's own date range have "
            f"zero races: {report.missing_years_in_range}. Any model trained on this dataset has no "
            "signal at all for those years."
        )

    if report.tracks_with_under_10_races:
        warnings.append(
            f"{len(report.tracks_with_under_10_races)} track(s) have fewer than 10 races recorded — "
            "course-specific features for these tracks will be almost entirely missing-data defaults."
        )

    if report.non_runner_count == 0 and report.runner_count > 0:
        warnings.append(
            "Zero non-runners recorded across the whole dataset. Real UK/Ireland racing always has "
            "some declared non-runners — this strongly suggests the source data does not represent "
            "non-runners at all, rather than that none occurred."
        )

    if report.dnf_pct is not None and report.dnf_pct == 0.0:
        warnings.append(
            "Zero DNF/pulled-up/unseated/fell/disqualified results recorded. If this dataset includes "
            "jumps racing, a 0% DNF rate is very unlikely to be genuine and suggests finishStatus is "
            "not populated for non-completions rather than that all runners completed."
        )

    if report.missing_sp_pct is not None and report.missing_sp_pct > 20.0:
        warnings.append(
            f"{report.missing_sp_pct}% of runners have no starting price recorded — SP-derived "
            "features and value-backtesting cohorts will have reduced coverage."
        )

    if report.missing_class_pct is not None and report.missing_class_pct > 30.0:
        warnings.append(
            f"{report.missing_class_pct}% of races have no raceClass recorded — class-based features "
            "will fall back to their missing-data default for a large share of the dataset."
        )

    flat_total = sum(report.flat_jumps_counts.values())
    if flat_total:
        flat_pct = 100.0 * report.flat_jumps_counts.get("FLAT", 0) / flat_total
        jumps_pct = 100.0 * report.flat_jumps_counts.get("JUMPS", 0) / flat_total
        if flat_pct == 0.0 or jumps_pct == 0.0:
            missing_code = "jumps" if jumps_pct == 0.0 else "flat"
            warnings.append(f"Dataset contains no {missing_code} racing at all — coverage is single-code only.")

    report.warnings = warnings
