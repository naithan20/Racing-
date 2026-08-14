"""CLI: import a user-supplied free/community historical racing dataset,
using a REVIEWED mapping file produced by `data:inspect`.

Run:
  npm run data:import-free -- --file ~/Downloads/raceform.db \\
    --mapping ~/Downloads/raceform.mapping.json \\
    --source-label "Kaggle: uk-ireland-horse-racing-results" \\
    --provenance-status COMMUNITY_UNVERIFIED \\
    --from 2000-01-01 --to 2026-01-01

`--provenance-status` has NO default — you must state explicitly what's
known about this dataset's reuse rights (see DATA_PROVENANCE.md and
ProvenanceStatus in prisma/schema.prisma). `--source-type` defaults to
REAL, since a genuine historical results dataset (free or not) is real
data, not synthetic — reuse-rights uncertainty is tracked separately via
provenance status, never conflated with data authenticity.

Refuses to proceed if the mapping file has any unconfirmed ambiguous
column — edit the mapping file and re-run rather than trying to force it.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from racingedge_data.importers.free_dataset_importer import (
    VALID_PROVENANCE_STATUSES,
    MappingNotConfirmedError,
    import_free_dataset,
)
from racingedge_model import db


def _parse_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", required=True, help="Path to the source .db/.sqlite/.csv/.json/.jsonl file")
    parser.add_argument("--mapping", required=True, help="Path to the REVIEWED mapping.json (from data:inspect)")
    parser.add_argument(
        "--source-label",
        required=True,
        help="Dataset name/URL, e.g. 'Kaggle: uk-ireland-horse-racing-results' — stored on every "
        "DataProvenance row's sourceUrl for traceability",
    )
    parser.add_argument(
        "--provenance-status",
        required=True,
        choices=VALID_PROVENANCE_STATUSES,
        help="What's known about this dataset's reuse rights — no default, must be stated explicitly",
    )
    parser.add_argument("--source-type", default="REAL", choices=["REAL", "SYNTHETIC", "SAMPLE"])
    parser.add_argument("--from", dest="from_date", required=True, type=_parse_date)
    parser.add_argument("--to", dest="to_date", required=True, type=_parse_date)
    parser.add_argument("--idempotency-key", default=None)
    args = parser.parse_args()

    file_path = Path(args.file).expanduser()
    mapping_path = Path(args.mapping).expanduser()

    if not file_path.exists():
        print(f"File not found: {file_path}\n\nDownload the dataset manually and provide the local file path.", file=sys.stderr)
        sys.exit(2)
    if not mapping_path.exists():
        print(f"Mapping file not found: {mapping_path}\n\nRun `npm run data:inspect -- --file {file_path}` first.", file=sys.stderr)
        sys.exit(2)

    conn = db.get_connection()

    idempotency_key = args.idempotency_key or f"free-dataset-{file_path.name}-{args.from_date}-{args.to_date}"

    print(f"Importing {file_path} (mapping: {mapping_path}) as source_type={args.source_type}, "
          f"provenance_status={args.provenance_status} ...")

    try:
        outcome = import_free_dataset(
            conn,
            mapping_path,
            source_type=args.source_type,
            provenance_status=args.provenance_status,
            source_label=args.source_label,
            start_date=args.from_date,
            end_date=args.to_date,
            idempotency_key=idempotency_key,
        )
    except MappingNotConfirmedError as exc:
        print(f"\n{exc}", file=sys.stderr)
        sys.exit(2)

    for warning in outcome.warnings:
        print(f"\n*** WARNING: {warning} ***")

    result = outcome.result
    print(f"\nImportBatch {result.import_batch_id}: {result.status}")
    print(
        f"  processed={result.processed_rows} success={result.success_count} "
        f"duplicates={result.duplicate_rows} errors={result.error_count}"
    )
    if result.errors:
        print("  Failed records:")
        for error in result.errors[:20]:
            print(f"    index={error.index} provider_race_id={error.provider_race_id} error={error.message}")
        if len(result.errors) > 20:
            print(f"    ... and {len(result.errors) - 20} more")

    print(
        "\nNext steps: run the temporal leakage auditor "
        "(racingedge_data.leakage_audit.audit_training_data — runs automatically at the start of "
        "`python -m racingedge_model.train`), then create a DatasetVersion and check the "
        "minimum-real-data gate. See REAL_FREE_BASELINE.md."
    )

    if result.status == "FAILED":
        sys.exit(1)


if __name__ == "__main__":
    main()
