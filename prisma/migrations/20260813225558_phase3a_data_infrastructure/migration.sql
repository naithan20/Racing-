-- AlterTable
ALTER TABLE "RunnerMarketPrice" ADD COLUMN "availableVolume" REAL;
ALTER TABLE "RunnerMarketPrice" ADD COLUMN "backOddsDecimal" REAL;
ALTER TABLE "RunnerMarketPrice" ADD COLUMN "layOddsDecimal" REAL;
ALTER TABLE "RunnerMarketPrice" ADD COLUMN "marketStatus" TEXT;

-- CreateTable
CREATE TABLE "DataProvenance" (
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
    "importBatchId" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "DataProvenance_importBatchId_fkey" FOREIGN KEY ("importBatchId") REFERENCES "ImportBatch" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "RaceFieldHistory" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "raceId" TEXT NOT NULL,
    "fieldName" TEXT NOT NULL,
    "fieldValue" TEXT,
    "effectiveAt" DATETIME NOT NULL,
    "source" TEXT,
    "importBatchId" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "RaceFieldHistory_raceId_fkey" FOREIGN KEY ("raceId") REFERENCES "Race" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "RunnerFieldHistory" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "runnerId" TEXT NOT NULL,
    "fieldName" TEXT NOT NULL,
    "fieldValue" TEXT,
    "effectiveAt" DATETIME NOT NULL,
    "source" TEXT,
    "importBatchId" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "RunnerFieldHistory_runnerId_fkey" FOREIGN KEY ("runnerId") REFERENCES "Runner" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "RacePlaceTermsHistory" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "racePlaceTermsId" TEXT NOT NULL,
    "raceId" TEXT NOT NULL,
    "bookmakerId" TEXT NOT NULL,
    "places" INTEGER NOT NULL,
    "eachWayFraction" REAL NOT NULL,
    "extraPlaces" BOOLEAN NOT NULL DEFAULT false,
    "terms" TEXT,
    "effectiveAt" DATETIME NOT NULL,
    "supersededAt" DATETIME,
    "source" TEXT,
    "importBatchId" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "RacePlaceTermsHistory_racePlaceTermsId_fkey" FOREIGN KEY ("racePlaceTermsId") REFERENCES "RacePlaceTerms" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "RunnerSectionalPoint" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "runnerId" TEXT NOT NULL,
    "segmentIndex" INTEGER NOT NULL,
    "segmentDistanceFurlongs" REAL,
    "segmentTimeSeconds" REAL,
    "speedMps" REAL,
    "positionInRace" INTEGER,
    "strideLength" REAL,
    "strideFrequency" REAL,
    "latitude" REAL,
    "longitude" REAL,
    "source" TEXT,
    "importBatchId" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "RunnerSectionalPoint_runnerId_fkey" FOREIGN KEY ("runnerId") REFERENCES "Runner" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "EntityAlias" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "entityType" TEXT NOT NULL,
    "canonicalId" TEXT NOT NULL,
    "rawName" TEXT NOT NULL,
    "normalizedName" TEXT NOT NULL,
    "providerName" TEXT,
    "providerId" TEXT,
    "matchMethod" TEXT NOT NULL,
    "confidence" REAL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "EntityResolutionQueueItem" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "entityType" TEXT NOT NULL,
    "rawName" TEXT NOT NULL,
    "normalizedName" TEXT NOT NULL,
    "providerName" TEXT,
    "candidateCanonicalIdsJson" TEXT,
    "status" TEXT NOT NULL DEFAULT 'PENDING',
    "resolvedCanonicalId" TEXT,
    "resolvedBy" TEXT,
    "resolvedAt" DATETIME,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "DatasetVersion" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "sourceType" TEXT NOT NULL,
    "providersJson" TEXT NOT NULL,
    "dateRangeStart" DATETIME NOT NULL,
    "dateRangeEnd" DATETIME NOT NULL,
    "raceCount" INTEGER NOT NULL,
    "runnerCount" INTEGER NOT NULL,
    "dataQualityMetricsJson" TEXT,
    "schemaVersion" TEXT NOT NULL,
    "importBatchIdsJson" TEXT,
    "notes" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "LeakageAuditRun" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "datasetVersionId" TEXT,
    "modelVersionId" TEXT,
    "status" TEXT NOT NULL,
    "featuresChecked" INTEGER NOT NULL,
    "violationsFound" INTEGER NOT NULL DEFAULT 0,
    "reportJson" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "LeakageAuditRun_datasetVersionId_fkey" FOREIGN KEY ("datasetVersionId") REFERENCES "DatasetVersion" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "LeakageAuditRun_modelVersionId_fkey" FOREIGN KEY ("modelVersionId") REFERENCES "ModelVersion" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_FormEntry" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "isSampleData" BOOLEAN NOT NULL DEFAULT false,
    "horseId" TEXT NOT NULL,
    "linkedRaceId" TEXT,
    "raceDate" DATETIME NOT NULL,
    "course" TEXT NOT NULL,
    "country" TEXT,
    "distanceFurlongs" REAL,
    "going" TEXT,
    "raceClass" INTEGER,
    "flatJumps" TEXT,
    "fieldSize" INTEGER,
    "finishingPosition" INTEGER,
    "finishStatus" TEXT,
    "beatenDistanceLengths" REAL,
    "startingPriceDecimal" REAL,
    "officialRating" INTEGER,
    "weightPounds" INTEGER,
    "draw" INTEGER,
    "jockeyName" TEXT,
    "headgear" TEXT,
    "raceComment" TEXT,
    "inRunningComment" TEXT,
    "earlyPosition" INTEGER,
    "halfwayPosition" INTEGER,
    "position3fOut" INTEGER,
    "position2fOut" INTEGER,
    "position1fOut" INTEGER,
    "sectionalTimes" TEXT,
    "finishingSpeedPercentage" REAL,
    "paceClassification" TEXT,
    "raceStrengthIndex" REAL,
    "winnerSubsequentPerformance" TEXT,
    "collateralFormNotes" TEXT,
    "hasPositionalData" BOOLEAN NOT NULL DEFAULT false,
    "hasSectionalData" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "FormEntry_horseId_fkey" FOREIGN KEY ("horseId") REFERENCES "Horse" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);
