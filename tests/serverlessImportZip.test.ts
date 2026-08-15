import { deflateRawSync } from "node:zlib";

import { describe, expect, it } from "vitest";

import { extractZip, isZip, pickPrimaryCsvEntry } from "@/lib/serverlessImport/zip";

const LOCAL_FILE_HEADER_SIGNATURE = 0x04034b50;
const CENTRAL_DIRECTORY_SIGNATURE = 0x02014b50;
const EOCD_SIGNATURE = 0x06054b50;

/** Hand-builds a minimal single- or multi-entry ZIP archive for round-trip testing, without any zip-writer dependency — mirroring src/lib/serverlessImport/zip.ts's own reader-side format knowledge. */
function buildTestZip(entries: { name: string; content: string; deflate?: boolean }[]): Buffer {
  const localParts: Buffer[] = [];
  const centralParts: Buffer[] = [];
  let offset = 0;

  for (const entry of entries) {
    const nameBuf = Buffer.from(entry.name, "utf-8");
    const rawContent = Buffer.from(entry.content, "utf-8");
    const compressed = entry.deflate ? deflateRawSync(rawContent) : rawContent;
    const method = entry.deflate ? 8 : 0;

    const localHeader = Buffer.alloc(30);
    localHeader.writeUInt32LE(LOCAL_FILE_HEADER_SIGNATURE, 0);
    localHeader.writeUInt16LE(20, 4); // version needed
    localHeader.writeUInt16LE(0, 6); // flags
    localHeader.writeUInt16LE(method, 8);
    localHeader.writeUInt16LE(0, 10); // mod time
    localHeader.writeUInt16LE(0, 12); // mod date
    localHeader.writeUInt32LE(0, 14); // crc32 (unused by this reader)
    localHeader.writeUInt32LE(compressed.length, 18);
    localHeader.writeUInt32LE(rawContent.length, 22);
    localHeader.writeUInt16LE(nameBuf.length, 26);
    localHeader.writeUInt16LE(0, 28); // extra length

    const localEntry = Buffer.concat([localHeader, nameBuf, compressed]);
    const localOffset = offset;
    localParts.push(localEntry);
    offset += localEntry.length;

    const centralHeader = Buffer.alloc(46);
    centralHeader.writeUInt32LE(CENTRAL_DIRECTORY_SIGNATURE, 0);
    centralHeader.writeUInt16LE(20, 4); // version made by
    centralHeader.writeUInt16LE(20, 6); // version needed
    centralHeader.writeUInt16LE(0, 8); // flags
    centralHeader.writeUInt16LE(method, 10);
    centralHeader.writeUInt16LE(0, 12);
    centralHeader.writeUInt16LE(0, 14);
    centralHeader.writeUInt32LE(0, 16); // crc32
    centralHeader.writeUInt32LE(compressed.length, 20);
    centralHeader.writeUInt32LE(rawContent.length, 24);
    centralHeader.writeUInt16LE(nameBuf.length, 28);
    centralHeader.writeUInt16LE(0, 30); // extra length
    centralHeader.writeUInt16LE(0, 32); // comment length
    centralHeader.writeUInt16LE(0, 34); // disk number
    centralHeader.writeUInt16LE(0, 36); // internal attrs
    centralHeader.writeUInt32LE(0, 38); // external attrs
    centralHeader.writeUInt32LE(localOffset, 42);

    centralParts.push(Buffer.concat([centralHeader, nameBuf]));
  }

  const localSection = Buffer.concat(localParts);
  const centralSection = Buffer.concat(centralParts);

  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(EOCD_SIGNATURE, 0);
  eocd.writeUInt16LE(0, 4);
  eocd.writeUInt16LE(0, 6);
  eocd.writeUInt16LE(entries.length, 8);
  eocd.writeUInt16LE(entries.length, 10);
  eocd.writeUInt32LE(centralSection.length, 12);
  eocd.writeUInt32LE(localSection.length, 16);
  eocd.writeUInt16LE(0, 20);

  return Buffer.concat([localSection, centralSection, eocd]);
}

describe("isZip", () => {
  it("recognizes a ZIP local file header signature", () => {
    const zip = buildTestZip([{ name: "a.csv", content: "x" }]);
    expect(isZip(zip)).toBe(true);
  });

  it("rejects a plain text buffer", () => {
    expect(isZip(Buffer.from("race_date,course\n2020-01-01,Ascot\n"))).toBe(false);
  });
});

describe("extractZip", () => {
  it("round-trips a single STORED (uncompressed) entry", () => {
    const zip = buildTestZip([{ name: "data.csv", content: "a,b\n1,2\n" }]);
    const entries = extractZip(zip);
    expect(entries).toHaveLength(1);
    expect(entries[0].name).toBe("data.csv");
    expect(entries[0].data.toString("utf-8")).toBe("a,b\n1,2\n");
  });

  it("round-trips a DEFLATE-compressed entry", () => {
    const content = "race_date,course,horse_name\n2020-01-01,Ascot,Sample Star\n".repeat(50);
    const zip = buildTestZip([{ name: "results.csv", content, deflate: true }]);
    const entries = extractZip(zip);
    expect(entries[0].data.toString("utf-8")).toBe(content);
  });

  it("handles multiple entries and picks the largest CSV", () => {
    const zip = buildTestZip([
      { name: "readme.txt", content: "hello" },
      { name: "small.csv", content: "a,b\n1,2\n" },
      { name: "big.csv", content: "a,b\n1,2\n3,4\n5,6\n7,8\n9,10\n".repeat(10), deflate: true },
    ]);
    const entries = extractZip(zip);
    expect(entries).toHaveLength(3);
    const primary = pickPrimaryCsvEntry(entries);
    expect(primary?.name).toBe("big.csv");
  });

  it("throws a clear error for a corrupt/non-ZIP buffer", () => {
    expect(() => extractZip(Buffer.from("not a zip"))).toThrow(/End Of Central Directory/);
  });
});

describe("pickPrimaryCsvEntry", () => {
  it("returns null when the archive has no CSV entries", () => {
    const zip = buildTestZip([{ name: "readme.txt", content: "hello" }]);
    expect(pickPrimaryCsvEntry(extractZip(zip))).toBeNull();
  });
});
