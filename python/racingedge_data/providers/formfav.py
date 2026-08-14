"""Placeholder adapter for **FormFav** (formfav.com) — deliberately NOT
implemented as a live client.

## Why this is a placeholder, not a real adapter

The task brief was explicit: implement a FormFav adapter *"if official
current documentation confirms a free API tier. Use only the official
FormFav API/docs."* Direct access to `https://formfav.com/docs` (and every
other `formfav.com` page) returned `EGRESS_BLOCKED` from this environment's
network egress policy — the same restriction encountered with
`api.theracingapi.com` in Phase 3B. Unlike Racing API, where the vendor's
own published example scripts on GitHub gave genuine (if secondary)
verification of the base URL, endpoints, and several field names,
**no equivalent secondary source was found for FormFav** — web search
results only surfaced marketing-page claims ("free racing data feed",
"RESTful JSON API", "24+ countries", "no contracts required") with no
endpoint paths, authentication header format, or response field names
anywhere reachable from this environment.

Building a "real" HTTP client under those conditions would mean guessing
essentially the entire contract (base URL, endpoint paths, auth scheme,
every field name) and presenting it as if verified — which is exactly the
fabrication this project's brief prohibits. So this file intentionally
contains no live client, no endpoint paths, and no field-mapping logic: all
three would be invented.

## What would unblock this

1. Direct (unblocked) access to `https://formfav.com/docs`, OR
2. A maintainer with access pasting the relevant documentation excerpts
   (base URL, authentication method, endpoint paths, example JSON
   responses for form/career-stats/jockey-stats/trainer-stats/course-stats)
   so the real contract can be implemented and verified the same way
   `racing_api.py` was.

Once either exists, this module should gain the same shape as
`racing_api.py` / `timeform.py`: `FixtureBackedProvider` subclass(es)
implementing whichever of `HistoricalResultsProvider` (form/career stats)
this API's actually-confirmed capabilities support, with credentials read
from the `FORMFAV_API_KEY` environment variable per the brief. Per the
brief, FormFav should be treated as an ENRICHMENT provider — supplementary
form/stats data layered onto races/runners already imported via Racing API
or a free dataset — not a race-card source of its own, since its
racecard/results coverage for UK & Ireland was never confirmed.
"""

from __future__ import annotations

import os
from typing import Optional

from racingedge_data.providers.base import ProviderConfigurationError

REQUIRED_ENV_VAR = "FORMFAV_API_KEY"


class FormFavNotImplementedError(ProviderConfigurationError):
    """Raised by every method on this placeholder — see module docstring
    for exactly why no real client exists here yet."""


class FormFavProvider:
    """Placeholder only. See module docstring — this class deliberately
    implements no provider interface and makes no network call."""

    name = "formfav"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get(REQUIRED_ENV_VAR)

    def _not_implemented(self) -> FormFavNotImplementedError:
        return FormFavNotImplementedError(
            "FormFav has no real adapter implementation in this build. "
            f"https://formfav.com/docs could not be reached from this environment "
            "(network egress blocked) and no secondary source confirmed the actual API "
            "contract (endpoints, field names). Implementing this without that would mean "
            "fabricating the contract, which this project does not do. See "
            "FREE_DATA_SOURCES.md and this module's docstring for exactly what's needed to "
            f"unblock it. Credential this project expects once unblocked: {REQUIRED_ENV_VAR}."
        )

    def fetch_form_stats(self, *args, **kwargs):
        raise self._not_implemented()

    def fetch_career_stats(self, *args, **kwargs):
        raise self._not_implemented()

    def fetch_jockey_stats(self, *args, **kwargs):
        raise self._not_implemented()

    def fetch_trainer_stats(self, *args, **kwargs):
        raise self._not_implemented()

    def fetch_course_stats(self, *args, **kwargs):
        raise self._not_implemented()