INSERT INTO "new_FormEntry" ("beatenDistanceLengths", "collateralFormNotes", "country", "course", "createdAt", "distanceFurlongs", "draw", "earlyPosition", "fieldSize", "finishStatus", "finishingPosition", "finishingSpeedPercentage", "flatJumps", "going", "halfwayPosition", "headgear", "horseId", "id", "inRunningComment", "isSampleData", "jockeyName", "linkedRaceId", "officialRating", "paceClassification", "position1fOut", "position2fOut", "position3fOut", "raceClass", "raceComment", "raceDate", "raceStrengthIndex", "sectionalTimes", "startingPriceDecimal", "weightPounds", "winnerSubsequentPerformance") SELECT "beatenDistanceLengths", "collateralFormNotes", "country", "course", "createdAt", "distanceFurlongs", "draw", "earlyPosition", "fieldSize", "finishStatus", "finishingPosition", "finishingSpeedPercentage", "flatJumps", "going", "halfwayPosition", "headgear", "horseId", "id", "inRunningComment", "isSampleData", "jockeyName", "linkedRaceId", "officialRating", "paceClassification", "position1fOut", "position2fOut", "position3fOut", "raceClass", "raceComment", "raceDate", "raceStrengthIndex", "sectionalTimes", "startingPriceDecimal", "weightPounds", "winnerSubsequentPerformance" FROM "FormEntry";
DROP TABLE "FormEntry";
ALTER TABLE "new_FormEntry" RENAME TO "FormEntry";
CREATE INDEX "FormEntry_horseId_idx" ON "FormEntry"("horseId");
CREATE INDEX "FormEntry_raceDate_idx" ON "FormEntry"("raceDate");
CREATE INDEX "FormEntry_course_idx" ON "FormEntry"("course");
CREATE TABLE "new_Horse" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "isSampleData" BOOLEAN NOT NULL DEFAULT false,
    "sourceType" TEXT NOT NULL DEFAULT 'SAMPLE',
    "name" TEXT NOT NULL,
    "countryBred" TEXT,
    "yearOfBirth" INTEGER,
    "sex" TEXT,
    "sireName" TEXT,
    "damName" TEXT,
    "damsireName" TEXT,
    "trainerName" TEXT,
    "ownerName" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);
