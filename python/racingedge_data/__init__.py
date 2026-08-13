"""RacingEdge Phase 3A — real racing data infrastructure.

Sibling package to `racingedge_model` (Phase 2). This package owns
provider-agnostic ingestion, canonical data shapes, provenance tracking,
point-in-time reconstruction, entity resolution, dataset versioning, and the
temporal leakage auditor. It deliberately does NOT alter any Phase 2
modelling code — `racingedge_model` consumes REAL data produced here via the
same SQLite database, unchanged.

Reuses `racingedge_model.db` for the SQLite connection and Prisma-compatible
datetime formatting rather than duplicating it, since both packages read and
write the exact same database file.
"""
