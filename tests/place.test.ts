import { describe, expect, it } from "vitest";

import {
  describePlaceBasis,
  InvalidPlaceTermsError,
  isPlacedUnderTerms,
  placeOddsDecimal,
  settleEachWayBet,
  settleWinBet,
} from "@/value/place";

describe("isPlacedUnderTerms", () => {
  it("never assumes top 3 — respects the bookmaker's actual place count", () => {
    const fivePlaces = { places: 5, eachWayFraction: 0.2 };
    expect(isPlacedUnderTerms(4, fivePlaces)).toBe(true);
    expect(isPlacedUnderTerms(5, fivePlaces)).toBe(true);
    expect(isPlacedUnderTerms(6, fivePlaces)).toBe(false);
  });

  it("handles the classic 3-places case correctly too", () => {
    const threePlaces = { places: 3, eachWayFraction: 0.25 };
    expect(isPlacedUnderTerms(3, threePlaces)).toBe(true);
    expect(isPlacedUnderTerms(4, threePlaces)).toBe(false);
  });

  it("returns false for a non-finisher", () => {
    expect(isPlacedUnderTerms(null, { places: 4, eachWayFraction: 0.2 })).toBe(false);
  });
});

describe("describePlaceBasis", () => {
  it("always states the number of places explicitly", () => {
    const text = describePlaceBasis({ places: 5, eachWayFraction: 0.2, extraPlaces: true }, 16);
    expect(text).toContain("top 5");
    expect(text).toContain("16 runners");
    expect(text).toContain("extra places");
  });

  it("omits the runner count when not supplied", () => {
    const text = describePlaceBasis({ places: 3, eachWayFraction: 0.25 });
    expect(text).toBe("Place probability based on top 3");
  });
});

describe("placeOddsDecimal", () => {
  it("computes the each-way place price from win odds and fraction", () => {
    // 9/1 (decimal 10) at 1/4 odds -> place odds = 1 + 9*0.25 = 3.25
    expect(placeOddsDecimal(10, 0.25)).toBeCloseTo(3.25, 10);
    // 4/1 (decimal 5) at 1/5 odds -> place odds = 1 + 4*0.2 = 1.8
    expect(placeOddsDecimal(5, 0.2)).toBeCloseTo(1.8, 10);
  });

  it("rejects an each-way fraction outside (0, 1)", () => {
    expect(() => placeOddsDecimal(5, 0)).toThrow(InvalidPlaceTermsError);
    expect(() => placeOddsDecimal(5, 1)).toThrow(InvalidPlaceTermsError);
  });
});

describe("settleWinBet", () => {
  it("pays out stake * odds on a win", () => {
    const settlement = settleWinBet(10, 4, true);
    expect(settlement.totalReturn).toBe(40);
    expect(settlement.profitLoss).toBe(30);
  });

  it("loses the full stake otherwise", () => {
    const settlement = settleWinBet(10, 4, false);
    expect(settlement.totalReturn).toBe(0);
    expect(settlement.profitLoss).toBe(-10);
  });
});

describe("settleEachWayBet", () => {
  const terms = { places: 4, eachWayFraction: 0.25 };

  it("pays both halves when the selection wins", () => {
    // 1pt each way at 9/1 (decimal 10): win part 1*10=10, place part 1*3.25=3.25
    const settlement = settleEachWayBet(1, 10, terms, { won: true, placed: true });
    expect(settlement.totalReturn).toBeCloseTo(13.25, 10);
    expect(settlement.profitLoss).toBeCloseTo(11.25, 10); // total return - 2pt stake
  });

  it("pays only the place part when placed but not won", () => {
    const settlement = settleEachWayBet(1, 10, terms, { won: false, placed: true });
    expect(settlement.totalReturn).toBeCloseTo(3.25, 10);
    expect(settlement.profitLoss).toBeCloseTo(1.25, 10);
  });

  it("loses the full each-way stake when unplaced", () => {
    const settlement = settleEachWayBet(1, 10, terms, { won: false, placed: false });
    expect(settlement.totalReturn).toBe(0);
    expect(settlement.profitLoss).toBe(-2);
  });

  it("treats a win as automatically placed even if the caller passes placed:false", () => {
    const settlement = settleEachWayBet(1, 10, terms, { won: true, placed: false });
    expect(settlement.placedPart).toBe(true);
    expect(settlement.totalReturn).toBeCloseTo(13.25, 10);
  });
});
