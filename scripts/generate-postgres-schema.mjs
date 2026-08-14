#!/usr/bin/env node
/**
 * Derives prisma/postgres/schema.prisma from prisma/schema.prisma.
 *
 * There is deliberately only ONE hand-maintained source of truth for the
 * ~1300 lines of models/enums (prisma/schema.prisma, SQLite, used for local
 * development) — this script produces the Postgres variant used for
 * production (Vercel + Neon/any Postgres) by swapping only the
 * `datasource` block and the generator's `output` path (one directory
 * deeper, since the postgres schema lives in its own `prisma/postgres/`
 * subfolder so its migration history never collides with the SQLite one in
 * `prisma/migrations/`). Every model/enum/field is identical between the
 * two — the schema was written in Postgres-compatible types from the start
 * (see the comment at the top of schema.prisma), so no field-level changes
 * are ever needed here.
 *
 * Run via `npm run db:generate:postgres` (which runs this first) or
 * directly: `node scripts/generate-postgres-schema.mjs`.
 */

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");

const SOURCE_SCHEMA_PATH = path.join(ROOT, "prisma", "schema.prisma");
const OUTPUT_DIR = path.join(ROOT, "prisma", "postgres");
const OUTPUT_SCHEMA_PATH = path.join(OUTPUT_DIR, "schema.prisma");

const source = readFileSync(SOURCE_SCHEMA_PATH, "utf-8");

const datasourceBlockPattern = /datasource\s+db\s*\{[^}]*\}/;
if (!datasourceBlockPattern.test(source)) {
  throw new Error(`Could not find a "datasource db { ... }" block in ${SOURCE_SCHEMA_PATH}`);
}

let generated = source.replace(
  datasourceBlockPattern,
  'datasource db {\n  provider = "postgresql"\n}'
);

// The generator's `output` path is relative to THIS schema file's own
// directory — prisma/postgres/schema.prisma needs one extra `../` to land
// in the same src/generated/prisma/ location the SQLite schema targets,
// so the app's `@/generated/prisma/*` imports resolve identically
// regardless of which schema produced them.
generated = generated.replace(
  /output\s*=\s*"\.\.\/src\/generated\/prisma"/,
  'output   = "../../src/generated/prisma"'
);

const header =
  "// GENERATED FILE — do not edit directly.\n" +
  "// Derived from ../schema.prisma by scripts/generate-postgres-schema.mjs.\n" +
  "// Edit the models/enums in ../schema.prisma (the single source of truth) and re-run\n" +
  "// `npm run db:generate:postgres` (or `node scripts/generate-postgres-schema.mjs`) to refresh this file.\n\n";

mkdirSync(OUTPUT_DIR, { recursive: true });
writeFileSync(OUTPUT_SCHEMA_PATH, header + generated);

console.log(`Wrote ${path.relative(ROOT, OUTPUT_SCHEMA_PATH)} from ${path.relative(ROOT, SOURCE_SCHEMA_PATH)}`);