INSERT INTO "new_Horse" ("countryBred", "createdAt", "damName", "damsireName", "id", "isSampleData", "name", "ownerName", "sex", "sireName", "trainerName", "updatedAt", "yearOfBirth") SELECT "countryBred", "createdAt", "damName", "damsireName", "id", "isSampleData", "name", "ownerName", "sex", "sireName", "trainerName", "updatedAt", "yearOfBirth" FROM "Horse";
DROP TABLE "Horse";
ALTER TABLE "new_Horse" RENAME TO "Horse";
CREATE INDEX "Horse_name_idx" ON "Horse"("name");
CREATE INDEX "Horse_sourceType_idx" ON "Horse"("sourceType");
CREATE TABLE "new_ImportBatch" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "sourceType" TEXT NOT NULL,
    "filename" TEXT,
    "status" TEXT NOT NULL DEFAULT 'PENDING',
    "rowCount" INTEGER,
    "successCount" INTEGER,
    "errorCount" INTEGER,
    "errorLog" TEXT,
    "totalRows" INTEGER,
    "processedRows" INTEGER,
    "duplicateRows" INTEGER,
    "resumeCursor" TEXT,
    "idempotencyKey" TEXT,
    "providerName" TEXT,
    "datasetVersionId" TEXT,
    "importedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "ImportBatch_datasetVersionId_fkey" FOREIGN KEY ("datasetVersionId") REFERENCES "DatasetVersion" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);
INSERT INTO "new_ImportBatch" ("errorCount", "errorLog", "filename", "id", "importedAt", "rowCount", "sourceType", "status", "successCount") SELECT "errorCount", "errorLog", "filename", "id", "importedAt", "rowCount", "sourceType", "status", "successCount" FROM "ImportBatch";
DROP TABLE "ImportBatch";
ALTER TABLE "new_ImportBatch" RENAME TO "ImportBatch";
CREATE UNIQUE INDEX "ImportBatch_idempotencyKey_key" ON "ImportBatch"("idempotencyKey");
CREATE INDEX "ImportBatch_providerName_idx" ON "ImportBatch"("providerName");
CREATE INDEX "ImportBatch_datasetVersionId_idx" ON "ImportBatch"("datasetVersionId");
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
    "metricsJson" TEXT,
    "featureImportanceJson" TEXT,
    "artifactPath" TEXT,
    "notes" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "ModelVersion_datasetVersionId_fkey" FOREIGN KEY ("datasetVersionId") REFERENCES "DatasetVersion" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);
INSERT INTO "new_ModelVersion" ("algorithm", "artifactPath", "calibrationMethod", "createdAt", "featureImportanceJson", "featureSetVersion", "hyperparameters", "id", "isSynthetic", "metricsJson", "name", "notes", "testEndDate", "testStartDate", "trainingEndDate", "trainingRaceCount", "trainingRowCount", "trainingStartDate", "validationEndDate", "validationStartDate", "version") SELECT "algorithm", "artifactPath", "calibrationMethod", "createdAt", "featureImportanceJson", "featureSetVersion", "hyperparameters", "id", "isSynthetic", "metricsJson", "name", "notes", "testEndDate", "testStartDate", "trainingEndDate", "trainingRaceCount", "trainingRowCount", "trainingStartDate", "validationEndDate", "validationStartDate", "version" FROM "ModelVersion";
DROP TABLE "ModelVersion";
ALTER TABLE "new_ModelVersion" RENAME TO "ModelVersion";
CREATE INDEX "ModelVersion_algorithm_idx" ON "ModelVersion"("algorithm");
CREATE INDEX "ModelVersion_datasetVersionId_idx" ON "ModelVersion"("datasetVersionId");
CREATE UNIQUE INDEX "ModelVersion_name_version_key" ON "ModelVersion"("name", "version");
CREATE TABLE "new_Race" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "isSampleData" BOOLEAN NOT NULL DEFAULT false,
    "sourceType" TEXT NOT NULL DEFAULT 'SAMPLE',
    "date" DATETIME NOT NULL,
    "raceTime" TEXT NOT NULL,
    "racecourse" TEXT NOT NULL,
    "country" TEXT NOT NULL,
    "raceName" TEXT NOT NULL,
    "raceType" TEXT,
    "flatJumps" TEXT NOT NULL,
    "surface" TEXT NOT NULL,
    "distanceYards" INTEGER,
    "distanceFurlongs" REAL NOT NULL,
    "raceClass" INTEGER,
    "gradeGroup" TEXT,
    "handicapType" TEXT NOT NULL,
    "ageRestriction" TEXT,
    "sexRestriction" TEXT,
    "numberOfRunners" INTEGER NOT NULL,
    "going" TEXT,
    "goingDescription" TEXT,
    "railPosition" TEXT,
    "stallsPosition" TEXT,
    "weatherSummary" TEXT,
    "temperatureCelsius" REAL,
    "windSummary" TEXT,
    "precipitationMm" REAL,
    "prizeMoneyTotal" REAL,
    "currency" TEXT NOT NULL DEFAULT 'GBP',
    "eachWayFraction" REAL,
    "bookmakerPlaces" INTEGER,
    "extraPlaceFlag" BOOLEAN NOT NULL DEFAULT false,
    "raceStatus" TEXT NOT NULL DEFAULT 'SCHEDULED',
    "resultStatus" TEXT NOT NULL DEFAULT 'PENDING',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "importBatchId" TEXT,
    CONSTRAINT "Race_importBatchId_fkey" FOREIGN KEY ("importBatchId") REFERENCES "ImportBatch" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);
