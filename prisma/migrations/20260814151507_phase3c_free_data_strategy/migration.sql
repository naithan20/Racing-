-- CreateTable
CREATE TABLE "DatasetReview" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "datasetName" TEXT NOT NULL,
    "source" TEXT NOT NULL,
    "licenceStated" TEXT,
    "licenceUrl" TEXT,
    "originalProvider" TEXT,
    "redistributionPermitted" BOOLEAN,
    "researchUsePermitted" BOOLEAN,
    "commercialUsePermitted" BOOLEAN,
    "provenanceConfidence" TEXT NOT NULL DEFAULT 'UNKNOWN',
    "reviewerNotes" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_DataProvenance" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "entityType" TEXT NOT NULL,
    "entityId" TEXT NOT NULL,
    "dataDomain" TEXT NOT NULL,
    "provider" TEXT NOT NULL,
    "providerRecordId" TEXT,
    "providerTimestamp" DATETIME,
    "retrievedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "effectiveAt" DATETIME,
    "sourceVersion" TEXT,
    "rawPayloadHash" TEXT,
    "provenanceStatus" TEXT NOT NULL DEFAULT 'UNKNOWN',
    "sourceUrl" TEXT,
    "importBatchId" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "DataProvenance_importBatchId_fkey" FOREIGN KEY ("importBatchId") REFERENCES "ImportBatch" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);
INSERT INTO "new_DataProvenance" ("createdAt", "dataDomain", "effectiveAt", "entityId", "entityType", "id", "importBatchId", "provider", "providerRecordId", "providerTimestamp", "rawPayloadHash", "retrievedAt", "sourceVersion") SELECT "createdAt", "dataDomain", "effectiveAt", "entityId", "entityType", "id", "importBatchId", "provider", "providerRecordId", "providerTimestamp", "rawPayloadHash", "retrievedAt", "sourceVersion" FROM "DataProvenance";
DROP TABLE "DataProvenance";
ALTER TABLE "new_DataProvenance" RENAME TO "DataProvenance";
CREATE INDEX "DataProvenance_entityType_entityId_idx" ON "DataProvenance"("entityType", "entityId");
CREATE INDEX "DataProvenance_dataDomain_idx" ON "DataProvenance"("dataDomain");
CREATE INDEX "DataProvenance_provider_idx" ON "DataProvenance"("provider");
CREATE INDEX "DataProvenance_importBatchId_idx" ON "DataProvenance"("importBatchId");
CREATE INDEX "DataProvenance_provenanceStatus_idx" ON "DataProvenance"("provenanceStatus");
CREATE TABLE "new_ModelVersion" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "version" TEXT NOT NULL,
    "featureSetVersion" TEXT NOT NULL,
    "algorithm" TEXT NOT NULL,
    "hyperparameters" TEXT NOT NULL,
    "calibrationMethod" TEXT NOT NULL,
    "trainingStartDate" DATETIME NOT NULL,
    "trainingEndDate" DATETIME NOT NULL,
    "validationStartDate" DATETIME,
    "validationEndDate" DATETIME,
    "testStartDate" DATETIME,
    "testEndDate" DATETIME,
    "trainingRowCount" INTEGER NOT NULL,
    "trainingRaceCount" INTEGER NOT NULL,
    "datasetVersionId" TEXT,
    "isSynthetic" BOOLEAN NOT NULL DEFAULT false,
    "featureProfile" TEXT NOT NULL DEFAULT 'FULL_MODEL',
    "metricsJson" TEXT,
    "featureImportanceJson" TEXT,
    "artifactPath" TEXT,
    "notes" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "ModelVersion_datasetVersionId_fkey" FOREIGN KEY ("datasetVersionId") REFERENCES "DatasetVersion" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);
INSERT INTO "new_ModelVersion" ("algorithm", "artifactPath", "calibrationMethod", "createdAt", "datasetVersionId", "featureImportanceJson", "featureSetVersion", "hyperparameters", "id", "isSynthetic", "metricsJson", "name", "notes", "testEndDate", "testStartDate", "trainingEndDate", "trainingRaceCount", "trainingRowCount", "trainingStartDate", "validationEndDate", "validationStartDate", "version") SELECT "algorithm", "artifactPath", "calibrationMethod", "createdAt", "datasetVersionId", "featureImportanceJson", "featureSetVersion", "hyperparameters", "id", "isSynthetic", "metricsJson", "name", "notes", "testEndDate", "testStartDate", "trainingEndDate", "trainingRaceCount", "trainingRowCount", "trainingStartDate", "validationEndDate", "validationStartDate", "version" FROM "ModelVersion";
DROP TABLE "ModelVersion";
ALTER TABLE "new_ModelVersion" RENAME TO "ModelVersion";
CREATE INDEX "ModelVersion_algorithm_idx" ON "ModelVersion"("algorithm");
CREATE INDEX "ModelVersion_datasetVersionId_idx" ON "ModelVersion"("datasetVersionId");
CREATE UNIQUE INDEX "ModelVersion_name_version_key" ON "ModelVersion"("name", "version");
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;

-- CreateIndex
CREATE INDEX "DatasetReview_provenanceConfidence_idx" ON "DatasetReview"("provenanceConfidence");
