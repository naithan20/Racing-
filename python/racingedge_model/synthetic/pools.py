"""Static name pools for the synthetic historical dataset.

Every entity generated from these pools is clearly synthetic:
  - Horse.countryBred = "SYN" for every synthetic-history horse
  - Race.racecourse is always prefixed "Synthetic "
  - Race.raceName is always prefixed "SYNTHETIC HISTORY —"
  - trainerName / jockeyName are drawn from "Synth Trainer NN" / "Synth Jockey NN"

These prefixes double as the cleanup filter used by
`generate_history.py --reset` (DELETE races/horses matching them) so the
generator is safely re-runnable.
"""

from __future__ import annotations

HORSE_NAME_PARTS_A = [
    "Vector", "Ledger", "Quantum", "Meridian", "Northern", "Silver", "Amber",
    "Copper", "Winter", "Summer", "Autumn", "Golden", "Iron", "Crimson",
    "Cobalt", "Azure", "Marble", "Granite", "Velvet", "Echo", "Cipher",
    "Signal", "Compass", "Horizon", "Lantern", "Ember", "Frost", "Storm",
    "Harbour", "Ridge", "Hollow", "Bramble", "Thistle", "Willow", "Cinder",
]
HORSE_NAME_PARTS_B = [
    "Point", "Drive", "Reach", "Wager", "Runner", "Chaser", "Dancer",
    "Charger", "Spirit", "Legacy", "Fortune", "Voyage", "Ascent", "Flight",
    "Gallop", "Stride", "Crossing", "Passage", "Anthem", "Verdict",
    "Outcome", "Margin", "Yield", "Return", "Rally", "Advance", "Pursuit",
    "Momentum", "Trajectory", "Bearing", "Course", "Pathway", "Circuit",
    "Ridgeline", "Overture",
]

TRAINER_NAMES = [f"Synth Trainer {i:02d}" for i in range(1, 16)]
JOCKEY_NAMES = [f"Synth Jockey {i:02d}" for i in range(1, 21)]
OWNER_NAME = "Synthetic Data Partnership"

# Each course fixed to a surface/type so distance ranges stay realistic.
FLAT_TURF_COURSES = [
    "Synthetic Meridian",
    "Synthetic Bridgewater",
    "Synthetic Northfield",
    "Synthetic Coastal Vale",
]
FLAT_AW_COURSES = [
    "Synthetic Silverdale",
    "Synthetic Redgate",
]
JUMPS_COURSES = [
    "Synthetic Thornbury",
    "Synthetic Hollow Hill",
    "Synthetic Kestrel Moor",
    "Synthetic Fenwick",
    "Synthetic Amberley",
    "Synthetic Oakhurst",
]

COUNTRY_FOR_COURSE = {
    "Synthetic Meridian": "GB",
    "Synthetic Bridgewater": "GB",
    "Synthetic Northfield": "IRE",
    "Synthetic Coastal Vale": "FR",
    "Synthetic Silverdale": "GB",
    "Synthetic Redgate": "GB",
    "Synthetic Thornbury": "GB",
    "Synthetic Hollow Hill": "IRE",
    "Synthetic Kestrel Moor": "GB",
    "Synthetic Fenwick": "GB",
    "Synthetic Amberley": "IRE",
    "Synthetic Oakhurst": "GB",
}

TURF_GOINGS = ["Firm", "Good to Firm", "Good", "Good to Soft", "Soft", "Heavy"]
AW_GOINGS = ["Standard", "Standard to Slow", "Slow"]

RACE_NAME_TEMPLATES = [
    "SYNTHETIC HISTORY — {course} {race_type}",
]