INSERT INTO "new_Race" ("ageRestriction", "bookmakerPlaces", "country", "createdAt", "currency", "date", "distanceFurlongs", "distanceYards", "eachWayFraction", "extraPlaceFlag", "flatJumps", "going", "goingDescription", "gradeGroup", "handicapType", "id", "importBatchId", "isSampleData", "numberOfRunners", "precipitationMm", "prizeMoneyTotal", "raceClass", "raceName", "raceStatus", "raceTime", "raceType", "racecourse", "railPosition", "resultStatus", "sexRestriction", "stallsPosition", "surface", "temperatureCelsius", "updatedAt", "weatherSummary", "windSummary") SELECT "ageRestriction", "bookmakerPlaces", "country", "createdAt", "currency", "date", "distanceFurlongs", "distanceYards", "eachWayFraction", "extraPlaceFlag", "flatJumps", "going", "goingDescription", "gradeGroup", "handicapType", "id", "importBatchId", "isSampleData", "numberOfRunners", "precipitationMm", "prizeMoneyTotal", "raceClass", "raceName", "raceStatus", "raceTime", "raceType", "racecourse", "railPosition", "resultStatus", "sexRestriction", "stallsPosition", "surface", "temperatureCelsius", "updatedAt", "weatherSummary", "windSummary" FROM "Race";
DROP TABLE "Race";
ALTER TABLE "new_Race" RENAME TO "Race";
CREATE INDEX "Race_date_idx" ON "Race"("date");
CREATE INDEX "Race_racecourse_idx" ON "Race"("racecourse");
CREATE INDEX "Race_country_idx" ON "Race"("country");
CREATE INDEX "Race_sourceType_idx" ON "Race"("sourceType");
CREATE TABLE "new_RacePlaceTerms" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "raceId" TEXT NOT NULL,
    "bookmakerId" TEXT NOT NULL,
    "places" INTEGER NOT NULL,
    "eachWayFraction" REAL NOT NULL,
    "extraPlaces" BOOLEAN NOT NULL DEFAULT false,
    "terms" TEXT,
    "effectiveAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "RacePlaceTerms_raceId_fkey" FOREIGN KEY ("raceId") REFERENCES "Race" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "RacePlaceTerms_bookmakerId_fkey" FOREIGN KEY ("bookmakerId") REFERENCES "Bookmaker" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
