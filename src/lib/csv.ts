/**
 * Minimal, dependency-free RFC 4180-style CSV parser.
 *
 * Handles quoted fields, embedded commas, embedded newlines, and escaped
 * quotes ("" inside a quoted field). Deliberately small and dependency-free
 * so the import pipeline has no hidden external behaviour to audit.
 */

export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let inQuotes = false;

  const pushField = () => {
    row.push(field);
    field = "";
  };
  const pushRow = () => {
    pushField();
    rows.push(row);
    row = [];
  };

  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    const next = text[i + 1];

    if (inQuotes) {
      if (char === '"' && next === '"') {
        field += '"';
        i++;
      } else if (char === '"') {
        inQuotes = false;
      } else {
        field += char;
      }
      continue;
    }

    if (char === '"') {
      inQuotes = true;
    } else if (char === ",") {
      pushField();
    } else if (char === "\r") {
      // skip; \n (or end of text) will terminate the row
    } else if (char === "\n") {
      pushRow();
    } else {
      field += char;
    }
  }

  // Flush any trailing field/row (handles files without a final newline).
  if (field.length > 0 || row.length > 0) {
    pushRow();
  }

  return rows.filter((r) => !(r.length === 1 && r[0] === ""));
}

/** Parses CSV text into an array of header-keyed records. */
export function parseCsvToRecords(text: string): Record<string, string>[] {
  const rows = parseCsv(text);
  if (rows.length === 0) return [];
  const [header, ...dataRows] = rows;
  return dataRows.map((row) => {
    const record: Record<string, string> = {};
    header.forEach((key, index) => {
      record[key.trim()] = row[index] ?? "";
    });
    return record;
  });
}
