-- CreateSchema
CREATE SCHEMA IF NOT EXISTS "public";

-- CreateEnum
CREATE TYPE "FlatJumps" AS ENUM ('FLAT', 'JUMPS');

-- CreateEnum
CREATE TYPE "RaceSurface" AS ENUM ('TURF', 'ALL_WEATHER', 'DIRT');

-- CreateEnum
CREATE TYPE "HandicapType" AS ENUM ('HANDICAP', 'NON_HANDICAP');

-- CreateEnum
CREATE TYPE "RaceStatus" AS ENUM ('SCHEDULED', 'DELAYED', 'ABANDONED', 'RESULTED');

-- CreateEnum
CREATE TYPE "ResultStatus" AS ENUM ('PENDING', 'PROVISIONAL', 'CONFIRMED', 'VOID');

-- CreateEnum
CREATE TYPE "Sex" AS ENUM ('COLT', 'FILLY', 'GELDING', 'MARE', 'HORSE', 'RIG');

-- CreateEnum
CREATE TYPE "SnapshotType" AS ENUM ('PRE_RACE', 'IN_PLAY', 'POST_RACE_REVIEW');

-- CreateEnum
CREATE TYPE "EvidenceDensityLabel" AS ENUM ('VERY_LOW', 'LOW', 'MODERATE', 'HIGH', 'VERY_HIGH');

-- CreateEnum
CREATE TYPE "PaceRole" AS ENUM ('LEADER', 'PRONOUNCED_PACE', 'MIDDIVISION', 'HOLD_UP', 'UNKNOWN');

-- CreateEnum
CREATE TYPE "FeatureValueType" AS ENUM ('NUMERIC', 'TEXT', 'BOOLEAN', 'CATEGORY');

-- CreateEnum
CREATE TYPE "FeatureCategory" AS ENUM ('CURRENT_ABILITY', 'CLASS', 'HANDICAP', 'WEIGHT', 'COURSE', 'DISTANCE', 'GROUND', 'DRAW', 'PACE_POSITION_ACQUISITION', 'PACE_TRANSITION_SPEED', 'PACE_LATE_SUSTAINABILITY', 'PACE_RACE_SHAPE', 'TRAINER_JOCKEY', 'HEADGEAR_EQUIPMENT', 'PEDIGREE', 'EVIDENCE_UNCERTAINTY', 'OTHER');

-- CreateEnum
CREATE TYPE "ImportSourceType" AS ENUM ('MANUAL', 'CSV', 'JSON', 'API');

-- CreateEnum
CREATE TYPE "ImportStatus" AS ENUM ('PENDING', 'IN_PROGRESS', 'SUCCESS', 'PARTIAL', 'FAILED');

-- CreateEnum
CREATE TYPE "ObservationTagType" AS ENUM ('EXCELLENT_BREAK', 'SLOW_BREAK', 'LED_CHEAPLY', 'FOUGHT_FOR_LEAD', 'RACED_PROMINENTLY', 'MIDFIELD', 'HELD_UP', 'TRAPPED_WIDE', 'BLOCKED', 'SWITCHED', 'LOST_GROUND_SEEKING_RUN', 'TRAVELLED_STRONGLY', 'UNABLE_TO_MATCH_ACCELERATION', 'STRONG_TRANSITION', 'WEAKENED_FINAL_FURLONG', 'STAYED_ON_STRONGLY', 'PACE_COLLAPSE_BENEFITED', 'PACE_COLLAPSE_HURT', 'BAD_RIDE_POSITIONING', 'RACE_NOT_REPRESENTATIVE', 'CLEAN_TEST_OF_THESIS');

-- CreateEnum
CREATE TYPE "SelectionType" AS ENUM ('WIN_VALUE', 'EACH_WAY_VALUE', 'PLACE_PROBABILITY', 'DAILY_VALUE', 'LUCKY_15_LEG');

-- CreateEnum
CREATE TYPE "DataSourceType" AS ENUM ('REAL', 'SYNTHETIC', 'SAMPLE');

-- CreateEnum
CREATE TYPE "EntityType" AS ENUM ('HORSE', 'TRAINER', 'JOCKEY', 'COURSE');

-- CreateEnum
CREATE TYPE "EntityResolutionStatus" AS ENUM ('PENDING', 'RESOLVED', 'REJECTED');

