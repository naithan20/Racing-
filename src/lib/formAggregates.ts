/**
 * Deterministic historical-record aggregation over FormEntry rows.
 *
 * These are literal counts (runs/wins/places at a course, distance, going)
 * — not model features or predictions. They power the "record" panels on
 * the runner detail page and double as raw inputs a future model could read
 * (see src/features for the flexible store those inputs would land in).
 */

export interface FormEntryLike {
  course: string;
  distanceFurlongs: number | null;
  going: string | null;
  finishingPosition: number | null;
}

export interface RecordSummary {
  runs: number;
  wins: number;
  places: number; // top 3, for this generic summary only — see value/place.ts for bookmaker-specific place logic
  winPercentage: number | null;
  placePercentage: number | null;
}

function summarise(entries: FormEntryLike[]): RecordSummary {
  const runs = entries.length;
  const wins = entries.filter((e) => e.finishingPosition === 1).length;
  const places = entries.filter((e) => e.finishingPosition !== null && e.finishingPosition <= 3).length;
  return {
    runs,
    wins,
    places,
    winPercentage: runs > 0 ? wins / runs : null,
    placePercentage: runs > 0 ? places / runs : null,
  };
}

export function courseRecord(entries: FormEntryLike[], course: string): RecordSummary {
  return summarise(entries.filter((e) => e.course === course));
}

export function distanceRecord(
  entries: FormEntryLike[],
  distanceFurlongs: number,
  toleranceFurlongs = 1
): RecordSummary {
  return summarise(
    entries.filter(
      (e) => e.distanceFurlongs !== null && Math.abs(e.distanceFurlongs - distanceFurlongs) <= toleranceFurlongs
    )
  );
}

export function goingRecord(entries: FormEntryLike[], going: string): RecordSummary {
  const normalised = going.toLowerCase();
  return summarise(entries.filter((e) => (e.going ?? "").toLowerCase() === normalised));
}

export function courseDistanceRecord(
  entries: FormEntryLike[],
  course: string,
  distanceFurlongs: number,
  toleranceFurlongs = 1
): RecordSummary {
  return summarise(
    entries.filter(
      (e) =>
        e.course === course &&
        e.distanceFurlongs !== null &&
        Math.abs(e.distanceFurlongs - distanceFurlongs) <= toleranceFurlongs
    )
  );
}
