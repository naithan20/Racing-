import { notFound } from "next/navigation";

import {
  getImportJobById,
  getImportJobCompletionSummary,
  getMappingReviewData,
  listCanonicalRoles,
} from "@/data/dataSources";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { JobProgressView } from "@/components/data-sources/JobProgressView";
import { MappingReviewForm } from "@/components/data-sources/MappingReviewForm";

export default async function ImportJobPage({ params }: PageProps<"/data-sources/jobs/[jobId]">) {
  const { jobId } = await params;
  const job = await getImportJobById(jobId);
  if (!job) notFound();

  const completion = job.status === "COMPLETED" ? await getImportJobCompletionSummary(jobId) : null;

  return (
    <div className="mx-auto max-w-[900px] space-y-6 px-4 py-6 sm:px-6">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Import: {job.sourceLabel || job.sourceId}</h1>
        <p className="mt-1 text-sm text-text-secondary">Job {job.id}</p>
      </div>

      {job.status === "AWAITING_MAPPING_REVIEW" ? (
        <MappingReviewCard jobId={jobId} />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Import progress</CardTitle>
          </CardHeader>
          <CardBody>
            <JobProgressView
              job={{
                id: job.id,
                status: job.status,
                progressPercent: job.progressPercent,
                currentStepLabel: job.currentStepLabel,
                errorMessage: job.errorMessage,
                racesImported: job.racesImported,
                runnersImported: job.runnersImported,
                datasetVersionId: job.datasetVersionId,
                log: job.logJson ? JSON.parse(job.logJson) : [],
                completion: completion
                  ? {
                      coverageStart: completion.coverageStart?.toISOString() ?? null,
                      coverageEnd: completion.coverageEnd?.toISOString() ?? null,
                      completenessScore: completion.completenessScore,
                      leakageAuditStatus: completion.leakageAuditStatus,
                    }
                  : null,
              }}
            />
          </CardBody>
        </Card>
      )}
    </div>
  );
}

async function MappingReviewCard({ jobId }: { jobId: string }) {
  const data = await getMappingReviewData(jobId);
  const canonicalRoles = listCanonicalRoles();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Review field mapping</CardTitle>
      </CardHeader>
      <CardBody>
        {data ? (
          <MappingReviewForm
            jobId={jobId}
            columns={data.columnsNeedingReview}
            autoMappedCount={data.autoMappedCount}
            canonicalRoles={canonicalRoles}
          />
        ) : (
          <p className="text-sm text-text-muted">Mapping data not found for this job.</p>
        )}
      </CardBody>
    </Card>
  );
}
