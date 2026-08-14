"""CLI: inspect a user-supplied historical racing dataset file and propose
a column-role mapping — the first step of the Phase 3C £0-data-cost import
workflow. Makes no network call, imports nothing, fabricates nothing.

Run:
  npm run data:inspect -- --file ~/Downloads/raceform.db
  # or directly:
  python -m racingedge_data.cli.inspect_dataset --file ~/Downloads/raceform.db

Writes two files next to a report you specify (or alongside the input file
by default):
  <name>.inspection.json  — the full profile (tables, columns, row counts,
                             date coverage, dtype, sample values)
  <name>.mapping.json     — the REVIEWABLE proposed mapping. Edit this file
                             to correct/confirm ambiguous columns, then pass
                             it to `data:import-free` (see
                             racingedge_data.importers.free_dataset_importer).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from racingedge_data.inspector import inspect_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", required=True, help="Path to a .db/.sqlite/.csv/.json/.jsonl file")
    parser.add_argument("--out-prefix", default=None, help="Output file prefix (default: alongside --file)")
    parser.add_argument("--sample-rows", type=int, default=5000)
    args = parser.parse_args()

    file_path = Path(args.file).expanduser()
    if not file_path.exists():
        print(
            f"File not found: {file_path}\n\n"
            "Download the dataset manually and provide the local file path. "
            "This tool does not download anything automatically.",
            file=sys.stderr,
        )
        sys.exit(2)

    print(f"Inspecting {file_path} ...")
    report = inspect_file(file_path, sample_rows=args.sample_rows)

    out_prefix = Path(args.out_prefix) if args.out_prefix else file_path.with_suffix("")
    inspection_path = Path(f"{out_prefix}.inspection.json")
    mapping_path = Path(f"{out_prefix}.mapping.json")

    inspection_path.write_text(report.to_json())
    report.write_mapping_template(mapping_path)

    print(f"\nFormat: {report.source_format}")
    for table in report.tables:
        print(f"\nTable '{table.name}' ({table.likely_kind}): {table.row_count:,} rows")
        if table.date_range:
            print(f"  date coverage: {table.date_range[0]} .. {table.date_range[1]} (column: {table.date_column})")
        high = [c for c in table.columns if c.confidence == "high"]
        medium = [c for c in table.columns if c.confidence == "medium"]
        low = [c for c in table.columns if c.confidence == "low"]
        unmapped = [c for c in table.columns if c.proposed_role is None]
        print(f"  columns: {len(table.columns)} total — {len(high)} high-confidence, {len(medium)} medium, "
              f"{len(low)} low-confidence, {len(unmapped)} unmapped")

    ambiguous = report.ambiguous_columns()
    print(f"\nWrote {inspection_path}")
    print(f"Wrote {mapping_path}")
    if ambiguous:
        print(
            f"\n{len(ambiguous)} column(s) need explicit review before import — see \"confirmed\": false "
            f"entries in {mapping_path}:"
        )
        for table_name, col_name in ambiguous[:30]:
            print(f"  {table_name}.{col_name}")
        if len(ambiguous) > 30:
            print(f"  ... and {len(ambiguous) - 30} more")
        print(
            "\nEdit the mapping file to correct/confirm these, then run:\n"
            f"  npm run data:import-free -- --file {file_path} --mapping {mapping_path}"
        )
    else:
        print(
            "\nAll proposed columns are high-confidence. Review the mapping file anyway, then run:\n"
            f"  npm run data:import-free -- --file {file_path} --mapping {mapping_path}"
        )


if __name__ == "__main__":
    main()
