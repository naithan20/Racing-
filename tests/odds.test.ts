import { describe, expect, it } from "vitest";

import {
  bookPercentage,
  decimalToFractional,
  fractionalToDecimal,
  impliedProbability,
  InvalidOddsError,
  InvalidProbabilityError,
  normaliseImpliedProbabilities,
  overroundPercentage,
  probabilityToDecimalOdds,
} from "@/lib/odds";

describe("impliedProbability", () => {
  it("converts decimal odds to implied probability", () => {
    expect(impliedProbability(2)).toBeCloseTo(0.5, 10);
    expect(impliedProbability(4)).toBeCloseTo(0.25, 10);
    expect(impliedProbability(1.01)).toBeCloseTo(1 / 1.01, 10);
  });

  it("rejects odds of 1 or less", () => {
    expect(() => impliedProbability(1)).toThrow(InvalidOddsError);
    expect(() => impliedProbability(0)).toThrow(InvalidOddsError);
    expect(() => impliedProbability(-3)).toThrow(InvalidOddsError);
  });

  it("rejects non-finite odds", () => {
    expect(() => impliedProbability(Number.NaN)).toThrow(InvalidOddsError);
    expect(() => impliedProbability(Infinity)).toThrow(InvalidOddsError);
  });
});

describe("probabilityToDecimalOdds", () => {
  it("is the inverse of impliedProbability", () => {
    expect(probabilityToDecimalOdds(0.5)).toBeCloseTo(2, 10);
    expect(probabilityToDecimalOdds(0.25)).toBeCloseTo(4, 10);
  });

  it("rejects probabilities outside (0, 1]", () => {
    expect(() => probabilityToDecimalOdds(0)).toThrow(InvalidProbabilityError);
    expect(() => probabilityToDecimalOdds(-0.1)).toThrow(InvalidProbabilityError);
    expect(() => probabilityToDecimalOdds(1.5)).toThrow(InvalidProbabilityError);
  });

  it("accepts probability of exactly 1", () => {
    expect(probabilityToDecimalOdds(1)).toBe(1);
  });
});

describe("bookPercentage / overroundPercentage", () => {
  it("sums to 100% for a fair book", () => {
    // Fair coin-flip market: two runners at evens each.
    expect(bookPercentage([2, 2])).toBeCloseTo(1, 10);
    expect(overroundPercentage([2, 2])).toBeCloseTo(0, 10);
  });

  it("detects overround above 100%", () => {
    const book = bookPercentage([1.9, 1.9]);
    expect(book).toBeGreaterThan(1);
    expect(overroundPercentage([1.9, 1.9])).toBeCloseTo((book - 1) * 100, 10);
  });
});

describe("normaliseImpliedProbabilities", () => {
  it("removes overround so probabilities sum to 1", () => {
    const normalised = normaliseImpliedProbabilities([1.9, 1.9, 5]);
    const sum = normalised.reduce((a, b) => a + b, 0);
    expect(sum).toBeCloseTo(1, 10);
  });
});

describe("decimalToFractional / fractionalToDecimal", () => {
  it("converts common decimal odds to recognisable fractions", () => {
    expect(decimalToFractional(2)).toBe("1/1");
    expect(decimalToFractional(3)).toBe("2/1");
    expect(decimalToFractional(2.5)).toBe("3/2");
    expect(decimalToFractional(1.5)).toBe("1/2");
  });

  it("round-trips fractional -> decimal -> fractional for simple fractions", () => {
    expect(fractionalToDecimal("5/2")).toBeCloseTo(3.5, 10);
    expect(fractionalToDecimal("evens")).toBe(2);
    expect(fractionalToDecimal("9-4")).toBeCloseTo(9 / 4 + 1, 10);
  });

  it("throws on unparsable fractional odds", () => {
    expect(() => fractionalToDecimal("nonsense")).toThrow();
    expect(() => fractionalToDecimal("5/0")).toThrow();
  });

  it("rejects invalid decimal odds when converting to fractional", () => {
    expect(() => decimalToFractional(1)).toThrow(InvalidOddsError);
    expect(() => decimalToFractional(0.5)).toThrow(InvalidOddsError);
  });
});
