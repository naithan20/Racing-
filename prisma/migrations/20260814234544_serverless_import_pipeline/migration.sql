-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_ImportJob" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "sourceId" TEXT NOT NULL,
    "connectionId" TEXT,
    "status" TEXT NOT NULL DEFAULT 'PENDING',
    "runtime" TEXT NOT NULL DEFAULT 'PYTHON_CLI',
    "progressPercent" INTEGER NOT NULL DEFAULT 0,
    "currentStepLabel" TEXT,
    "downloadUrl" TEXT,
    "downloadedFilePath" TEXT,
    "mappingFilePath" TEXT,
    "mappingDataJson" TEXT,
    "provenanceStatus" TEXT,
    "sourceLabel" TEXT,
    "paramsJson" TEXT,
    "datasetVersionId" TEXT,
    "importBatchId" TEXT,
    "racesImported" INTEGER,
    "runnersImported" INTEGER,
    "errorMessage" TEXT,
    "logJson" TEXT,
    "startedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "completedAt" DATETIME,
    CONSTRAINT "ImportJob_connectionId_fkey" FOREIGN KEY ("connectionId") REFERENCES "DataSourceConnection" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);
INSERT INTO "new_ImportJob" ("completedAt", "connectionId", "currentStepLabel", "datasetVersionId", "downloadUrl", "downloadedFilePath", "errorMessage", "id", "importBatchId", "logJson", "mappingFilePath", "paramsJson", "progressPercent", "provenanceStatus", "racesImported", "runnersImported", "sourceId", "sourceLabel", "startedAt", "status", "updatedAt") SELECT "completedAt", "connectionId", "currentStepLabel", "datasetVersionId", "downloadUrl", "downloadedFilePath", "errorMessage", "id", "importBatchId", "logJson", "mappingFilePath", "paramsJson", "progressPercent", "provenanceStatus", "racesImported", "runnersImported", "sourceId", "sourceLabel", "startedAt", "status", "updatedAt" FROM "ImportJob";
DROP TABLE "ImportJob";
ALTER TABLE "new_ImportJob" RENAME TO "ImportJob";
CREATE INDEX "ImportJob_sourceId_idx" ON "ImportJob"("sourceId");
CREATE INDEX "ImportJob_status_idx" ON "ImportJob"("status");
CREATE INDEX "ImportJob_connectionId_idx" ON "ImportJob"("connectionId");
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
