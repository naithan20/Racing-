"""CLI: import historical UK & Irish races from The Racing API into
RacingEdge as REAL data.

Run:
  python -m racingedge_data.cli.import_racing_api --from 2024-01-01 --to 2026-08-01

or via the npm wrapper:
  npm run data:racingapi -- --from 2024-01-01 --to 2026-08-01

Requires a licensed theracingapi.com subscription — set `RACING_API_USERNAME`
and `RACING_API_PASSWORD` environment variables before running. **If they
are not set, this command stops immediately with a clear message and does
NOT fall back to synthetic/sample data or fabricate a result.**

Built on top of `racingedge_data.importers.import_runner.import_races`, so
this command is, by construction:

- **resumable** — pass `--resume-batch-id <id>` (printed by a previous,
  interrupted run) to continue from where it left off, using the
  `ImportBatch.resumeCursor` the earlier run left behind.
- **idempotent** — defaults to a deterministic `idempotency_key` derived
  from the date range, so re-running the exact same command twice is safe
  and the second run short-circuits immediately.
- **rate-limit aware** — `RacingApiProvider`'s HTTP client enforces the
  confirmed 2 requests/second ceiling.
- **pagination aware** — pages through `/results` via `limit`/`skip`/`total`.
- **retrying with exponential backoff** — on 429/5xx/connection errors, up
  to 5 attempts per request before raising.
- **progress-reporting** — prints `processed`/`errors` as it goes.
- **duplicate-handling** — races already recorded in `DataProvenance` for
  this provider are skipped and counted, never re-inserted.
- **audited** — every run is one `ImportBatch` row, and every imported race
  gets a `DataProvenance` row (see DATA_PROVENANCE.md).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime

from racingedge_data.importers.import_runner import import_races
from racingedge_data.providers.base import ProviderConfigurationError
from racingedge_data.providers.racing_api import RacingApiProvider
from racingedge_model import db


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Expected YYYY-MM-DD, got {value!r}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from", dest="from_date", required=True, type=_parse_date, help="Start date, YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", required=True, type=_parse_date, help="End date, YYYY-MM-DD")
    parser.add_argument(
        "--resume-batch-id",
        default=None,
        help="Resume a previously interrupted ImportBatch by id instead of starting a new one",
    )
    parser.add_argument(
        "--idempotency-key",
        default=None,
        help="Defaults to a deterministic key derived from the date range — re-running with the "
        "same key (or the same dates, if left unset) is always safe",
    )
    args = parser.parse_args()

    if args.from_date > args.to_date:
        print("--from must not be after --to", file=sys.stderr)
        sys.exit(2)

    username = os.environ.get("RACING_API_USERNAME")
    password = os.environ.get("RACING_API_PASSWORD")
    if not username or not password:
        print(
            "Racing API credentials are not configured — nothing has been imported.\n\n"
            "This command requires a licensed theracingapi.com subscription. Set these\n"
            "environment variables and re-run:\n\n"
            "  RACING_API_USERNAME\n"
            "  RACING_API_PASSWORD\n\n"
            "No data has been fabricated or substituted with synthetic data. See\n"
            "DATA_SOURCES.md for exactly what plan/subscription tier is required for\n"
            "historical /results access, and what this adapter has and hasn't verified\n"
            "about the API's field-level schema.",
            file=sys.stderr,
        )
        sys.exit(2)

    provider = RacingApiProvider(username=username, password=password)
    idempotency_key = args.idempotency_key or f"racing-api-{args.from_date.isoformat()}-{args.to_date.isoformat()}"

    conn = db.get_connection()

    def on_progress(processed: int, errors: int) -> None:
        print(f"  processed={processed} errors={errors}", end="\r", flush=True)

    print(
        f"Importing Racing API results for {args.from_date} .. {args.to_date} "
        f"(idempotency_key={idempotency_key})..."
    )

    try:
        result = import_races(
            conn,
            provider,
            args.from_date,
            args.to_date,
            source_type="REAL",
            filename=None,
            idempotency_key=idempotency_key,
            resume_from_batch_id=args.resume_batch_id,
            on_progress=on_progress,
        )
    except ProviderConfigurationError as exc:
        print(f"\nProvider configuration error: {exc}", file=sys.stderr)
        sys.exit(2)

    print(f"\n\nImportBatch {result.import_batch_id}: {result.status}")
    print(
        f"  processed={result.processed_rows} success={result.success_count} "
        f"duplicates={result.duplicate_rows} errors={result.error_count}"
    )
    if result.errors:
        print("  Failed records (see ImportBatch.errorLog for the full list):")
        for error in result.errors[:20]:
            print(f"    index={error.index} provider_race_id={error.provider_race_id} error={error.message}")
        if len(result.errors) > 20:
            print(f"    ... and {len(result.errors) - 20} more")

    if result.status == "FAILED":
        sys.exit(1)


if __name__ == "__main__":
    main()
