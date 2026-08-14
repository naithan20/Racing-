import { PrismaBetterSqlite3 } from "@prisma/adapter-better-sqlite3";
import { PrismaPg } from "@prisma/adapter-pg";

import { PrismaClient } from "@/generated/prisma/client";

const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };

// The generated client's SQL dialect is fixed at `prisma generate` time by
// which schema produced it (prisma/schema.prisma for local SQLite dev,
// prisma/postgres/schema.prisma for Vercel/production — see
// scripts/generate-postgres-schema.mjs). This just has to pick the
// matching DRIVER ADAPTER for whichever DATABASE_URL is actually
// configured in this environment; the two are always kept in sync by the
// build scripts (`npm run build` generates the SQLite client, `npm run
// vercel-build` generates the Postgres one).
function isPostgresUrl(url: string): boolean {
  return url.startsWith("postgres://") || url.startsWith("postgresql://");
}

function createClient() {
  const url = process.env.DATABASE_URL ?? "file:./dev.db";
  const adapter = isPostgresUrl(url) ? new PrismaPg({ connectionString: url }) : new PrismaBetterSqlite3({ url });
  return new PrismaClient({ adapter });
}

export const prisma = globalForPrisma.prisma ?? createClient();

if (process.env.NODE_ENV !== "production") {
  globalForPrisma.prisma = prisma;
}
