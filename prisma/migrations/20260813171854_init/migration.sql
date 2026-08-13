-- CreateTable
CREATE TABLE "Race" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "isSampleData" BOOLEAN NOT NULL DEFAULT false,
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

-- CreateTable
CREATE TABLE "RacePlaceTerms" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "raceId" TEXT NOT NULL,
    "bookmakerId" TEXT NOT NULL,
    "places" INTEGER NOT NULL,
    "eachWayFraction" REAL NOT NULL,
    "extraPlaces" BOOLEAN NOT NULL DEFAULT false,
    "terms" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "RacePlaceTerms_raceId_fkey" FOREIGN KEY ("raceId") REFERENCES "Race" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "RacePlaceTerms_bookmakerId_fkey" FOREIGN KEY ("bookmakerId") REFERENCES "Bookmaker" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Horse" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "isSampleData" BOOLEAN NOT NULL DEFAULT false,
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

-- CreateTable
CREATE TABLE "Runner" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "isSampleData" BOOLEAN NOT NULL DEFAULT false,
    "raceId" TEXT NOT NULL,
    "horseId" TEXT NOT NULL,
    "clothNumber" INTEGER,
    "draw" INTEGER,
    "ageAtRace" INTEGER,
    "weightStone" INTEGER,
    "weightPounds" INTEGER,
    "weightLbsTotal" INTEGER,
    "officialRating" INTEGER,
    "racingPostRating" INTEGER,
    "timeformRating" INTEGER,
    "topspeedRating" INTEGER,
    "jockeyName" TEXT,
    "jockeyClaimLbs" INTEGER,
    "trainerName" TEXT,
    "headgear" TEXT,
    "firstTimeHeadgear" BOOLEAN NOT NULL DEFAULT false,
    "daysSinceLastRun" INTEGER,
    "currentOddsDecimal" REAL,
    "currentOddsFractional" TEXT,
    "openingOddsDecimal" REAL,
    "startingPriceDecimal" REAL,
    "exchangePriceDecimal" REAL,
    "nonRunner" BOOLEAN NOT NULL DEFAULT false,
    "favouriteRank" INTEGER,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Runner_raceId_fkey" FOREIGN KEY ("raceId") REFERENCES "Race" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "Runner_horseId_fkey" FOREIGN KEY ("horseId") REFERENCES "Horse" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "FormEntry" (
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
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "FormEntry_horseId_fkey" FOREIGN KEY ("horseId") REFERENCES "Horse" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "FeatureDefinition" (
    "key" TEXT NOT NULL PRIMARY KEY,
    "category" TEXT NOT NULL,
    "label" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "valueType" TEXT NOT NULL,
    "unit" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "Feature" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "runnerId" TEXT NOT NULL,
    "key" TEXT NOT NULL,
    "numericValue" REAL,
    "textValue" TEXT,
    "booleanValue" BOOLEAN,
    "computedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "modelVersion" TEXT,
    "sourceNote" TEXT,
    CONSTRAINT "Feature_runnerId_fkey" FOREIGN KEY ("runnerId") REFERENCES "Runner" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "Feature_key_fkey" FOREIGN KEY ("key") REFERENCES "FeatureDefinition" ("key") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "EvidenceProfile" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "horseId" TEXT NOT NULL,
    "careerStarts" INTEGER NOT NULL DEFAULT 0,
    "startsLast12Months" INTEGER NOT NULL DEFAULT 0,
    "startsAtCourse" INTEGER NOT NULL DEFAULT 0,
    "startsAtDistance" INTEGER NOT NULL DEFAULT 0,
    "startsOnGoing" INTEGER NOT NULL DEFAULT 0,
    "evidenceDensityScore" REAL,
    "evidenceDensityLabel" TEXT,
    "uncertaintyNote" TEXT,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "EvidenceProfile_horseId_fkey" FOREIGN KEY ("horseId") REFERENCES "Horse" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "RunnerPaceProfile" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "runnerId" TEXT NOT NULL,
    "projectedRole" TEXT NOT NULL DEFAULT 'UNKNOWN',
    "usualEarlyPosition" REAL,
    "breaksQuicklyRate" REAL,
    "slowStartRate" REAL,
    "energyToObtainPositionIndex" REAL,
    "positionChange3fTo2f" REAL,
    "positionChange2fTo1f" REAL,
    "relativeAccelerationIndex" REAL,
    "finishingSpeedIndex" REAL,
    "positionChangeFinalFurlong" REAL,
    "weakensLateRate" REAL,
    "staysOnStronglyRate" REAL,
    "competitionForLeadIndex" REAL,
    "pacePressureIndex" REAL,
    "paceCollapseProbability" REAL,
    "notes" TEXT,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "RunnerPaceProfile_runnerId_fkey" FOREIGN KEY ("runnerId") REFERENCES "Runner" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Bookmaker" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "isExchange" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "RunnerMarketPrice" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "runnerId" TEXT NOT NULL,
    "bookmakerId" TEXT NOT NULL,
    "timestamp" DATETIME NOT NULL,
    "winOddsDecimal" REAL NOT NULL,
    "eachWayFraction" REAL,
    "numberOfPlaces" INTEGER,
    "extraPlaces" BOOLEAN NOT NULL DEFAULT false,
    "isOpeningPrice" BOOLEAN NOT NULL DEFAULT false,
    "isStartingPrice" BOOLEAN NOT NULL DEFAULT false,
    "isClosingPrice" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "RunnerMarketPrice_runnerId_fkey" FOREIGN KEY ("runnerId") REFERENCES "Runner" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "RunnerMarketPrice_bookmakerId_fkey" FOREIGN KEY ("bookmakerId") REFERENCES "Bookmaker" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "PredictionSnapshot" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "runnerId" TEXT NOT NULL,
    "snapshotType" TEXT NOT NULL DEFAULT 'PRE_RACE',
    "modelVersion" TEXT NOT NULL,
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
    CONSTRAINT "PredictionSnapshot_runnerId_fkey" FOREIGN KEY ("runnerId") REFERENCES "Runner" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "ResultEntry" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "runnerId" TEXT NOT NULL,
    "finishingPosition" INTEGER,
    "finishStatus" TEXT,
    "beatenDistanceLengths" REAL,
    "startingPriceDecimal" REAL,
    "closingOddsDecimal" REAL,
    "placeOutcome" BOOLEAN,
    "profitLossWinStake" REAL,
    "profitLossEachWayStake" REAL,
    "resultStatus" TEXT NOT NULL DEFAULT 'PENDING',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "ResultEntry_runnerId_fkey" FOREIGN KEY ("runnerId") REFERENCES "Runner" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "RunnerObservation" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "resultId" TEXT NOT NULL,
    "tag" TEXT,
    "freeText" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "RunnerObservation_resultId_fkey" FOREIGN KEY ("resultId") REFERENCES "ResultEntry" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Lucky15Slip" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT,
    "date" DATETIME NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "minOddsDecimal" REAL,
    "maxOddsDecimal" REAL,
    "minConfidence" REAL,
    "minPlaceEdge" REAL,
    "minRunners" INTEGER,
    "enhancedPlacesOnly" BOOLEAN NOT NULL DEFAULT false,
    "flatJumpsFilter" TEXT,
    "countryFilter" TEXT,
    "bookmakerId" TEXT
);

