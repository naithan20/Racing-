-- CreateTable
CREATE TABLE "DataSourceConnection" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "sourceId" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'NOT_CONNECTED',
    "connectedAt" DATETIME,
    "lastSyncAt" DATETIME,
    "errorMessage" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "ImportJob" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "sourceId" TEXT NOT NULL,
    "connectionId" TEXT,
    "status" TEXT NOT NULL DEFAULT 'PENDING',
    "progressPercent" INTEGER NOT NULL DEFAULT 0,
    "currentStepLabel" TEXT,
    "downloadUrl" TEXT,
    "downloadedFilePath" TEXT,
    "mappingFilePath" TEXT,
    "provenanceStatus" TEXT,
    "sourceLabel" TEXT,
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

-- CreateIndex
CREATE UNIQUE INDEX "DataSourceConnection_sourceId_key" ON "DataSourceConnection"("sourceId");

-- CreateIndex
CREATE INDEX "DataSourceConnection_sourceId_idx" ON "DataSourceConnection"("sourceId");

-- CreateIndex
CREATE INDEX "ImportJob_sourceId_idx" ON "ImportJob"("sourceId");

-- CreateIndex
CREATE INDEX "ImportJob_status_idx" ON "ImportJob"("status");

-- CreateIndex
CREATE INDEX "ImportJob_connectionId_idx" ON "ImportJob"("connectionId");
