-- CreateTable
CREATE TABLE "ModelVersion" (
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
    "isSynthetic" BOOLEAN NOT NULL DEFAULT false,
    "metricsJson" TEXT,
    "featureImportanceJson" TEXT,
    "artifactPath" TEXT,
    "notes" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "PlaceProbabilityBand" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "predictionSnapshotId" TEXT NOT NULL,
    "topN" INTEGER NOT NULL,
    "probabilityRaw" REAL NOT NULL,
    "probabilityCalibrated" REAL NOT NULL,
    CONSTRAINT "PlaceProbabilityBand_predictionSnapshotId_fkey" FOREIGN KEY ("predictionSnapshotId") REFERENCES "PredictionSnapshot" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_PredictionSnapshot" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "runnerId" TEXT NOT NULL,
    "snapshotType" TEXT NOT NULL DEFAULT 'PRE_RACE',
    "modelVersion" TEXT NOT NULL,
    "modelVersionId" TEXT,
    "winProbability" REAL,
    "placeProbability" REAL,
    "placeBasisPlaces" INTEGER,
    "placeBasisBookmakerId" TEXT,
    "modelConfidence" REAL,
    "fairOddsDecimal" REAL,
    "marketImpliedProbability" REAL,
    "valueEdgeAbsolute" REAL,
    "valueEdgeRelative" REAL,
    "referenceOddsDecimal" REAL,
    "isLocked" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "PredictionSnapshot_runnerId_fkey" FOREIGN KEY ("runnerId") REFERENCES "Runner" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "PredictionSnapshot_modelVersionId_fkey" FOREIGN KEY ("modelVersionId") REFERENCES "ModelVersion" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);
INSERT INTO "new_PredictionSnapshot" ("createdAt", "fairOddsDecimal", "id", "isLocked", "marketImpliedProbability", "modelConfidence", "modelVersion", "placeBasisBookmakerId", "placeBasisPlaces", "placeProbability", "referenceOddsDecimal", "runnerId", "snapshotType", "valueEdgeAbsolute", "valueEdgeRelative", "winProbability") SELECT "createdAt", "fairOddsDecimal", "id", "isLocked", "marketImpliedProbability", "modelConfidence", "modelVersion", "placeBasisBookmakerId", "placeBasisPlaces", "placeProbability", "referenceOddsDecimal", "runnerId", "snapshotType", "valueEdgeAbsolute", "valueEdgeRelative", "winProbability" FROM "PredictionSnapshot";
DROP TABLE "PredictionSnapshot";
ALTER TABLE "new_PredictionSnapshot" RENAME TO "PredictionSnapshot";
CREATE INDEX "PredictionSnapshot_runnerId_idx" ON "PredictionSnapshot"("runnerId");
CREATE INDEX "PredictionSnapshot_snapshotType_idx" ON "PredictionSnapshot"("snapshotType");
CREATE INDEX "PredictionSnapshot_modelVersionId_idx" ON "PredictionSnapshot"("modelVersionId");
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;

-- CreateIndex
CREATE INDEX "ModelVersion_algorithm_idx" ON "ModelVersion"("algorithm");

-- CreateIndex
CREATE UNIQUE INDEX "ModelVersion_name_version_key" ON "ModelVersion"("name", "version");

-- CreateIndex
CREATE UNIQUE INDEX "PlaceProbabilityBand_predictionSnapshotId_topN_key" ON "PlaceProbabilityBand"("predictionSnapshotId", "topN");
