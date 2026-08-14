"""CLI: run the Phase 3D "click Import" pipeline from a terminal — the
developer/automation entry point for `racingedge_data.import_pipeline`.
The browser UI (`/data-sources`) is the primary way most users trigger
this; this command exists for scripting, large/unattended imports, and
testing, per the project's "command line remains available" requirement.

Run:
  # start a new job from a local file
  python -m racingedge_data.cli.run_import_job --source-id local-file \\
      --local-file /path/to/dataset.db --provenance-status USER_SUPPLIED \\
      --source-label "My dataset"

  # start a new job from a Kaggle dataset (requires a Kaggle connection)
  python -m racingedge_data.cli.run_import_job --source-id kaggle-uk-ire-historical \\
      --kaggle-dataset-ref owner/dataset-slug --provenance-status COMMUNITY_UNVERIFIED

  # start a new job from a direct URL
  python -m racingedge_data.cli.run_import_job --source-id user-url \\
      --download-url https://example.com/races.csv --provenance-status UNKNOWN

  # resume a job that paused for mapping review, after editing its mapping
  # file directly (or supplying a JSON patch via --confirm-mapping-json)
  python -m racingedge_data.cli.run_import_job --job-id <id> --resume
"""

from __future__ import annotations

import argparse
import json
import sys

from racingedge_data.import_pipeline import (
    apply_mapping_review,
    confirm_mapping_and_resume,
    create_import_job,
    get_import_job,
    run_import_job,
)
from racingedge_model.db import get_connection


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--job-id", default=None, help="Resume an existing job instead of creating one")
    parser.add_argument("--resume", action="store_true", help="Resume --job-id as-is (mapping file already edited)")
    parser.add_argument(
        "--apply-mapping-json",
        default=None,
        help=(
            'Path to a JSON file: {"table.column": {"role": "...", "confirmed": true}, ...} — '
            "applies the patch to the job's mapping file and exits WITHOUT running the pipeline "
            "(fast, synchronous). Pair with a separate `--job-id <id>` (no other flags) call to "
            "actually resume — this is the two-call shape the Next.js server action uses."
        ),
    )
    parser.add_argument(
        "--confirm-mapping-json",
        default=None,
        help='Path to a JSON file: {"table.column": {"role": "...", "confirmed": true}, ...}',
    )

    parser.add_argument("--source-id", default=None, help="SourceCatalog id (see src/data/sourceCatalog.ts)")
    parser.add_argument("--local-file", default=None)
    parser.add_argument("--kaggle-dataset-ref", default=None, help='"owner/dataset-slug"')
    parser.add_argument("--download-url", default=None)
    parser.add_argument("--source-label", default=None)
    parser.add_argument(
        "--provenance-status",
        default=None,
        choices=["VERIFIED_OPEN", "PUBLIC_RESEARCH", "COMMUNITY_UNVERIFIED", "USER_SUPPLIED", "UNKNOWN", "RESTRICTED"],
    )
    parser.add_argument("--source-type", default="REAL", choices=["REAL", "SYNTHETIC", "SAMPLE"])
    parser.add_argument("--from", dest="date_from", default=None)
    parser.add_argument("--to", dest="date_to", default=None)
    parser.add_argument(
        "--create-only",
        action="store_true",
        help=(
            "Only create the job row (a fast, synchronous INSERT) and print {\"job_id\": \"...\"} "
            "as JSON — does not run the pipeline. Used by the Next.js server action, which creates "
            "the job synchronously (so it can return a job id to the browser immediately) and then "
            "spawns a separate detached process to actually run it: "
            "`run_import_job.py --job-id <id>`."
        ),
    )
    args = parser.parse_args()

    conn = get_connection()
    try:
        if args.create_only:
            if not args.source_id:
                print("--source-id is required with --create-only", file=sys.stderr)
                sys.exit(2)
            job_id = create_import_job(
                conn,
                source_id=args.source_id,
                source_label=args.source_label,
                provenance_status=args.provenance_status,
                download_url=args.download_url,
                kaggle_dataset_ref=args.kaggle_dataset_ref,
                local_file_path=args.local_file,
                source_type=args.source_type,
                date_from=args.date_from,
                date_to=args.date_to,
            )
            conn.commit()
            print(json.dumps({"job_id": job_id}))
            return
        elif args.apply_mapping_json:
            if not args.job_id:
                print("--apply-mapping-json requires --job-id", file=sys.stderr)
                sys.exit(2)
            updates = json.loads(open(args.apply_mapping_json).read())
            apply_mapping_review(conn, args.job_id, updates)
            conn.commit()
            print(json.dumps({"job_id": args.job_id, "applied": True}))
            return
        elif args.confirm_mapping_json:
            if not args.job_id:
                print("--confirm-mapping-json requires --job-id", file=sys.stderr)
                sys.exit(2)
            updates = json.loads(open(args.confirm_mapping_json).read())
            confirm_mapping_and_resume(conn, args.job_id, updates)
            conn.commit()
        elif args.resume or args.job_id:
            if not args.job_id:
                print("--resume requires --job-id", file=sys.stderr)
                sys.exit(2)
            run_import_job(conn, args.job_id)
            conn.commit()
        else:
            if not args.source_id:
                print("--source-id is required to start a new job", file=sys.stderr)
                sys.exit(2)
            job_id = create_import_job(
                conn,
                source_id=args.source_id,
                source_label=args.source_label,
                provenance_status=args.provenance_status,
                download_url=args.download_url,
                kaggle_dataset_ref=args.kaggle_dataset_ref,
                local_file_path=args.local_file,
                source_type=args.source_type,
                date_from=args.date_from,
                date_to=args.date_to,
            )
            conn.commit()
            print(f"Created ImportJob {job_id}")
            run_import_job(conn, job_id)
            conn.commit()
            args.job_id = job_id
    except Exception as exc:
        print(f"\nImport job failed: {exc}", file=sys.stderr)
        conn.commit()  # keep whatever status the pipeline already recorded
        sys.exit(1)
    finally:
        conn.close()

    job = get_connection()
    try:
        row = get_import_job(job, args.job_id)
    finally:
        job.close()

    print(f"\nJob {row['id']}: status={row['status']}")
    if row["status"] == "AWAITING_MAPPING_REVIEW":
        print(f"Mapping needs review: {row['mappingFilePath']}")
        print(
            "Edit the mapping file directly, or supply a JSON patch via --confirm-mapping-json, "
            f"then re-run with --job-id {row['id']} --resume."
        )
    elif row["status"] == "COMPLETED":
        print(f"Races imported: {row['racesImported']}, runners imported: {row['runnersImported']}")
        print(f"DatasetVersion: {row['datasetVersionId']}")
    elif row["status"] == "FAILED":
        print(f"Error: {row['errorMessage']}")


if __name__ == "__main__":
    main()
