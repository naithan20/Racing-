/**
 * Minimal, dependency-free ZIP archive reader.
 *
 * Kaggle's `datasets/download` endpoint always wraps its response in a ZIP
 * (even single-file datasets), and this app's serverless import pipeline
 * (src/lib/serverlessImport/) has no filesystem to shell out to `unzip` —
 * Vercel serverless functions can't spawn subprocesses reliably and have no
 * persistent disk. Rather than add a dependency for something the ZIP
 * format specification and Node's built-in `zlib` already make tractable,
 * this reads the End-Of-Central-Directory record, walks the central
 * directory, and inflates each entry with `zlib.inflateRawSync` — the same
 * "dependency-free so the pipeline has no hidden external behaviour to
 * audit" philosophy as src/lib/csv.ts.
 *
 * Deliberately narrow: only STORED (method 0) and DEFLATE (method 8)
 * entries are supported — the two methods every common ZIP writer
 * (Kaggle's own backend included) uses for CSV/text content. Encrypted
 * entries, ZIP64, and other compression methods are rejected with a clear
 * error rather than silently producing garbage.
 */

import { inflateRawSync } from "node:zlib";

const EOCD_SIGNATURE = 0x06054b50;
const CENTRAL_DIRECTORY_SIGNATURE = 0x02014b50;
const LOCAL_FILE_HEADER_SIGNATURE = 0x04034b50;
const EOCD_MIN_SIZE = 22;
const MAX_COMMENT_LENGTH = 65535;

export interface ZipEntry {
  name: string;
  data: Buffer;
}

export function isZip(buffer: Buffer): boolean {
  return buffer.length >= 4 && buffer.readUInt32LE(0) === LOCAL_FILE_HEADER_SIGNATURE;
}

function findEndOfCentralDirectory(buffer: Buffer): number {
  const searchStart = Math.max(0, buffer.length - EOCD_MIN_SIZE - MAX_COMMENT_LENGTH);
  for (let i = buffer.length - EOCD_MIN_SIZE; i >= searchStart; i--) {
    if (buffer.readUInt32LE(i) === EOCD_SIGNATURE) return i;
  }
  throw new Error("Not a valid ZIP archive: End Of Central Directory record not found.");
}

/** Extracts every entry from a ZIP archive held entirely in memory. */
export function extractZip(buffer: Buffer): ZipEntry[] {
  const eocdOffset = findEndOfCentralDirectory(buffer);
  const entryCount = buffer.readUInt16LE(eocdOffset + 10);
  const centralDirectoryOffset = buffer.readUInt32LE(eocdOffset + 16);

  const entries: ZipEntry[] = [];
  let offset = centralDirectoryOffset;

  for (let i = 0; i < entryCount; i++) {
    if (buffer.readUInt32LE(offset) !== CENTRAL_DIRECTORY_SIGNATURE) {
      throw new Error(`Corrupt ZIP archive: expected central directory entry at offset ${offset}.`);
    }

    const compressionMethod = buffer.readUInt16LE(offset + 10);
    const compressedSize = buffer.readUInt32LE(offset + 20);
    const nameLength = buffer.readUInt16LE(offset + 28);
    const extraLength = buffer.readUInt16LE(offset + 30);
    const commentLength = buffer.readUInt16LE(offset + 32);
    const localHeaderOffset = buffer.readUInt32LE(offset + 42);
    const name = buffer.toString("utf-8", offset + 46, offset + 46 + nameLength);

    // Directory entries end with "/" and carry no data worth extracting.
    if (!name.endsWith("/")) {
      entries.push({ name, data: readLocalFileEntry(buffer, localHeaderOffset, compressionMethod, compressedSize) });
    }

    offset += 46 + nameLength + extraLength + commentLength;
  }

  return entries;
}

function readLocalFileEntry(buffer: Buffer, localHeaderOffset: number, compressionMethod: number, compressedSize: number): Buffer {
  if (buffer.readUInt32LE(localHeaderOffset) !== LOCAL_FILE_HEADER_SIGNATURE) {
    throw new Error(`Corrupt ZIP archive: expected local file header at offset ${localHeaderOffset}.`);
  }
  const nameLength = buffer.readUInt16LE(localHeaderOffset + 26);
  const extraLength = buffer.readUInt16LE(localHeaderOffset + 28);
  const dataStart = localHeaderOffset + 30 + nameLength + extraLength;
  const compressed = buffer.subarray(dataStart, dataStart + compressedSize);

  if (compressionMethod === 0) return Buffer.from(compressed);
  if (compressionMethod === 8) return inflateRawSync(compressed);
  throw new Error(
    `Unsupported ZIP compression method ${compressionMethod} — only STORED (0) and DEFLATE (8) are supported.`
  );
}

/** Picks the largest .csv entry in the archive — the common shape for a Kaggle/GitHub-release dataset ZIP (one primary data file, maybe a small readme). */
export function pickPrimaryCsvEntry(entries: ZipEntry[]): ZipEntry | null {
  const csvEntries = entries.filter((e) => e.name.toLowerCase().endsWith(".csv"));
  if (csvEntries.length === 0) return null;
  return csvEntries.reduce((largest, entry) => (entry.data.length > largest.data.length ? entry : largest));
}
