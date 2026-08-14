import { describe, expect, it } from "vitest";

import { classifyUrl } from "@/lib/urlPreview";

describe("classifyUrl", () => {
  it("accepts a plain https CSV URL", () => {
    const result = classifyUrl("https://example.com/data/races.csv");
    expect(result.valid).toBe(true);
    expect(result.hostname).toBe("example.com");
    expect(result.scheme).toBe("https");
    expect(result.fileExtension).toBe(".csv");
    expect(result.isAllowedExtension).toBe(true);
  });

  it("flags an executable extension as not allowed, without rejecting outright", () => {
    const result = classifyUrl("https://example.com/tool.exe");
    expect(result.valid).toBe(true);
    expect(result.isAllowedExtension).toBe(false);
    expect(result.fileExtension).toBe(".exe");
  });

  it("rejects a non-http(s) scheme", () => {
    const result = classifyUrl("ftp://example.com/data.csv");
    expect(result.valid).toBe(false);
    expect(result.error).toMatch(/http\/https/);
  });

  it("rejects an unparseable URL", () => {
    const result = classifyUrl("not a url");
    expect(result.valid).toBe(false);
  });

  it("handles a URL with no file extension", () => {
    const result = classifyUrl("https://example.com/download");
    expect(result.valid).toBe(true);
    expect(result.fileExtension).toBeNull();
    expect(result.isAllowedExtension).toBe(false);
  });

  it("recognises every allowed extension", () => {
    for (const ext of [".csv", ".json", ".jsonl", ".ndjson", ".db", ".sqlite", ".sqlite3", ".zip", ".gz", ".gzip"]) {
      const result = classifyUrl(`https://example.com/file${ext}`);
      expect(result.isAllowedExtension, `expected ${ext} to be allowed`).toBe(true);
    }
  });
});
