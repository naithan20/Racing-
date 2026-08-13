import shutil
import sqlite3

import pytest

from racingedge_model import db
from racingedge_model.config import DB_PATH
from racingedge_model.dataset import build_training_dataset


@pytest.fixture(scope="session")
def full_dataset():
    """Builds the training dataset ONCE from the real project database
    (read-only) and shares it across every test that just needs to inspect
    dataset shape/targets/splits — rebuilding it per-test would be slow."""
    conn = db.get_connection()
    return build_training_dataset(conn, verbose=False)


@pytest.fixture
def tmp_db_conn(tmp_path):
    """A private, mutable COPY of the project database, isolated from the
    real dev.db. Used by tests (e.g. the leakage test) that need to mutate
    data — never mutate the real database in a test."""
    if not DB_PATH.exists():
        pytest.skip(f"No database found at {DB_PATH} — run `npm run db:migrate && npm run model:history` first.")
    tmp_path_db = tmp_path / "test_copy.db"
    shutil.copy(DB_PATH, tmp_path_db)
    conn = sqlite3.connect(str(tmp_path_db))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