-- CreateEnum
CREATE TYPE "EntityMatchMethod" AS ENUM ('PROVIDER_ID', 'EXACT_NORMALIZED_NAME', 'MANUAL_REVIEW');

-- CreateEnum
CREATE TYPE "LeakageAuditStatus" AS ENUM ('PASSED', 'FAILED');

-- CreateEnum
CREATE TYPE "ProvenanceStatus" AS ENUM ('VERIFIED_OPEN', 'PUBLIC_RESEARCH', 'COMMUNITY_UNVERIFIED', 'USER_SUPPLIED', 'UNKNOWN', 'RESTRICTED');

-- CreateEnum
CREATE TYPE "FeatureProfile" AS ENUM ('CORE_FREE_MODEL', 'ENRICHED_FREE_MODEL', 'FULL_MODEL');

-- CreateEnum
CREATE TYPE "ConnectionStatus" AS ENUM ('NOT_CONNECTED', 'CONNECTED', 'ERROR');

-- CreateEnum
CREATE TYPE "ImportJobStatus" AS ENUM ('PENDING', 'DOWNLOADING', 'INSPECTING', 'AWAITING_MAPPING_REVIEW', 'VALIDATING', 'IMPORTING', 'RESOLVING_ENTITIES', 'PROVENANCE_REVIEW', 'LEAKAGE_AUDIT', 'CREATING_DATASET_VERSION', 'GENERATING_QUALITY_REPORT', 'COMPLETED', 'FAILED');

