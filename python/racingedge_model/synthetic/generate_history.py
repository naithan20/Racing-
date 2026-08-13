"""Generates a synthetic historical racing dataset directly into the
project's SQLite database, so the Phase 2 modelling pipeline has enough
history to compute meaningful features and run genuine (if synthetic)
backtests.

Every row this script creates is unambiguously tagged as synthetic:
  - Horse.countryBred == "SYN"
  - Race.racecourse starts with "Synthetic "
  - Race.raceName starts with "SYNTHETIC HISTORY —"
  - trainerName / jockeyName drawn from "Synth Trainer NN" / "Synth Jockey NN"

Any model trained wholly or partly on this data MUST be labelled, in the UI
and in ModelVersion.isSynthetic, as:

    SYNTHETIC TEST MODEL — NOT FOR BETTING USE

Design notes (see also docs/MODEL_CARD.md):
  - Outcomes are generated via a sequential Plackett-Luce model over a
    latent "true ability" score that the model never observes directly.
  - Observable features (rating, market price, form) are noisy, lagged
    functions of that latent ability — not the ability itself — so the
    pipeline is genuinely tested rather than trivially solvable.
  - Official ratings evolve causally: a horse's rating going INTO a race is
    only ever a function of races BEFORE it.
  - The market price also carries independent noise, so the model is not
    artificially guaranteed to "beat" the market — any edge found during
    backtesting is genuine (within the limits of a synthetic simulation).

Usage:
    python -m racingedge_model.synthetic.generate_history [--reset] [--races N]
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np

from racingedge_model import db
from racingedge_model.going import going_softness_index
from racingedge_model.ids import new_id
from racingedge_model.synthetic import pools
from racingedge_model.synthetic.simulate import (
    approximate_beaten_lengths,
    class_or_band,
    plackett_luce_order,
)

SEED = 20260813
N_HORSES_FLAT = 100
N_HORSES_JUMPS = 60
N_RACES = 190
HISTORY_DAYS = 300  # races span [today - HISTORY_DAYS, today - 1]

PACE_ARCHETYPES = ["LEADER", "PRONOUNCED_PACE", "MIDDIVISION", "HOLD_UP"]
HEADGEAR_CODES = ["B", "V", "CP", "T", "H"]


@dataclass
class HorseState:
    id: str
    name: str
    year_of_birth: int
    sex: str
    flat_jumps: str
    trainer_name: str
    jockey_name: str
    true_ability: float
    ability_trend_per_day: float
    preferred_distance_furlongs: float
    preferred_going_softness: float  # 0 (firm-loving) .. 1 (soft-loving)
    surface: str  # TURF or ALL_WEATHER (flat horses may run either)
    pace_archetype: str
    headgear: str | None
    current_or: float
    career_starts: int = 0
    last_run_date: datetime | None = None
    or_history: list[tuple[datetime, float]] = field(default_factory=list)


def ability_at(horse: HorseState, at_date: datetime, base_date: datetime, rng: np.random.Generator) -> float:
    days_elapsed = (at_date - base_date).days
    drift = horse.ability_trend_per_day * days_elapsed
    race_day_noise = rng.normal(0, 0.12)
    return horse.true_ability + drift + race_day_noise


def make_horse_pool(rng: np.random.Generator, base_date: datetime) -> list[HorseState]:
    horses: list[HorseState] = []
    name_a = list(pools.HORSE_NAME_PARTS_A)
    name_b = list(pools.HORSE_NAME_PARTS_B)
    used_names: set[str] = set()

    def draw_name() -> str:
        for _ in range(200):
            candidate = f"{rng.choice(name_a)} {rng.choice(name_b)}"
            if candidate not in used_names:
                used_names.add(candidate)
                return candidate
        # Extremely unlikely fallback if the pool is exhausted.
        candidate = f"{rng.choice(name_a)} {rng.choice(name_b)} {rng.integers(2, 999)}"
        used_names.add(candidate)
        return candidate

    def make_one(flat_jumps: str) -> HorseState:
        age_years = int(rng.integers(4, 11)) if flat_jumps == "JUMPS" else int(rng.integers(3, 9))
        year_of_birth = base_date.year - age_years
        sex = str(rng.choice(["GELDING", "GELDING", "MARE", "COLT", "FILLY"]))
        trainer = str(rng.choice(pools.TRAINER_NAMES))
        jockey = str(rng.choice(pools.JOCKEY_NAMES))
        true_ability = float(rng.normal(0, 1.0))
        trend = float(rng.normal(0, 0.0015))  # slow fitness drift over the dataset window
        pref_distance = (
            float(rng.uniform(5, 20)) if flat_jumps == "FLAT" else float(rng.uniform(16, 34))
        )
        pref_going_softness = float(rng.uniform(0, 1))
        surface = "TURF" if flat_jumps == "JUMPS" else str(rng.choice(["TURF", "ALL_WEATHER"], p=[0.7, 0.3]))
        archetype = str(rng.choice(PACE_ARCHETYPES, p=[0.18, 0.32, 0.32, 0.18]))
        headgear = str(rng.choice(HEADGEAR_CODES)) if rng.random() < 0.28 else None

        band = class_or_band(flat_jumps, int(rng.integers(2, 6)))
        starting_or = float(rng.uniform(band[0], band[1]))

        return HorseState(
            id=new_id(),
            name=draw_name(),
            year_of_birth=year_of_birth,
            sex=sex,
            flat_jumps=flat_jumps,
            trainer_name=trainer,
            jockey_name=jockey,
            true_ability=true_ability,
            ability_trend_per_day=trend,
            preferred_distance_furlongs=pref_distance,
            preferred_going_softness=pref_going_softness,
            surface=surface,
            pace_archetype=archetype,
            headgear=headgear,
            current_or=starting_or,
        )

    horses.extend(make_one("FLAT") for _ in range(N_HORSES_FLAT))
    horses.extend(make_one("JUMPS") for _ in range(N_HORSES_JUMPS))
    return horses


def pick_going(surface: str, rng: np.random.Generator) -> str:
    options = pools.TURF_GOINGS if surface != "ALL_WEATHER" else pools.AW_GOINGS
    return str(rng.choice(options))


def pick_race_class(flat_jumps: str, rng: np.random.Generator) -> int:
    if flat_jumps == "FLAT":
        classes = [1, 2, 3, 4, 5, 6, 7]
        weights = [0.04, 0.10, 0.18, 0.24, 0.22, 0.14, 0.08]
    else:
        classes = [1, 2, 3, 4, 5, 6]
        weights = [0.05, 0.12, 0.20, 0.28, 0.22, 0.13]
    return int(rng.choice(classes, p=weights))


def pick_distance(flat_jumps: str, rng: np.random.Generator) -> float:
    if flat_jumps == "FLAT":
        return round(float(rng.uniform(5, 20)) * 2) / 2  # nearest half furlong
    return round(float(rng.uniform(16, 34)) * 2) / 2


def effective_weight_lbs(flat_jumps: str, race_class: int, or_gap_from_top: float, rng: np.random.Generator) -> int:
    base_top = 154 if flat_jumps == "JUMPS" else 133
    weight = base_top - or_gap_from_top * 0.9 + rng.normal(0, 1.5)
    floor = 119 if flat_jumps == "JUMPS" else 112
    return int(np.clip(round(weight), floor, base_top))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="delete existing synthetic-history rows first")
    parser.add_argument("--races", type=int, default=N_RACES)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    conn = db.get_connection()

    if args.reset:
        _reset_synthetic_history(conn)

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    base_date = today - timedelta(days=HISTORY_DAYS)

    horses = make_horse_pool(rng, base_date)

    bookmaker_ids = _ensure_bookmakers(conn)

    with db.transaction(conn):
        for h in horses:
            conn.execute(
                'INSERT INTO "Horse" (id, isSampleData, name, countryBred, yearOfBirth, sex, sireName, '
                "damName, damsireName, trainerName, ownerName, createdAt, updatedAt) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    h.id,
                    1,
                    h.name,
                    "SYN",
                    h.year_of_birth,
                    h.sex,
                    None,
                    None,
                    None,
                    h.trainer_name,
                    pools.OWNER_NAME,
                    db.to_prisma_datetime(datetime.now(timezone.utc)),
                    db.to_prisma_datetime(datetime.now(timezone.utc)),
                ),
            )

    # Spread N races across HISTORY_DAYS with some days having 0-2 races.
    race_dates = sorted(
        base_date + timedelta(days=int(d))
        for d in rng.integers(0, HISTORY_DAYS, size=args.races)
    )

    races_written = 0
    runners_written = 0

    with db.transaction(conn):
        for race_date in race_dates:
            result = _generate_one_race(conn, rng, race_date, base_date, horses, bookmaker_ids)
            if result is None:
                continue
            races_written += 1
            runners_written += result

        _write_evidence_profiles(conn, horses, today)

    print(
        json.dumps(
            {
                "races_written": races_written,
                "runners_written": runners_written,
                "horses_in_pool": len(horses),
                "date_range": [base_date.date().isoformat(), (today - timedelta(days=1)).date().isoformat()],
            },
            indent=2,
        )
    )


def _reset_synthetic_history(conn) -> None:
    with db.transaction(conn):
        conn.execute('DELETE FROM "Race" WHERE racecourse LIKE \'Synthetic %\'')
        conn.execute('DELETE FROM "Horse" WHERE countryBred = \'SYN\'')
    print("Reset: deleted existing synthetic-history races and horses.")


def _ensure_bookmakers(conn) -> dict[str, str]:
    names = ["Bet365 (sample)", "Sky Bet (sample)", "Paddy Power (sample)", "Betfair Exchange (sample)"]
    ids: dict[str, str] = {}
    with db.transaction(conn):
        for name in names:
            row = conn.execute('SELECT id FROM "Bookmaker" WHERE name = ?', (name,)).fetchone()
            if row:
                ids[name] = row["id"]
                continue
            bookmaker_id = new_id()
            conn.execute(
                'INSERT INTO "Bookmaker" (id, name, isExchange, createdAt) VALUES (?, ?, ?, ?)',
                (bookmaker_id, name, int("Exchange" in name), db.to_prisma_datetime(datetime.now(timezone.utc))),
            )
            ids[name] = bookmaker_id
    return ids


def _generate_one_race(conn, rng, race_date, base_date, horses, bookmaker_ids) -> int | None:
    flat_jumps = "FLAT" if rng.random() < (N_HORSES_FLAT / (N_HORSES_FLAT + N_HORSES_JUMPS)) else "JUMPS"
    surface = "TURF" if flat_jumps == "JUMPS" else str(rng.choice(["TURF", "ALL_WEATHER"], p=[0.7, 0.3]))

    if flat_jumps == "JUMPS":
        course = str(rng.choice(pools.JUMPS_COURSES))
    elif surface == "TURF":
        course = str(rng.choice(pools.FLAT_TURF_COURSES))
    else:
        course = str(rng.choice(pools.FLAT_AW_COURSES))

    country = pools.COUNTRY_FOR_COURSE[course]
    going = pick_going(surface, rng)
    race_class = pick_race_class(flat_jumps, rng)
    distance = pick_distance(flat_jumps, rng)
    handicap_type = "HANDICAP" if rng.random() < 0.58 else "NON_HANDICAP"
    age_restriction = "3yo+" if flat_jumps == "FLAT" else "4yo+"
    min_age = 3 if flat_jumps == "FLAT" else 4

    or_low, or_high = class_or_band(flat_jumps, race_class)
    margin = 10

    eligible = []
    for h in horses:
        if h.flat_jumps != flat_jumps:
            continue
        age = race_date.year - h.year_of_birth
        if age < min_age:
            continue
        if not (or_low - margin <= h.current_or <= or_high + margin):
            continue
        if h.last_run_date is not None:
            gap_days = (race_date - h.last_run_date).days
            if gap_days < 4:
                continue
            if gap_days < 12 and rng.random() > 0.15:
                continue
        eligible.append(h)

    if len(eligible) < 6:
        return None  # skip this date; pool too thin for a sensible field

    n_runners = int(rng.integers(6, min(16, len(eligible)) + 1))

    # Soft preference weighting toward horses suited to today's conditions —
    # not a hard filter, so distance/going *changes* still occur (needed for
    # those features to have signal at all).
    weights = np.array(
        [
            np.exp(
                -0.02 * abs(h.preferred_distance_furlongs - distance)
                - 0.6 * abs(h.preferred_going_softness - going_softness_index(going))
            )
            for h in eligible
        ]
    )
    weights = weights / weights.sum()
    chosen_idx = rng.choice(len(eligible), size=n_runners, replace=False, p=weights)
    field_horses = [eligible[i] for i in chosen_idx]

    race_id = new_id()
    race_name = f"SYNTHETIC HISTORY — {course.replace('Synthetic ', '')} {race_class_label(flat_jumps, race_class)}"
    each_way_fraction = float(rng.choice([0.2, 0.25]))
    bookmaker_places = int(rng.choice([2, 3, 3, 4, 4, 5]))

    conn.execute(
        'INSERT INTO "Race" (id, isSampleData, date, raceTime, racecourse, country, raceName, raceType, '
        "flatJumps, surface, distanceYards, distanceFurlongs, raceClass, gradeGroup, handicapType, "
        "ageRestriction, sexRestriction, numberOfRunners, going, goingDescription, railPosition, "
        "stallsPosition, weatherSummary, temperatureCelsius, windSummary, precipitationMm, "
        "prizeMoneyTotal, currency, eachWayFraction, bookmakerPlaces, extraPlaceFlag, raceStatus, "
        "resultStatus, createdAt, updatedAt, importBatchId) VALUES "
        "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            race_id,
            1,
            db.to_prisma_datetime(race_date),
            f"{int(rng.integers(12, 17)):02d}:{int(rng.choice([0, 10, 20, 30, 40, 50])):02d}",
            course,
            country,
            race_name,
            race_class_label(flat_jumps, race_class),
            flat_jumps,
            surface,
            int(distance * 220),
            distance,
            race_class,
            "Group 3" if race_class == 1 and rng.random() < 0.3 else None,
            handicap_type,
            age_restriction,
            None,
            n_runners,
            going,
            going,
            None,
            None,
            str(rng.choice(["Overcast", "Sunny intervals", "Rain", "Drizzle", "Clear"])),
            float(rng.uniform(4, 22)),
            None,
            None,
            float(rng.integers(4, 60)) * 1000,
            "GBP",
            each_way_fraction,
            bookmaker_places,
            0,
            "RESULTED",
            "CONFIRMED",
            db.to_prisma_datetime(datetime.now(timezone.utc)),
            db.to_prisma_datetime(datetime.now(timezone.utc)),
            None,
        ),
    )

    # Race-shape context: how many of today's field are natural pace-setters.
    n_leaders = sum(1 for h in field_horses if h.pace_archetype == "LEADER")
    n_prominent = sum(1 for h in field_horses if h.pace_archetype == "PRONOUNCED_PACE")
    pace_pressure = float(np.clip((n_leaders * 1.5 + n_prominent * 0.6) / max(n_runners, 1), 0, 1.5))

    strengths = np.zeros(n_runners)
    or_values = np.array([h.current_or for h in field_horses])
    field_mean_or = or_values.mean()
    weights_lbs = []

    for i, h in enumerate(field_horses):
        ability = ability_at(h, race_date, base_date, rng)
        going_fit = -0.9 * abs(h.preferred_going_softness - going_softness_index(going))
        distance_fit = -0.03 * abs(h.preferred_distance_furlongs - distance)
        or_gap_from_top = float(or_values.max() - h.current_or)
        w_lbs = effective_weight_lbs(flat_jumps, race_class, or_gap_from_top, rng)
        weights_lbs.append(w_lbs)
        weight_effect = -0.01 * (w_lbs - np.mean([effective_weight_lbs(flat_jumps, race_class, float(or_values.max() - hh.current_or), rng) for hh in [h]]))
        # Pace interaction: hold-up horses benefit when pace pressure is high
        # (closers profit from a fast, unsustainable pace); prominent/leader
        # types are hurt by high pressure (burn-out risk); mid-division is
        # roughly neutral. This is a deliberately small, documented effect.
        if h.pace_archetype == "HOLD_UP":
            pace_interaction = 0.18 * pace_pressure
        elif h.pace_archetype in ("LEADER", "PRONOUNCED_PACE"):
            pace_interaction = -0.12 * pace_pressure
        else:
            pace_interaction = 0.0

        race_noise = rng.normal(0, 0.55)
        strengths[i] = ability + going_fit + distance_fit + weight_effect + pace_interaction + race_noise

    order = plackett_luce_order(strengths, rng)
    beaten = approximate_beaten_lengths(strengths, order, rng)

    # Market: correlated with strength but with independent noise + overround
    # — the market is informative but not omniscient, and not identical to
    # the model's information set.
    market_noise_close = rng.normal(0, 0.35, size=n_runners)
    market_noise_open = rng.normal(0, 0.55, size=n_runners)
    close_probs = _softmax(0.85 * strengths + market_noise_close)
    open_probs = _softmax(0.85 * strengths + market_noise_open)
    overround = 1.12
    close_probs_book = close_probs * overround
    open_probs_book = open_probs * overround

    draws = None
    if flat_jumps == "FLAT":
        draws = list(rng.permutation(np.arange(1, n_runners + 1)))

    place_terms_bookmakers = list(rng.choice(list(bookmaker_ids.keys()), size=min(2, len(bookmaker_ids)), replace=False))
    for bm_name in place_terms_bookmakers:
        conn.execute(
            'INSERT INTO "RacePlaceTerms" (id, raceId, bookmakerId, places, eachWayFraction, extraPlaces, terms, createdAt) '
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                new_id(),
                race_id,
                bookmaker_ids[bm_name],
                bookmaker_places if bm_name == place_terms_bookmakers[0] else max(2, bookmaker_places - 1),
                each_way_fraction,
                int(bookmaker_places >= 5),
                None,
                db.to_prisma_datetime(datetime.now(timezone.utc)),
            ),
        )

    finishing_position_by_slot = {slot: pos + 1 for pos, slot in enumerate(order)}

    for i, h in enumerate(field_horses):
        finishing_position = finishing_position_by_slot[i]
        sp_decimal = round(float(1 / close_probs_book[i]), 2)
        open_decimal = round(float(1 / open_probs_book[i]), 2)
        headgear = h.headgear
        first_time_headgear = headgear is not None and rng.random() < (0.12 if h.career_starts > 0 else 0.5)
        jockey_claim = int(rng.choice([0, 0, 0, 3, 5, 7], p=[0.55, 0.15, 0.1, 0.1, 0.06, 0.04]))
        draw = int(draws[i]) if draws is not None else None
        days_since_last = (race_date - h.last_run_date).days if h.last_run_date else None

        runner_id = new_id()
        conn.execute(
            'INSERT INTO "Runner" (id, isSampleData, raceId, horseId, clothNumber, draw, ageAtRace, '
            "weightStone, weightPounds, weightLbsTotal, officialRating, racingPostRating, timeformRating, "
            "topspeedRating, jockeyName, jockeyClaimLbs, trainerName, headgear, firstTimeHeadgear, "
            "daysSinceLastRun, currentOddsDecimal, currentOddsFractional, openingOddsDecimal, "
            "startingPriceDecimal, exchangePriceDecimal, nonRunner, favouriteRank, createdAt, updatedAt) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                runner_id,
                1,
                race_id,
                h.id,
                i + 1,
                draw,
                race_date.year - h.year_of_birth,
                None,
                None,
                weights_lbs[i],
                round(h.current_or),
                None,
                None,
                None,
                h.jockey_name,
                jockey_claim if jockey_claim > 0 else None,
                h.trainer_name,
                headgear,
                int(first_time_headgear),
                days_since_last,
                sp_decimal,
                None,
                open_decimal,
                sp_decimal,
                round(sp_decimal * float(rng.uniform(0.96, 1.0)), 2),
                0,
                None,
                db.to_prisma_datetime(datetime.now(timezone.utc)),
                db.to_prisma_datetime(datetime.now(timezone.utc)),
            ),
        )

        conn.execute(
            'INSERT INTO "RunnerPaceProfile" (id, runnerId, projectedRole, usualEarlyPosition, '
            "breaksQuicklyRate, slowStartRate, energyToObtainPositionIndex, positionChange3fTo2f, "
            "positionChange2fTo1f, relativeAccelerationIndex, finishingSpeedIndex, "
            "positionChangeFinalFurlong, weakensLateRate, staysOnStronglyRate, competitionForLeadIndex, "
            "pacePressureIndex, paceCollapseProbability, notes, updatedAt) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                new_id(),
                runner_id,
                h.pace_archetype,
                *pace_profile_values(h, rng),
                None,
                db.to_prisma_datetime(datetime.now(timezone.utc)),
            ),
        )

        for is_opening, ts, dec in (
            (1, race_date - timedelta(hours=20), open_decimal),
            (0, race_date, sp_decimal),
        ):
            conn.execute(
                'INSERT INTO "RunnerMarketPrice" (id, runnerId, bookmakerId, timestamp, winOddsDecimal, '
                "eachWayFraction, numberOfPlaces, extraPlaces, isOpeningPrice, isStartingPrice, "
                "isClosingPrice, createdAt) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    new_id(),
                    runner_id,
                    bookmaker_ids[place_terms_bookmakers[0]],
                    db.to_prisma_datetime(ts),
                    dec,
                    each_way_fraction,
                    bookmaker_places,
                    0,
                    is_opening,
                    1 - is_opening,
                    1 - is_opening,
                    db.to_prisma_datetime(datetime.now(timezone.utc)),
                ),
            )

        placed = finishing_position <= bookmaker_places
        conn.execute(
            'INSERT INTO "ResultEntry" (id, runnerId, finishingPosition, finishStatus, '
            "beatenDistanceLengths, startingPriceDecimal, closingOddsDecimal, placeOutcome, "
            "profitLossWinStake, profitLossEachWayStake, resultStatus, createdAt, updatedAt) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                new_id(),
                runner_id,
                finishing_position,
                "WON" if finishing_position == 1 else "RAN",
                beaten[finishing_position - 1],
                sp_decimal,
                sp_decimal,
                int(placed),
                round(sp_decimal - 1, 2) if finishing_position == 1 else -1.0,
                None,
                "CONFIRMED",
                db.to_prisma_datetime(datetime.now(timezone.utc)),
                db.to_prisma_datetime(datetime.now(timezone.utc)),
            ),
        )

        # FormEntry mirrors this run with the extra positional/sectional
        # detail — see module docstring for why this is the canonical
        # feature-engineering source for current-form/pace features.
        pos3f, pos2f, pos1f = simulated_running_positions(h, finishing_position, n_runners, rng)
        conn.execute(
            'INSERT INTO "FormEntry" (id, isSampleData, horseId, linkedRaceId, raceDate, course, country, '
            "distanceFurlongs, going, raceClass, flatJumps, fieldSize, finishingPosition, finishStatus, "
            "beatenDistanceLengths, startingPriceDecimal, officialRating, weightPounds, draw, jockeyName, "
            "headgear, raceComment, inRunningComment, earlyPosition, halfwayPosition, position3fOut, "
            "position2fOut, position1fOut, sectionalTimes, finishingSpeedPercentage, paceClassification, "
            "raceStrengthIndex, winnerSubsequentPerformance, collateralFormNotes, createdAt) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                new_id(),
                1,
                h.id,
                race_id,
                db.to_prisma_datetime(race_date),
                course,
                country,
                distance,
                going,
                race_class,
                flat_jumps,
                n_runners,
                finishing_position,
                "RAN",
                beaten[finishing_position - 1],
                sp_decimal,
                round(h.current_or),
                weights_lbs[i],
                draw,
                h.jockey_name,
                headgear,
                None,
                None,
                pos3f,
                None,
                pos3f,
                pos2f,
                pos1f,
                None,
                finishing_speed_percentage(h, finishing_position, n_runners, rng),
                pace_classification_label(pos3f, pos1f, n_runners),
                None,
                None,
                None,
                db.to_prisma_datetime(datetime.now(timezone.utc)),
            ),
        )

        # Causal rating update: informs the NEXT race only.
        expected_percentile = _expected_percentile(h, field_horses)
        actual_percentile = (n_runners - finishing_position) / max(n_runners - 1, 1)
        delta = float(np.clip(12 * (actual_percentile - expected_percentile), -8, 8))
        h.current_or = float(np.clip(h.current_or + delta, 30, 175))
        h.or_history.append((race_date, h.current_or))
        h.last_run_date = race_date
        h.career_starts += 1

    return n_runners


def _softmax(x: np.ndarray) -> np.ndarray:
    shifted = x - np.max(x)
    exp = np.exp(shifted)
    return exp / exp.sum()


def _expected_percentile(horse: HorseState, field_horses: list[HorseState]) -> float:
    ors = np.array([h.current_or for h in field_horses])
    rank = (ors < horse.current_or).sum() + 0.5 * (ors == horse.current_or).sum()
    return float(rank / max(len(field_horses) - 1, 1))


def race_class_label(flat_jumps: str, race_class: int) -> str:
    kind = "Chase" if flat_jumps == "JUMPS" and race_class <= 3 else ("Hurdle" if flat_jumps == "JUMPS" else "Stakes")
    return f"Class {race_class} {kind}"


def pace_profile_values(h: HorseState, rng: np.random.Generator) -> tuple:
    archetype_position = {"LEADER": 0.08, "PRONOUNCED_PACE": 0.3, "MIDDIVISION": 0.55, "HOLD_UP": 0.85}
    base = archetype_position[h.pace_archetype]
    usual_early_position = float(np.clip(base + rng.normal(0, 0.06), 0.02, 0.98))
    breaks_quickly_rate = float(np.clip(1 - base + rng.normal(0, 0.1), 0, 1))
    slow_start_rate = float(np.clip(base * 0.4 + rng.normal(0, 0.05), 0, 1))
    energy_index = float(np.clip(1 - base + rng.normal(0, 0.1), 0, 1))
    transition_gain = float(np.clip((base - 0.3) * 0.6 + rng.normal(0, 0.1), -1, 1))
    transition_gain_2 = float(np.clip((base - 0.3) * 0.4 + rng.normal(0, 0.1), -1, 1))
    accel_index = float(np.clip(0.5 + (base - 0.5) * 0.3 + rng.normal(0, 0.1), 0, 1))
    finishing_speed_index = float(np.clip(base * 0.7 + rng.normal(0, 0.1), 0, 1))
    final_furlong_change = float(np.clip((base - 0.4) * 0.5 + rng.normal(0, 0.1), -1, 1))
    weakens_late_rate = float(np.clip((1 - base) * 0.35 + rng.normal(0, 0.05), 0, 1))
    stays_on_rate = float(np.clip(base * 0.55 + rng.normal(0, 0.08), 0, 1))
    competition_for_lead = float(np.clip(rng.uniform(0.2, 0.8), 0, 1))
    pace_pressure = float(np.clip(rng.uniform(0.2, 0.8), 0, 1))
    pace_collapse_prob = float(np.clip(rng.uniform(0.1, 0.5), 0, 1))
    return (
        usual_early_position,
        breaks_quickly_rate,
        slow_start_rate,
        energy_index,
        transition_gain,
        transition_gain_2,
        accel_index,
        finishing_speed_index,
        final_furlong_change,
        weakens_late_rate,
        stays_on_rate,
        competition_for_lead,
        pace_pressure,
        pace_collapse_prob,
    )


def simulated_running_positions(h: HorseState, finishing_position: int, field_size: int, rng: np.random.Generator) -> tuple[int, int, int]:
    archetype_position = {"LEADER": 0.08, "PRONOUNCED_PACE": 0.3, "MIDDIVISION": 0.55, "HOLD_UP": 0.85}
    base_pct = archetype_position[h.pace_archetype]
    base_pos = max(1, round(base_pct * field_size))
    jitter = lambda: int(rng.integers(-1, 2))
    pos3f = int(np.clip(base_pos + jitter(), 1, field_size))
    # Positions converge toward the actual finishing position as the race ends.
    pos2f = int(np.clip(round((pos3f + finishing_position) / 2) + jitter(), 1, field_size))
    pos1f = int(np.clip(round((pos2f + finishing_position) / 2) + jitter(), 1, field_size))
    return pos3f, pos2f, pos1f


def finishing_speed_percentage(h: HorseState, finishing_position: int, field_size: int, rng: np.random.Generator) -> float:
    archetype_bonus = {"LEADER": -2.0, "PRONOUNCED_PACE": -0.5, "MIDDIVISION": 0.5, "HOLD_UP": 2.0}
    base = 100 + archetype_bonus[h.pace_archetype] - (finishing_position - 1) * 0.35
    return round(float(base + rng.normal(0, 1.5)), 2)


def pace_classification_label(pos3f: int, pos1f: int, field_size: int) -> str:
    pct3f = pos3f / max(field_size, 1)
    if pct3f <= 0.2:
        return "Led" if pos1f <= pos3f else "Prominent, faded"
    if pct3f <= 0.45:
        return "Prominent"
    if pos1f < pos3f - 1:
        return "Held up, strong late progress"
    return "Held up"


def _write_evidence_profiles(conn, horses: list[HorseState], today: datetime) -> None:
    for h in horses:
        starts_last_12mo = sum(1 for d, _ in h.or_history if (today - d).days <= 365)
        density = min(1.0, 0.15 + 0.05 * min(h.career_starts, 17))
        label = (
            "VERY_LOW" if h.career_starts <= 1 else
            "LOW" if h.career_starts <= 3 else
            "MODERATE" if h.career_starts <= 7 else
            "HIGH" if h.career_starts <= 14 else
            "VERY_HIGH"
        )
        existing = conn.execute('SELECT id FROM "EvidenceProfile" WHERE horseId = ?', (h.id,)).fetchone()
        if existing:
            continue
        conn.execute(
            'INSERT INTO "EvidenceProfile" (id, horseId, careerStarts, startsLast12Months, startsAtCourse, '
            "startsAtDistance, startsOnGoing, evidenceDensityScore, evidenceDensityLabel, uncertaintyNote, "
            "updatedAt) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                new_id(),
                h.id,
                h.career_starts,
                starts_last_12mo,
                min(h.career_starts, 3),
                min(h.career_starts, 5),
                min(h.career_starts, 4),
                round(density, 3),
                label,
                None,
                db.to_prisma_datetime(today),
            ),
        )


if __name__ == "__main__":
    main()
