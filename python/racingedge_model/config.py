"""Central configuration: paths, versioning, and tunable thresholds.

Every "magic number" that affects feature calculation or model behaviour is
defined here, in one place, so it is auditable and can be cited in
documentation and tests rather than buried inline.
"""

from __future__ import annotations

import os
from pathlib import Path

PYTHON_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = PYTHON_DIR.parent

ARTIFACTS_DIR = PYTHON_DIR / "artifacts"
REPORTS_DIR = PYTHON_DIR / "reports"

# Bump this whenever a feature's calculation logic changes in a way that
# would make old ModelVersion artifacts incompatible with freshly-computed
# features. Stored on every ModelVersion row (featureSetVersion).
FEATURE_SET_VERSION = "2026.08-v1"

# Reproducibility.
RANDOM_SEED = 42

# Bookmaker place depths supported by the place-probability models.
PLACE_DEPTHS: list[int] = [2, 3, 4, 5, 6]

# Rolling windows (by number of runs) used for current-form features.
FORM_WINDOWS: list[int] = [3, 5, 10]

# Trainer/jockey rolling windows, in days before the target race.
TRAINER_JOCKEY_WINDOWS_DAYS: list[int] = [14, 30]

# --- Minimum sample size thresholds (avoid tiny samples dominating) ---
#
# Below these thresholds, the corresponding feature is either withheld
# (feature value = NaN, with a *_available flag = 0) or blended towards a
# neutral prior via additive (Laplace-style) smoothing — see
# features/trainer_jockey.py and features/draw.py for exactly which.

# Draw-bias features require this many historical runners in the same
# (course, distance-band, field-size-band) bucket before being trusted.
MIN_SAMPLES_DRAW_BIAS = 30

# Trainer/jockey rolling strike-rate features are smoothed with this many
# "virtual" prior runs at a neutral (population-average) strike rate. A
# trainer with 1 run in the window is barely different from prior; a
# trainer with 100 runs is barely affected by the prior.
TRAINER_JOCKEY_SMOOTHING_PRIOR_RUNS = 8

# Course/distance/going record features (win %, place %) use the same
# additive smoothing, with this many virtual prior runs.
RECORD_SMOOTHING_PRIOR_RUNS = 4

# A horse needs at least this many prior runs for pace transition/late-
# sustainability features to be considered "available" rather than NaN.
MIN_RUNS_FOR_PACE_FEATURES = 2

# Population-average finishing metrics used as smoothing priors and as
# fallback values when a horse/trainer/jockey has zero history. Computed
# once from the training set at fit time in practice; these are the
# cold-start defaults used before any dataset-specific prior is available.
DEFAULT_WIN_RATE_PRIOR = 0.10
DEFAULT_PLACE_RATE_PRIOR = 0.30


def resolve_db_path() -> Path:
    """Resolves the SQLite database path the same way the Next.js app does.

    Honours DATABASE_URL="file:./dev.db" (relative to the project root) if
    set, otherwise falls back to <project root>/dev.db.
    """

    database_url = os.environ.get("DATABASE_URL", "file:./dev.db")
    raw_path = database_url.removeprefix("file:")
    path = Path(raw_path)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path


DB_PATH = resolve_db_path()