-- CreateTable
CREATE TABLE "Race" (
    "id" TEXT NOT NULL,
    "isSampleData" BOOLEAN NOT NULL DEFAULT false,
    "sourceType" "DataSourceType" NOT NULL DEFAULT 'SAMPLE',
    "date" TIMESTAMP(3) NOT NULL,
    "raceTime" TEXT NOT NULL,
    "racecourse" TEXT NOT NULL,
    "country" TEXT NOT NULL,
    "raceName" TEXT NOT NULL,
    "raceType" TEXT,
    "flatJumps" "FlatJumps" NOT NULL,
    "surface" "RaceSurface" NOT NULL,
    "distanceYards" INTEGER,
    "distanceFurlongs" DOUBLE PRECISION NOT NULL,
    "raceClass" INTEGER,
    "gradeGroup" TEXT,
    "handicapType" "HandicapType" NOT NULL,
    "ageRestriction" TEXT,
    "sexRestriction" TEXT,
    "numberOfRunners" INTEGER NOT NULL,
    "going" TEXT,
    "goingDescription" TEXT,
    "railPosition" TEXT,
    "stallsPosition" TEXT,
    "weatherSummary" TEXT,
    "temperatureCelsius" DOUBLE PRECISION,
    "windSummary" TEXT,
    "precipitationMm" DOUBLE PRECISION,
    "prizeMoneyTotal" DOUBLE PRECISION,
    "currency" TEXT NOT NULL DEFAULT 'GBP',
    "eachWayFraction" DOUBLE PRECISION,
    "bookmakerPlaces" INTEGER,
    "extraPlaceFlag" BOOLEAN NOT NULL DEFAULT false,
    "raceStatus" "RaceStatus" NOT NULL DEFAULT 'SCHEDULED',
    "resultStatus" "ResultStatus" NOT NULL DEFAULT 'PENDING',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "importBatchId" TEXT,

    CONSTRAINT "Race_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "RacePlaceTerms" (
    "id" TEXT NOT NULL,
    "raceId" TEXT NOT NULL,
    "bookmakerId" TEXT NOT NULL,
    "places" INTEGER NOT NULL,
    "eachWayFraction" DOUBLE PRECISION NOT NULL,
    "extraPlaces" BOOLEAN NOT NULL DEFAULT false,
    "terms" TEXT,
    "effectiveAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "RacePlaceTerms_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Horse" (
    "id" TEXT NOT NULL,
    "isSampleData" BOOLEAN NOT NULL DEFAULT false,
    "sourceType" "DataSourceType" NOT NULL DEFAULT 'SAMPLE',
    "name" TEXT NOT NULL,
    "countryBred" TEXT,
    "yearOfBirth" INTEGER,
    "sex" "Sex",
    "sireName" TEXT,
    "damName" TEXT,
    "damsireName" TEXT,
    "trainerName" TEXT,
    "ownerName" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Horse_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Runner" (
    "id" TEXT NOT NULL,
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
    "currentOddsDecimal" DOUBLE PRECISION,
    "currentOddsFractional" TEXT,
    "openingOddsDecimal" DOUBLE PRECISION,
    "startingPriceDecimal" DOUBLE PRECISION,
    "exchangePriceDecimal" DOUBLE PRECISION,
    "nonRunner" BOOLEAN NOT NULL DEFAULT false,
    "favouriteRank" INTEGER,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Runner_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "FormEntry" (
    "id" TEXT NOT NULL,
    "isSampleData" BOOLEAN NOT NULL DEFAULT false,
    "horseId" TEXT NOT NULL,
    "linkedRaceId" TEXT,
    "raceDate" TIMESTAMP(3) NOT NULL,
    "course" TEXT NOT NULL,
    "country" TEXT,
    "distanceFurlongs" DOUBLE PRECISION,
    "going" TEXT,
    "raceClass" INTEGER,
    "flatJumps" "FlatJumps",
    "fieldSize" INTEGER,
    "finishingPosition" INTEGER,
    "finishStatus" TEXT,
    "beatenDistanceLengths" DOUBLE PRECISION,
    "startingPriceDecimal" DOUBLE PRECISION,
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
    "finishingSpeedPercentage" DOUBLE PRECISION,
    "paceClassification" TEXT,
    "raceStrengthIndex" DOUBLE PRECISION,
    "winnerSubsequentPerformance" TEXT,
    "collateralFormNotes" TEXT,
    "hasPositionalData" BOOLEAN NOT NULL DEFAULT false,
    "hasSectionalData" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "FormEntry_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "FeatureDefinition" (
    "key" TEXT NOT NULL,
    "category" "FeatureCategory" NOT NULL,
    "label" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "valueType" "FeatureValueType" NOT NULL,
    "unit" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "FeatureDefinition_pkey" PRIMARY KEY ("key")
);

-- CreateTable
CREATE TABLE "Feature" (
    "id" TEXT NOT NULL,
    "runnerId" TEXT NOT NULL,
    "key" TEXT NOT NULL,
    "numericValue" DOUBLE PRECISION,
    "textValue" TEXT,
    "booleanValue" BOOLEAN,
    "computedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "modelVersion" TEXT,
    "sourceNote" TEXT,

    CONSTRAINT "Feature_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "EvidenceProfile" (
    "id" TEXT NOT NULL,
    "horseId" TEXT NOT NULL,
    "careerStarts" INTEGER NOT NULL DEFAULT 0,
    "startsLast12Months" INTEGER NOT NULL DEFAULT 0,
    "startsAtCourse" INTEGER NOT NULL DEFAULT 0,
    "startsAtDistance" INTEGER NOT NULL DEFAULT 0,
    "startsOnGoing" INTEGER NOT NULL DEFAULT 0,
    "evidenceDensityScore" DOUBLE PRECISION,
    "evidenceDensityLabel" "EvidenceDensityLabel",
    "uncertaintyNote" TEXT,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "EvidenceProfile_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "RunnerPaceProfile" (
    "id" TEXT NOT NULL,
    "runnerId" TEXT NOT NULL,
    "projectedRole" "PaceRole" NOT NULL DEFAULT 'UNKNOWN',
    "usualEarlyPosition" DOUBLE PRECISION,
    "breaksQuicklyRate" DOUBLE PRECISION,
    "slowStartRate" DOUBLE PRECISION,
    "energyToObtainPositionIndex" DOUBLE PRECISION,
    "positionChange3fTo2f" DOUBLE PRECISION,
    "positionChange2fTo1f" DOUBLE PRECISION,
    "relativeAccelerationIndex" DOUBLE PRECISION,
    "finishingSpeedIndex" DOUBLE PRECISION,
    "positionChangeFinalFurlong" DOUBLE PRECISION,
    "weakensLateRate" DOUBLE PRECISION,
    "staysOnStronglyRate" DOUBLE PRECISION,
    "competitionForLeadIndex" DOUBLE PRECISION,
    "pacePressureIndex" DOUBLE PRECISION,
    "paceCollapseProbability" DOUBLE PRECISION,
    "notes" TEXT,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "RunnerPaceProfile_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Bookmaker" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "isExchange" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Bookmaker_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "RunnerMarketPrice" (
    "id" TEXT NOT NULL,
    "runnerId" TEXT NOT NULL,
    "bookmakerId" TEXT NOT NULL,
    "timestamp" TIMESTAMP(3) NOT NULL,
    "winOddsDecimal" DOUBLE PRECISION NOT NULL,
    "eachWayFraction" DOUBLE PRECISION,
    "numberOfPlaces" INTEGER,
    "extraPlaces" BOOLEAN NOT NULL DEFAULT false,
    "backOddsDecimal" DOUBLE PRECISION,
    "layOddsDecimal" DOUBLE PRECISION,
    "availableVolume" DOUBLE PRECISION,
    "marketStatus" TEXT,
    "isOpeningPrice" BOOLEAN NOT NULL DEFAULT false,
    "isStartingPrice" BOOLEAN NOT NULL DEFAULT false,
    "isClosingPrice" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "RunnerMarketPrice_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "PredictionSnapshot" (
    "id" TEXT NOT NULL,
    "runnerId" TEXT NOT NULL,
    "snapshotType" "SnapshotType" NOT NULL DEFAULT 'PRE_RACE',
    "modelVersion" TEXT NOT NULL,
    "modelVersionId" TEXT,
    "winProbability" DOUBLE PRECISION,
    "placeProbability" DOUBLE PRECISION,
    "placeBasisPlaces" INTEGER,
    "placeBasisBookmakerId" TEXT,
    "modelConfidence" DOUBLE PRECISION,
    "fairOddsDecimal" DOUBLE PRECISION,
    "marketImpliedProbability" DOUBLE PRECISION,
    "valueEdgeAbsolute" DOUBLE PRECISION,
    "valueEdgeRelative" DOUBLE PRECISION,
    "referenceOddsDecimal" DOUBLE PRECISION,
    "isLocked" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "PredictionSnapshot_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ModelVersion" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "version" TEXT NOT NULL,
    "featureSetVersion" TEXT NOT NULL,
    "algorithm" TEXT NOT NULL,
    "hyperparameters" TEXT NOT NULL,
    "calibrationMethod" TEXT NOT NULL,
    "trainingStartDate" TIMESTAMP(3) NOT NULL,
    "trainingEndDate" TIMESTAMP(3) NOT NULL,
    "validationStartDate" TIMESTAMP(3),
    "validationEndDate" TIMESTAMP(3),
    "testStartDate" TIMESTAMP(3),
    "testEndDate" TIMESTAMP(3),
    "trainingRowCount" INTEGER NOT NULL,
    "trainingRaceCount" INTEGER NOT NULL,
    "datasetVersionId" TEXT,
    "isSynthetic" BOOLEAN NOT NULL DEFAULT false,
    "featureProfile" "FeatureProfile" NOT NULL DEFAULT 'FULL_MODEL',
    "metricsJson" TEXT,
    "featureImportanceJson" TEXT,
    "artifactPath" TEXT,
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ModelVersion_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "PlaceProbabilityBand" (
    "id" TEXT NOT NULL,
    "predictionSnapshotId" TEXT NOT NULL,
    "topN" INTEGER NOT NULL,
    "probabilityRaw" DOUBLE PRECISION NOT NULL,
    "probabilityCalibrated" DOUBLE PRECISION NOT NULL,

    CONSTRAINT "PlaceProbabilityBand_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ResultEntry" (
    "id" TEXT NOT NULL,
    "runnerId" TEXT NOT NULL,
    "finishingPosition" INTEGER,
    "finishStatus" TEXT,
    "beatenDistanceLengths" DOUBLE PRECISION,
    "deadHeat" BOOLEAN NOT NULL DEFAULT false,
    "startingPriceDecimal" DOUBLE PRECISION,
    "closingOddsDecimal" DOUBLE PRECISION,
    "bspDecimal" DOUBLE PRECISION,
    "placeOutcome" BOOLEAN,
    "profitLossWinStake" DOUBLE PRECISION,
    "profitLossEachWayStake" DOUBLE PRECISION,
    "resultStatus" "ResultStatus" NOT NULL DEFAULT 'PENDING',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "ResultEntry_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "RunnerObservation" (
    "id" TEXT NOT NULL,
    "resultId" TEXT NOT NULL,
    "tag" "ObservationTagType",
    "freeText" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "RunnerObservation_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Lucky15Slip" (
    "id" TEXT NOT NULL,
    "name" TEXT,
    "date" TIMESTAMP(3) NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "minOddsDecimal" DOUBLE PRECISION,
    "maxOddsDecimal" DOUBLE PRECISION,
    "minConfidence" DOUBLE PRECISION,
    "minPlaceEdge" DOUBLE PRECISION,
    "minRunners" INTEGER,
    "enhancedPlacesOnly" BOOLEAN NOT NULL DEFAULT false,
    "flatJumpsFilter" "FlatJumps",
    "countryFilter" TEXT,
    "bookmakerId" TEXT,

    CONSTRAINT "Lucky15Slip_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Lucky15Leg" (
    "id" TEXT NOT NULL,
    "slipId" TEXT NOT NULL,
    "runnerId" TEXT NOT NULL,
    "selectionType" "SelectionType" NOT NULL DEFAULT 'LUCKY_15_LEG',
    "rationale" TEXT,
    "sortOrder" INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT "Lucky15Leg_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ImportBatch" (
    "id" TEXT NOT NULL,
    "sourceType" "ImportSourceType" NOT NULL,
    "filename" TEXT,
    "status" "ImportStatus" NOT NULL DEFAULT 'PENDING',
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
    "importedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ImportBatch_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "DataProvenance" (
    "id" TEXT NOT NULL,
    "entityType" TEXT NOT NULL,
    "entityId" TEXT NOT NULL,
    "dataDomain" TEXT NOT NULL,
    "provider" TEXT NOT NULL,
    "providerRecordId" TEXT,
    "providerTimestamp" TIMESTAMP(3),
    "retrievedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "effectiveAt" TIMESTAMP(3),
    "sourceVersion" TEXT,
    "rawPayloadHash" TEXT,
    "provenanceStatus" "ProvenanceStatus" NOT NULL DEFAULT 'UNKNOWN',
    "sourceUrl" TEXT,
    "importBatchId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "DataProvenance_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "DatasetReview" (
    "id" TEXT NOT NULL,
    "datasetName" TEXT NOT NULL,
    "source" TEXT NOT NULL,
    "licenceStated" TEXT,
    "licenceUrl" TEXT,
    "originalProvider" TEXT,
    "redistributionPermitted" BOOLEAN,
    "researchUsePermitted" BOOLEAN,
    "commercialUsePermitted" BOOLEAN,
    "provenanceConfidence" "ProvenanceStatus" NOT NULL DEFAULT 'UNKNOWN',
    "reviewerNotes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "DatasetReview_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "RaceFieldHistory" (
    "id" TEXT NOT NULL,
    "raceId" TEXT NOT NULL,
    "fieldName" TEXT NOT NULL,
    "fieldValue" TEXT,
    "effectiveAt" TIMESTAMP(3) NOT NULL,
    "source" TEXT,
    "importBatchId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "RaceFieldHistory_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "RunnerFieldHistory" (
    "id" TEXT NOT NULL,
    "runnerId" TEXT NOT NULL,
    "fieldName" TEXT NOT NULL,
    "fieldValue" TEXT,
    "effectiveAt" TIMESTAMP(3) NOT NULL,
    "source" TEXT,
    "importBatchId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "RunnerFieldHistory_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "RacePlaceTermsHistory" (
    "id" TEXT NOT NULL,
    "racePlaceTermsId" TEXT NOT NULL,
    "raceId" TEXT NOT NULL,
    "bookmakerId" TEXT NOT NULL,
    "places" INTEGER NOT NULL,
    "eachWayFraction" DOUBLE PRECISION NOT NULL,
    "extraPlaces" BOOLEAN NOT NULL DEFAULT false,
    "terms" TEXT,
    "effectiveAt" TIMESTAMP(3) NOT NULL,
    "supersededAt" TIMESTAMP(3),
    "source" TEXT,
    "importBatchId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "RacePlaceTermsHistory_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "RunnerSectionalPoint" (
    "id" TEXT NOT NULL,
    "runnerId" TEXT NOT NULL,
    "segmentIndex" INTEGER NOT NULL,
    "segmentDistanceFurlongs" DOUBLE PRECISION,
    "segmentTimeSeconds" DOUBLE PRECISION,
    "speedMps" DOUBLE PRECISION,
    "positionInRace" INTEGER,
    "strideLength" DOUBLE PRECISION,
    "strideFrequency" DOUBLE PRECISION,
    "latitude" DOUBLE PRECISION,
    "longitude" DOUBLE PRECISION,
    "source" TEXT,
    "importBatchId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "RunnerSectionalPoint_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "EntityAlias" (
    "id" TEXT NOT NULL,
    "entityType" "EntityType" NOT NULL,
    "canonicalId" TEXT NOT NULL,
    "rawName" TEXT NOT NULL,
    "normalizedName" TEXT NOT NULL,
    "providerName" TEXT,
    "providerId" TEXT,
    "matchMethod" "EntityMatchMethod" NOT NULL,
    "confidence" DOUBLE PRECISION,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "EntityAlias_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "EntityResolutionQueueItem" (
    "id" TEXT NOT NULL,
    "entityType" "EntityType" NOT NULL,
    "rawName" TEXT NOT NULL,
    "normalizedName" TEXT NOT NULL,
    "providerName" TEXT,
    "candidateCanonicalIdsJson" TEXT,
    "status" "EntityResolutionStatus" NOT NULL DEFAULT 'PENDING',
    "resolvedCanonicalId" TEXT,
    "resolvedBy" TEXT,
    "resolvedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "EntityResolutionQueueItem_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "DatasetVersion" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "sourceType" "DataSourceType" NOT NULL,
    "providersJson" TEXT NOT NULL,
    "dateRangeStart" TIMESTAMP(3) NOT NULL,
    "dateRangeEnd" TIMESTAMP(3) NOT NULL,
    "raceCount" INTEGER NOT NULL,
    "runnerCount" INTEGER NOT NULL,
    "dataQualityMetricsJson" TEXT,
    "schemaVersion" TEXT NOT NULL,
    "importBatchIdsJson" TEXT,
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "DatasetVersion_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "DataSourceConnection" (
    "id" TEXT NOT NULL,
    "sourceId" TEXT NOT NULL,
    "status" "ConnectionStatus" NOT NULL DEFAULT 'NOT_CONNECTED',
    "connectedAt" TIMESTAMP(3),
    "lastSyncAt" TIMESTAMP(3),
    "errorMessage" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "DataSourceConnection_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ImportJob" (
    "id" TEXT NOT NULL,
    "sourceId" TEXT NOT NULL,
    "connectionId" TEXT,
    "status" "ImportJobStatus" NOT NULL DEFAULT 'PENDING',
    "progressPercent" INTEGER NOT NULL DEFAULT 0,
    "currentStepLabel" TEXT,
    "downloadUrl" TEXT,
    "downloadedFilePath" TEXT,
    "mappingFilePath" TEXT,
    "provenanceStatus" TEXT,
    "sourceLabel" TEXT,
    "paramsJson" TEXT,
    "datasetVersionId" TEXT,
    "importBatchId" TEXT,
    "racesImported" INTEGER,
    "runnersImported" INTEGER,
    "errorMessage" TEXT,
    "logJson" TEXT,
    "startedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "completedAt" TIMESTAMP(3),

    CONSTRAINT "ImportJob_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "LeakageAuditRun" (
    "id" TEXT NOT NULL,
    "datasetVersionId" TEXT,
    "modelVersionId" TEXT,
    "status" "LeakageAuditStatus" NOT NULL,
    "featuresChecked" INTEGER NOT NULL,
    "violationsFound" INTEGER NOT NULL DEFAULT 0,
    "reportJson" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "LeakageAuditRun_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "Race_date_idx" ON "Race"("date");

-- CreateIndex
CREATE INDEX "Race_racecourse_idx" ON "Race"("racecourse");

-- CreateIndex
CREATE INDEX "Race_country_idx" ON "Race"("country");

-- CreateIndex
CREATE INDEX "Race_sourceType_idx" ON "Race"("sourceType");

-- CreateIndex
CREATE UNIQUE INDEX "RacePlaceTerms_raceId_bookmakerId_key" ON "RacePlaceTerms"("raceId", "bookmakerId");

-- CreateIndex
CREATE INDEX "Horse_name_idx" ON "Horse"("name");

-- CreateIndex
CREATE INDEX "Horse_sourceType_idx" ON "Horse"("sourceType");

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
CREATE INDEX "PredictionSnapshot_modelVersionId_idx" ON "PredictionSnapshot"("modelVersionId");

-- CreateIndex
CREATE INDEX "ModelVersion_algorithm_idx" ON "ModelVersion"("algorithm");

-- CreateIndex
CREATE INDEX "ModelVersion_datasetVersionId_idx" ON "ModelVersion"("datasetVersionId");

-- CreateIndex
CREATE UNIQUE INDEX "ModelVersion_name_version_key" ON "ModelVersion"("name", "version");

-- CreateIndex
CREATE UNIQUE INDEX "PlaceProbabilityBand_predictionSnapshotId_topN_key" ON "PlaceProbabilityBand"("predictionSnapshotId", "topN");

-- CreateIndex
CREATE UNIQUE INDEX "ResultEntry_runnerId_key" ON "ResultEntry"("runnerId");

-- CreateIndex
CREATE INDEX "RunnerObservation_resultId_idx" ON "RunnerObservation"("resultId");

-- CreateIndex
CREATE UNIQUE INDEX "Lucky15Leg_slipId_runnerId_key" ON "Lucky15Leg"("slipId", "runnerId");

-- CreateIndex
CREATE UNIQUE INDEX "ImportBatch_idempotencyKey_key" ON "ImportBatch"("idempotencyKey");

-- CreateIndex
CREATE INDEX "ImportBatch_providerName_idx" ON "ImportBatch"("providerName");

-- CreateIndex
CREATE INDEX "ImportBatch_datasetVersionId_idx" ON "ImportBatch"("datasetVersionId");

-- CreateIndex
CREATE INDEX "DataProvenance_entityType_entityId_idx" ON "DataProvenance"("entityType", "entityId");

-- CreateIndex
CREATE INDEX "DataProvenance_dataDomain_idx" ON "DataProvenance"("dataDomain");

-- CreateIndex
CREATE INDEX "DataProvenance_provider_idx" ON "DataProvenance"("provider");

-- CreateIndex
CREATE INDEX "DataProvenance_importBatchId_idx" ON "DataProvenance"("importBatchId");

-- CreateIndex
CREATE INDEX "DataProvenance_provenanceStatus_idx" ON "DataProvenance"("provenanceStatus");

-- CreateIndex
CREATE INDEX "DatasetReview_provenanceConfidence_idx" ON "DatasetReview"("provenanceConfidence");

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
CREATE UNIQUE INDEX "DataSourceConnection_sourceId_key" ON "DataSourceConnection"("sourceId");

-- CreateIndex
CREATE INDEX "DataSourceConnection_sourceId_idx" ON "DataSourceConnection"("sourceId");

-- CreateIndex
CREATE INDEX "ImportJob_sourceId_idx" ON "ImportJob"("sourceId");

-- CreateIndex
CREATE INDEX "ImportJob_status_idx" ON "ImportJob"("status");

-- CreateIndex
CREATE INDEX "ImportJob_connectionId_idx" ON "ImportJob"("connectionId");

-- CreateIndex
CREATE INDEX "LeakageAuditRun_datasetVersionId_idx" ON "LeakageAuditRun"("datasetVersionId");

-- CreateIndex
CREATE INDEX "LeakageAuditRun_modelVersionId_idx" ON "LeakageAuditRun"("modelVersionId");

-- CreateIndex
CREATE INDEX "LeakageAuditRun_status_idx" ON "LeakageAuditRun"("status");

-- AddForeignKey
ALTER TABLE "Race" ADD CONSTRAINT "Race_importBatchId_fkey" FOREIGN KEY ("importBatchId") REFERENCES "ImportBatch"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "RacePlaceTerms" ADD CONSTRAINT "RacePlaceTerms_raceId_fkey" FOREIGN KEY ("raceId") REFERENCES "Race"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "RacePlaceTerms" ADD CONSTRAINT "RacePlaceTerms_bookmakerId_fkey" FOREIGN KEY ("bookmakerId") REFERENCES "Bookmaker"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Runner" ADD CONSTRAINT "Runner_raceId_fkey" FOREIGN KEY ("raceId") REFERENCES "Race"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Runner" ADD CONSTRAINT "Runner_horseId_fkey" FOREIGN KEY ("horseId") REFERENCES "Horse"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "FormEntry" ADD CONSTRAINT "FormEntry_horseId_fkey" FOREIGN KEY ("horseId") REFERENCES "Horse"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Feature" ADD CONSTRAINT "Feature_runnerId_fkey" FOREIGN KEY ("runnerId") REFERENCES "Runner"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Feature" ADD CONSTRAINT "Feature_key_fkey" FOREIGN KEY ("key") REFERENCES "FeatureDefinition"("key") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "EvidenceProfile" ADD CONSTRAINT "EvidenceProfile_horseId_fkey" FOREIGN KEY ("horseId") REFERENCES "Horse"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "RunnerPaceProfile" ADD CONSTRAINT "RunnerPaceProfile_runnerId_fkey" FOREIGN KEY ("runnerId") REFERENCES "Runner"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "RunnerMarketPrice" ADD CONSTRAINT "RunnerMarketPrice_runnerId_fkey" FOREIGN KEY ("runnerId") REFERENCES "Runner"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "RunnerMarketPrice" ADD CONSTRAINT "RunnerMarketPrice_bookmakerId_fkey" FOREIGN KEY ("bookmakerId") REFERENCES "Bookmaker"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "PredictionSnapshot" ADD CONSTRAINT "PredictionSnapshot_runnerId_fkey" FOREIGN KEY ("runnerId") REFERENCES "Runner"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "PredictionSnapshot" ADD CONSTRAINT "PredictionSnapshot_modelVersionId_fkey" FOREIGN KEY ("modelVersionId") REFERENCES "ModelVersion"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ModelVersion" ADD CONSTRAINT "ModelVersion_datasetVersionId_fkey" FOREIGN KEY ("datasetVersionId") REFERENCES "DatasetVersion"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "PlaceProbabilityBand" ADD CONSTRAINT "PlaceProbabilityBand_predictionSnapshotId_fkey" FOREIGN KEY ("predictionSnapshotId") REFERENCES "PredictionSnapshot"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ResultEntry" ADD CONSTRAINT "ResultEntry_runnerId_fkey" FOREIGN KEY ("runnerId") REFERENCES "Runner"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "RunnerObservation" ADD CONSTRAINT "RunnerObservation_resultId_fkey" FOREIGN KEY ("resultId") REFERENCES "ResultEntry"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Lucky15Leg" ADD CONSTRAINT "Lucky15Leg_slipId_fkey" FOREIGN KEY ("slipId") REFERENCES "Lucky15Slip"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Lucky15Leg" ADD CONSTRAINT "Lucky15Leg_runnerId_fkey" FOREIGN KEY ("runnerId") REFERENCES "Runner"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ImportBatch" ADD CONSTRAINT "ImportBatch_datasetVersionId_fkey" FOREIGN KEY ("datasetVersionId") REFERENCES "DatasetVersion"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "DataProvenance" ADD CONSTRAINT "DataProvenance_importBatchId_fkey" FOREIGN KEY ("importBatchId") REFERENCES "ImportBatch"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "RaceFieldHistory" ADD CONSTRAINT "RaceFieldHistory_raceId_fkey" FOREIGN KEY ("raceId") REFERENCES "Race"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "RunnerFieldHistory" ADD CONSTRAINT "RunnerFieldHistory_runnerId_fkey" FOREIGN KEY ("runnerId") REFERENCES "Runner"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "RacePlaceTermsHistory" ADD CONSTRAINT "RacePlaceTermsHistory_racePlaceTermsId_fkey" FOREIGN KEY ("racePlaceTermsId") REFERENCES "RacePlaceTerms"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "RunnerSectionalPoint" ADD CONSTRAINT "RunnerSectionalPoint_runnerId_fkey" FOREIGN KEY ("runnerId") REFERENCES "Runner"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ImportJob" ADD CONSTRAINT "ImportJob_connectionId_fkey" FOREIGN KEY ("connectionId") REFERENCES "DataSourceConnection"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "LeakageAuditRun" ADD CONSTRAINT "LeakageAuditRun_datasetVersionId_fkey" FOREIGN KEY ("datasetVersionId") REFERENCES "DatasetVersion"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "LeakageAuditRun" ADD CONSTRAINT "LeakageAuditRun_modelVersionId_fkey" FOREIGN KEY ("modelVersionId") REFERENCES "ModelVersion"("id") ON DELETE SET NULL ON UPDATE CASCADE;