-- CreateTable
CREATE TABLE "Lucky15Leg" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "slipId" TEXT NOT NULL,
    "runnerId" TEXT NOT NULL,
    "selectionType" TEXT NOT NULL DEFAULT 'LUCKY_15_LEG',
    "rationale" TEXT,
    "sortOrder" INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT "Lucky15Leg_slipId_fkey" FOREIGN KEY ("slipId") REFERENCES "Lucky15Slip" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "Lucky15Leg_runnerId_fkey" FOREIGN KEY ("runnerId") REFERENCES "Runner" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "ImportBatch" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "sourceType" TEXT NOT NULL,
    "filename" TEXT,
    "status" TEXT NOT NULL DEFAULT 'PENDING',
    "rowCount" INTEGER,
    "successCount" INTEGER,
    "errorCount" INTEGER,
    "errorLog" TEXT,
    "importedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateIndex
CREATE INDEX "Race_date_idx" ON "Race"("date");

-- CreateIndex
CREATE INDEX "Race_racecourse_idx" ON "Race"("racecourse");

-- CreateIndex
CREATE INDEX "Race_country_idx" ON "Race"("country");

-- CreateIndex
CREATE UNIQUE INDEX "RacePlaceTerms_raceId_bookmakerId_key" ON "RacePlaceTerms"("raceId", "bookmakerId");

-- CreateIndex
CREATE INDEX "Horse_name_idx" ON "Horse"("name");

-- CreateIndex
CREATE INDEX "Runner_raceId_idx" ON "Runner"("raceId");

-- CreateIndex
CREATE INDEX "Runner_horseId_idx" ON "Runner"("horseId");

-- CreateIndex
CREATE UNIQUE INDEX "Runner_raceId_horseId_key" ON "Runner"("raceId", "horseId");

-- CreateIndex
CREATE INDEX "FormEntry_horseId_idx" ON "FormEntry"("horseId");

-- CreateIndex
CREATE INDEX "FormEntry_raceDate_idx" ON "FormEntry"("raceDate");

-- CreateIndex
CREATE INDEX "FormEntry_course_idx" ON "FormEntry"("course");

-- CreateIndex
CREATE INDEX "Feature_runnerId_idx" ON "Feature"("runnerId");

-- CreateIndex
CREATE INDEX "Feature_key_idx" ON "Feature"("key");

-- CreateIndex
CREATE UNIQUE INDEX "Feature_runnerId_key_key" ON "Feature"("runnerId", "key");

-- CreateIndex
CREATE UNIQUE INDEX "EvidenceProfile_horseId_key" ON "EvidenceProfile"("horseId");

-- CreateIndex
CREATE UNIQUE INDEX "RunnerPaceProfile_runnerId_key" ON "RunnerPaceProfile"("runnerId");

-- CreateIndex
CREATE UNIQUE INDEX "Bookmaker_name_key" ON "Bookmaker"("name");

-- CreateIndex
CREATE INDEX "RunnerMarketPrice_runnerId_idx" ON "RunnerMarketPrice"("runnerId");

-- CreateIndex
CREATE INDEX "RunnerMarketPrice_bookmakerId_idx" ON "RunnerMarketPrice"("bookmakerId");

-- CreateIndex
CREATE INDEX "RunnerMarketPrice_timestamp_idx" ON "RunnerMarketPrice"("timestamp");

-- CreateIndex
CREATE INDEX "PredictionSnapshot_runnerId_idx" ON "PredictionSnapshot"("runnerId");

-- CreateIndex
CREATE INDEX "PredictionSnapshot_snapshotType_idx" ON "PredictionSnapshot"("snapshotType");

-- CreateIndex
CREATE UNIQUE INDEX "ResultEntry_runnerId_key" ON "ResultEntry"("runnerId");

-- CreateIndex
CREATE INDEX "RunnerObservation_resultId_idx" ON "RunnerObservation"("resultId");

-- CreateIndex
CREATE UNIQUE INDEX "Lucky15Leg_slipId_runnerId_key" ON "Lucky15Leg"("slipId", "runnerId");
