import { describe, expect, it } from "vitest";

import { getSourceCatalogEntry, listEnabledSources, SOURCE_CATALOG } from "@/data/sourceCatalog";

describe("SOURCE_CATALOG", () => {
  it("has unique ids", () => {
    const ids = SOURCE_CATALOG.map((s) => s.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("every entry is FREE — the £0 rule applies to the default catalog", () => {
    for (const entry of SOURCE_CATALOG) {
      expect(entry.cost).toBe("FREE");
    }
  });

  it("Kaggle sources require a kaggle connection", () => {
    const kaggleSources = SOURCE_CATALOG.filter((s) => s.downloadMechanism === "KAGGLE");
    expect(kaggleSources.length).toBeGreaterThan(0);
    for (const entry of kaggleSources) {
      expect(entry.authMechanism).toBe("kaggle");
    }
  });

  it("an UNAVAILABLE source is disabled rather than offered for import", () => {
    const unavailable = SOURCE_CATALOG.filter((s) => s.verificationStatus === "UNAVAILABLE");
    expect(unavailable.length).toBeGreaterThan(0);
    for (const entry of unavailable) {
      expect(entry.enabled).toBe(false);
    }
  });

  it("local-file is present as the advanced fallback", () => {
    const entry = getSourceCatalogEntry("local-file");
    expect(entry).toBeDefined();
    expect(entry?.downloadMechanism).toBe("LOCAL_FILE");
  });

  it("getSourceCatalogEntry returns undefined for an unknown id", () => {
    expect(getSourceCatalogEntry("does-not-exist")).toBeUndefined();
  });

  it("listEnabledSources excludes disabled entries", () => {
    const enabled = listEnabledSources();
    expect(enabled.every((s) => s.enabled)).toBe(true);
    expect(enabled.length).toBeLessThan(SOURCE_CATALOG.length);
  });
});