INSERT INTO "new_RacePlaceTerms" ("bookmakerId", "createdAt", "eachWayFraction", "extraPlaces", "id", "places", "raceId", "terms") SELECT "bookmakerId", "createdAt", "eachWayFraction", "extraPlaces", "id", "places", "raceId", "terms" FROM "RacePlaceTerms";
DROP TABLE "RacePlaceTerms";
ALTER TABLE "new_RacePlaceTerms" RENAME TO "RacePlaceTerms";
CREATE UNIQUE INDEX "RacePlaceTerms_raceId_bookmakerId_key" ON "RacePlaceTerms"("raceId", "bookmakerId");
CREATE TABLE "new_ResultEntry" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "runnerId" TEXT NOT NULL,
    "finishingPosition" INTEGER,
    "finishStatus" TEXT,
    "beatenDistanceLengths" REAL,
    "deadHeat" BOOLEAN NOT NULL DEFAULT false,
    "startingPriceDecimal" REAL,
    "closingOddsDecimal" REAL,
    "bspDecimal" REAL,
    "placeOutcome" BOOLEAN,
    "profitLossWinStake" REAL,
    "profitLossEachWayStake" REAL,
    "resultStatus" TEXT NOT NULL DEFAULT 'PENDING',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "ResultEntry_runnerId_fkey" FOREIGN KEY ("runnerId") REFERENCES "Runner" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);
INSERT INTO "new_ResultEntry" ("beatenDistanceLengths", "closingOddsDecimal", "createdAt", "finishStatus", "finishingPosition", "id", "placeOutcome", "profitLossEachWayStake", "profitLossWinStake", "resultStatus", "runnerId", "startingPriceDecimal", "updatedAt") SELECT "beatenDistanceLengths", "closingOddsDecimal", "createdAt", "finishStatus", "finishingPosition", "id", "placeOutcome", "profitLossEachWayStake", "profitLossWinStake", "resultStatus", "runnerId", "startingPriceDecimal", "updatedAt" FROM "ResultEntry";
DROP TABLE "ResultEntry";
ALTER TABLE "new_ResultEntry" RENAME TO "ResultEntry";
CREATE UNIQUE INDEX "ResultEntry_runnerId_key" ON "ResultEntry"("runnerId");
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;

-- CreateIndex
CREATE INDEX "DataProvenance_entityType_entityId_idx" ON "DataProvenance"("entityType", "entityId");

-- CreateIndex
CREATE INDEX "DataProvenance_dataDomain_idx" ON "DataProvenance"("dataDomain");

-- CreateIndex
CREATE INDEX "DataProvenance_provider_idx" ON "DataProvenance"("provider");

-- CreateIndex
CREATE INDEX "DataProvenance_importBatchId_idx" ON "DataProvenance"("importBatchId");

-- CreateIndex
CREATE INDEX "RaceFieldHistory_raceId_fieldName_effectiveAt_idx" ON "RaceFieldHistory"("raceId", "fieldName", "effectiveAt");

-- CreateIndex
CREATE INDEX "RunnerFieldHistory_runnerId_fieldName_effectiveAt_idx" ON "RunnerFieldHistory"("runnerId", "fieldName", "effectiveAt");

-- CreateIndex
CREATE INDEX "RacePlaceTermsHistory_raceId_bookmakerId_effectiveAt_idx" ON "RacePlaceTermsHistory"("raceId", "bookmakerId", "effectiveAt");

-- CreateIndex
CREATE INDEX "RunnerSectionalPoint_runnerId_segmentIndex_idx" ON "RunnerSectionalPoint"("runnerId", "segmentIndex");

-- CreateIndex
CREATE INDEX "EntityAlias_entityType_normalizedName_idx" ON "EntityAlias"("entityType", "normalizedName");

-- CreateIndex
CREATE INDEX "EntityAlias_canonicalId_idx" ON "EntityAlias"("canonicalId");

-- CreateIndex
CREATE UNIQUE INDEX "EntityAlias_entityType_providerName_providerId_key" ON "EntityAlias"("entityType", "providerName", "providerId");

-- CreateIndex
CREATE INDEX "EntityResolutionQueueItem_entityType_status_idx" ON "EntityResolutionQueueItem"("entityType", "status");

-- CreateIndex
CREATE INDEX "DatasetVersion_sourceType_idx" ON "DatasetVersion"("sourceType");

-- CreateIndex
CREATE INDEX "LeakageAuditRun_datasetVersionId_idx" ON "LeakageAuditRun"("datasetVersionId");

-- CreateIndex
CREATE INDEX "LeakageAuditRun_modelVersionId_idx" ON "LeakageAuditRun"("modelVersionId");

-- CreateIndex
CREATE INDEX "LeakageAuditRun_status_idx" ON "LeakageAuditRun"("status");
