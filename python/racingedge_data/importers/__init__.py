"""Streaming, chunked, resumable import pipeline.

`import_runner.import_races` is the main entry point — it drives a
`RaceDataProvider` (see `racingedge_data.providers`) one race at a time and
writes Race/Horse/Runner/RacePlaceTerms rows plus DataProvenance rows,
tracking progress/duplicates/errors on the `ImportBatch` row as it goes.
`file_io.open_source` builds the right provider for a CSV/JSON/JSONL file
(transparently handling `.gz` compression) from a path alone.
"""
