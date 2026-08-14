"""CLI: report dataset bias/skew figures — missing years/tracks/classes,
Flat vs jumps split, favourite/outsider distribution, field size, odds
distribution, non-runner and DNF coverage, and year-over-year comparison.

No verdict is printed ("good"/"bad" dataset) — only distributions and
explicit warnings, for a human to judge alongside the Feature Availability
Matrix and DatasetReview.

Note: `DatasetVersion` rows store aggregate counts and a date range, not
the individual race ids they cover, so this tool scopes by --source-type
and --from/--to date range directly against the `Race` table rather than
by DatasetVersion id — pass the same source-type/date-range you used to
build the DatasetVersion you want to inspect.

Run:
  npm run data:bias-report
  npm run data:bias-report -- --source-type REAL --from 2020-01-01 --to 2025-12-31
  # or directly:
  python -m racingedge_data.cli.bias_analysis [--source-type REAL] [--from DATE] [--to DATE] [--out report.json]
"""

from __future__ import annotations

import argparse

from racingedge_data.bias_analysis import compute_bias_report
from racingedge_model.db import get_connection


def _select_race_ids(conn, source_type: str | None, date_from: str | None, date_to: str | None) -> list[str] | None:
    if source_type is None and date_from is None and date_to is None:
        return None

    clauses = []
    params: list[str] = []
    if source_type is not None:
        clauses.append("sourceType = ?")
        params.append(source_type)
    if date_from is not None:
        clauses.append("date >= ?")
        params.append(date_from)
    if date_to is not None:
        clauses.append("date <= ?")
        params.append(date_to)

    where = " WHERE " + " AND ".join(clauses)
    rows = conn.execute(f'SELECT id FROM "Race"{where}', params).fetchall()
    return [row["id"] for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source-type", choices=["REAL", "SYNTHETIC", "SAMPLE"], default=None)
    parser.add_argument("--from", dest="date_from", default=None, help="ISO date, inclusive")
    parser.add_argument("--to", dest="date_to", default=None, help="ISO date, inclusive")
    parser.add_argument("--out", default=None, help="Optional path to write the full report as JSON")
    args = parser.parse_args()

    conn = get_connection()
    try:
        race_ids = _select_race_ids(conn, args.source_type, args.date_from, args.date_to)
        report = compute_bias_report(conn, race_ids=race_ids)
    finally:
        conn.close()

    print(f"Bias analysis — {report.race_count:,} races, {report.runner_count:,} runners\n")

    print(f"Years present: {report.years_present}")
    if report.missing_years_in_range:
        print(f"  MISSING years within range: {report.missing_years_in_range}")

    print(f"\nTracks: {len(report.track_race_counts)} distinct")
    if report.tracks_with_under_10_races:
        print(f"  {len(report.tracks_with_under_10_races)} track(s) with <10 races: {report.tracks_with_under_10_races}")

    print(f"\nClass coverage: {report.class_race_counts}")
    print(f"  missing raceClass: {report.missing_class_pct}%")

    print(f"\nFlat/Jumps split: {report.flat_jumps_counts}")

    print(f"\nField size: avg={report.avg_field_size}, median={report.median_field_size}, "
          f"min={report.min_field_size}, max={report.max_field_size}")

    print("\nFavourite/outsider buckets:")
    for label, stats in report.favourite_outsider_buckets.items():
        print(f"  {label}: n={stats['runner_count']}, win_rate={stats['win_rate_pct']}%")

    print(f"\nOdds distribution (SP buckets): {report.odds_distribution_buckets}")
    print(f"  missing SP: {report.missing_sp_pct}%")

    print(f"\nNon-runners: {report.non_runner_count} ({report.non_runner_pct}%)")
    print(f"DNF statuses: {report.dnf_status_counts} (DNF rate: {report.dnf_pct}%)")

    print("\nYear-over-year:")
    for y in report.by_year:
        print(f"  {y.year}: races={y.race_count}, runners={y.runner_count}, avg_field={y.avg_field_size}, "
              f"flat%={y.flat_pct}, fav_win_rate={y.favourite_win_rate}%, good-or-faster going%={y.going_good_or_faster_pct}")

    if report.warnings:
        print(f"\n{len(report.warnings)} warning(s):")
        for w in report.warnings:
            print(f"  - {w}")
    else:
        print("\nNo bias warnings raised.")

    if args.out:
        with open(args.out, "w") as f:
            f.write(report.to_json())
        print(f"\nWrote full report to {args.out}")


if __name__ == "__main__":
    main()
