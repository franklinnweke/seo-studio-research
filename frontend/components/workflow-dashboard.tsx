"use client";

import { useCallback, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Copy,
  Download,
  FileArchive,
  ImageIcon,
  Loader2,
  Maximize2,
  Sparkles,
  Upload,
  X,
} from "lucide-react";

import { ImageUploadPanel } from "@/components/image-upload-panel";
import { SeoMetadataPanel } from "@/components/seo-metadata-panel";
import { ImageResizerPanel } from "@/components/image-resizer-panel";
import {
  downloadApiFile,
  getImageMetadata,
  getJobFiles,
  getJobStatus,
  getProcessedImagesZipDownloadUrl,
  getImageMetadataZipDownloadUrl,
} from "@/lib/api";
import {
  clearActiveImageJobId,
  setActiveImageJobId,
  useActiveImageJobId,
} from "@/lib/workspace";

type StepId = "upload" | "optimize" | "metadata" | "resize" | "export";

type StepStatus = "not_started" | "ready" | "in_progress" | "complete";

type StepDefinition = {
  id: StepId;
  label: string;
  description: string;
  icon: typeof Upload;
  number: number;
};

const STEPS: StepDefinition[] = [
  {
    id: "upload",
    label: "Upload Files",
    description: "Drag and drop images or ZIP archives to create a job.",
    icon: Upload,
    number: 1,
  },
  {
    id: "optimize",
    label: "Optimize Images",
    description: "Compress, convert, and rename uploaded images.",
    icon: ImageIcon,
    number: 2,
  },
  {
    id: "metadata",
    label: "Generate SEO Metadata",
    description: "AI-powered filenames, alt text, and captions.",
    icon: Sparkles,
    number: 3,
  },
  {
    id: "resize",
    label: "Resize / Crop Review",
    description: "Resize into fixed website dimensions with crop review.",
    icon: Maximize2,
    number: 4,
  },
  {
    id: "export",
    label: "Export Outputs",
    description: "Download optimized images, metadata, and resized assets.",
    icon: Download,
    number: 5,
  },
];

const statusConfig: Record<StepStatus, { label: string; className: string }> = {
  not_started: {
    label: "Not started",
    className: "bg-[#f2f4f7] text-[#475467]",
  },
  ready: {
    label: "Ready",
    className: "bg-[#edf4ff] text-[#1d4ed8]",
  },
  in_progress: {
    label: "In progress",
    className: "bg-[#fff4e5] text-[#b45309]",
  },
  complete: {
    label: "Complete",
    className: "bg-[#eef6f0] text-[#20744a]",
  },
};

export function WorkflowDashboard() {
  const queryClient = useQueryClient();
  const activeJobId = useActiveImageJobId();
  const [expandedStep, setExpandedStep] = useState<StepId | null>(
    activeJobId ? null : "upload",
  );

  const jobStatusQuery = useQuery({
    queryKey: ["image-job-status", activeJobId],
    queryFn: () => getJobStatus(activeJobId),
    enabled: Boolean(activeJobId),
  });

  const filesQuery = useQuery({
    queryKey: ["image-job-files", activeJobId],
    queryFn: () => getJobFiles(activeJobId),
    enabled: Boolean(activeJobId),
  });

  const metadataQuery = useQuery({
    queryKey: ["image-metadata", activeJobId],
    queryFn: () => getImageMetadata(activeJobId),
    enabled: Boolean(activeJobId),
  });

  const uploadedCount = filesQuery.data?.files.length ?? 0;
  const jobStatus = jobStatusQuery.data?.status;
  const isProcessed = jobStatus === "processed";
  const metadataResults = metadataQuery.data?.results ?? [];
  const metadataGeneratedCount = metadataResults.filter(
    (r) => r.status === "needs_review",
  ).length;

  const handleJobCreated = useCallback((jobId: string) => {
    setActiveImageJobId(jobId);
    setExpandedStep("optimize");
  }, []);

  const handleNewJob = useCallback(() => {
    clearActiveImageJobId();
    setExpandedStep("upload");
  }, []);

  const handleProcessed = useCallback(
    (jobId: string) => {
      queryClient.invalidateQueries({ queryKey: ["image-job-status", jobId] });
      queryClient.invalidateQueries({ queryKey: ["image-job-files", jobId] });
      setExpandedStep("metadata");
    },
    [queryClient],
  );

  const copyJobId = useCallback(async () => {
    if (!activeJobId) return;
    try {
      await navigator.clipboard.writeText(activeJobId);
    } catch {
      /* clipboard may fail on non-HTTPS */
    }
  }, [activeJobId]);

  const stepStatuses = useMemo((): Record<StepId, StepStatus> => {
    if (!activeJobId) {
      return {
        upload: "ready",
        optimize: "not_started",
        metadata: "not_started",
        resize: "not_started",
        export: "not_started",
      };
    }

    const uploadStatus: StepStatus =
      uploadedCount > 0 ? "complete" : "in_progress";
    const optimizeStatus: StepStatus = isProcessed
      ? "complete"
      : uploadedCount > 0
        ? "ready"
        : "not_started";
    const metadataStatus: StepStatus =
      metadataGeneratedCount > 0
        ? "complete"
        : uploadedCount > 0
          ? "ready"
          : "not_started";
    const resizeStatus: StepStatus =
      uploadedCount > 0 ? "ready" : "not_started";
    const exportStatus: StepStatus =
      isProcessed || metadataGeneratedCount > 0
        ? "ready"
        : "not_started";

    return {
      upload: uploadStatus,
      optimize: optimizeStatus,
      metadata: metadataStatus,
      resize: resizeStatus,
      export: exportStatus,
    };
  }, [activeJobId, uploadedCount, isProcessed, metadataGeneratedCount]);

  const stepSummaries = useMemo((): Record<StepId, string> => {
    if (!activeJobId) {
      return {
        upload: "Drag and drop images to begin.",
        optimize: "",
        metadata: "",
        resize: "",
        export: "",
      };
    }

    return {
      upload: uploadedCount > 0
        ? `${uploadedCount} image${uploadedCount === 1 ? "" : "s"} uploaded`
        : "Uploading…",
      optimize: isProcessed
        ? "Images compressed and converted"
        : uploadedCount > 0
          ? "Ready to compress and convert"
          : "",
      metadata: metadataGeneratedCount > 0
        ? `${metadataGeneratedCount} metadata result${metadataGeneratedCount === 1 ? "" : "s"} generated`
        : uploadedCount > 0
          ? "Ready to generate AI metadata"
          : "",
      resize: uploadedCount > 0
        ? "Ready to resize and crop"
        : "",
      export: isProcessed || metadataGeneratedCount > 0
        ? "Downloads available"
        : "",
    };
  }, [activeJobId, uploadedCount, isProcessed, metadataGeneratedCount]);

  const toggleStep = (stepId: StepId) => {
    setExpandedStep((current) => (current === stepId ? null : stepId));
  };

  const allFileIds = useMemo(
    () => (filesQuery.data?.files ?? []).map((f) => f.id),
    [filesQuery.data],
  );

  return (
    <div className="space-y-4">
      {/* Active job banner */}
      {activeJobId ? (
        <div className="flex flex-col gap-3 rounded-lg border border-[#dfe3e8] bg-white px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#eef6f0] text-[#20744a]">
              <CheckCircle2 aria-hidden="true" size={20} />
            </div>
            <div>
              <p className="text-sm font-medium text-[#151923]">
                Active Image Job
              </p>
              <div className="mt-0.5 flex items-center gap-2">
                <code className="text-sm text-[#475467]">{activeJobId}</code>
                <button
                  type="button"
                  onClick={copyJobId}
                  className="inline-flex h-6 w-6 items-center justify-center rounded text-[#667085] hover:bg-[#edf4ff] hover:text-[#1d4ed8]"
                  aria-label="Copy job ID"
                  title="Copy job ID"
                >
                  <Copy aria-hidden="true" size={13} />
                </button>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {jobStatusQuery.isLoading ? (
              <span className="inline-flex items-center gap-2 text-sm text-[#667085]">
                <Loader2
                  aria-hidden="true"
                  className="animate-spin"
                  size={14}
                />
                Loading job…
              </span>
            ) : (
              <span className="rounded-md bg-[#eef6f0] px-2.5 py-1 text-xs font-medium text-[#20744a]">
                {uploadedCount} image{uploadedCount === 1 ? "" : "s"} ·{" "}
                {jobStatus ?? "loading"}
              </span>
            )}
            <button
              type="button"
              onClick={handleNewJob}
              className="inline-flex h-9 items-center gap-2 rounded-md border border-[#dfe3e8] px-3 text-sm font-medium text-[#475467] hover:bg-[#f2f4f7]"
            >
              <X aria-hidden="true" size={14} />
              New job
            </button>
          </div>
        </div>
      ) : null}

      {/* Workflow steps */}
      {STEPS.map((step) => {
        const status = stepStatuses[step.id];
        const summary = stepSummaries[step.id];
        const isExpanded = expandedStep === step.id;
        const isDisabled =
          status === "not_started" && step.id !== "upload";
        const statusInfo = statusConfig[status];
        const StepIcon = step.icon;

        return (
          <div
            key={step.id}
            className={`rounded-lg border bg-white transition ${
              isExpanded
                ? "border-[#1d4ed8]/30 shadow-sm"
                : "border-[#dfe3e8]"
            } ${isDisabled ? "opacity-60" : ""}`}
          >
            {/* Step header */}
            <button
              type="button"
              onClick={() => !isDisabled && toggleStep(step.id)}
              disabled={isDisabled}
              className="flex w-full items-center gap-4 px-5 py-4 text-left disabled:cursor-not-allowed"
            >
              <div
                className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${
                  status === "complete"
                    ? "bg-[#eef6f0] text-[#20744a]"
                    : isExpanded
                      ? "bg-[#edf4ff] text-[#1d4ed8]"
                      : "bg-[#f2f4f7] text-[#475467]"
                }`}
              >
                {status === "complete" ? (
                  <CheckCircle2 aria-hidden="true" size={20} />
                ) : (
                  <StepIcon aria-hidden="true" size={20} />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold uppercase text-[#667085]">
                    Step {step.number}
                  </span>
                  <span
                    className={`rounded-md px-2 py-0.5 text-xs font-medium ${statusInfo.className}`}
                  >
                    {statusInfo.label}
                  </span>
                </div>
                <p className="mt-0.5 text-sm font-semibold text-[#151923]">
                  {step.label}
                </p>
                {summary ? (
                  <p className="mt-0.5 text-sm text-[#667085]">{summary}</p>
                ) : (
                  <p className="mt-0.5 text-sm text-[#667085]">
                    {step.description}
                  </p>
                )}
              </div>
              <div className="shrink-0 text-[#667085]">
                {isExpanded ? (
                  <ChevronDown aria-hidden="true" size={20} />
                ) : (
                  <ChevronRight aria-hidden="true" size={20} />
                )}
              </div>
            </button>

            {/* Step content */}
            {isExpanded ? (
              <div className="border-t border-[#dfe3e8] p-5">
                {step.id === "upload" && (
                  <ImageUploadPanel
                    embedded
                    onJobCreated={handleJobCreated}
                  />
                )}

                {step.id === "optimize" && activeJobId && (
                  <ImageUploadPanel
                    key={activeJobId}
                    activeJobId={activeJobId}
                    embedded
                    onProcessed={handleProcessed}
                  />
                )}

                {step.id === "metadata" && activeJobId && (
                  <SeoMetadataPanel
                    key={activeJobId}
                    activeJobId={activeJobId}
                    embedded
                  />
                )}

                {step.id === "resize" && activeJobId && (
                  <ImageResizerPanel
                    key={activeJobId}
                    activeJobId={activeJobId}
                    embedded
                  />
                )}

                {step.id === "export" && activeJobId && (
                  <ExportStep
                    jobId={activeJobId}
                    isProcessed={isProcessed}
                    metadataCount={metadataGeneratedCount}
                    allFileIds={allFileIds}
                  />
                )}

                {step.id !== "upload" && !activeJobId && (
                  <div className="rounded-lg border border-dashed border-[#b8c0cc] bg-[#fafbfc] px-4 py-10 text-center">
                    <p className="text-sm text-[#667085]">
                      Upload images in Step 1 to unlock this step.
                    </p>
                  </div>
                )}
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

/* ---------- Export step sub-component ---------- */

function ExportStep({
  jobId,
  isProcessed,
  metadataCount,
  allFileIds,
}: {
  jobId: string;
  isProcessed: boolean;
  metadataCount: number;
  allFileIds: string[];
}) {
  const optimizedZipUrl = getProcessedImagesZipDownloadUrl(jobId);
  const metadataZipUrl =
    allFileIds.length > 0
      ? getImageMetadataZipDownloadUrl(jobId, allFileIds)
      : "";

  const hasAnyExport = isProcessed || metadataCount > 0;

  if (!hasAnyExport) {
    return (
      <div className="rounded-lg border border-dashed border-[#b8c0cc] bg-[#fafbfc] px-4 py-10 text-center">
        <FileArchive
          aria-hidden="true"
          className="mx-auto text-[#667085]"
          size={28}
        />
        <p className="mt-3 text-sm font-medium text-[#151923]">
          No exports available yet
        </p>
        <p className="mt-2 text-sm text-[#667085]">
          Process images or generate metadata to unlock downloads.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2">
        {/* Optimized images export */}
        <div className="rounded-lg border border-[#dfe3e8] p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#edf4ff] text-[#1d4ed8]">
              <ImageIcon aria-hidden="true" size={20} />
            </div>
            <div>
              <p className="text-sm font-semibold text-[#151923]">
                Optimized Images
              </p>
              <p className="text-sm text-[#667085]">
                {isProcessed
                  ? "Compressed and converted images"
                  : "Process images first"}
              </p>
            </div>
          </div>
          <button
            type="button"
            disabled={!isProcessed}
            onClick={() => {
              if (isProcessed) {
                downloadApiFile(optimizedZipUrl, `${jobId}-optimized.zip`);
              }
            }}
            className={`mt-4 inline-flex h-10 w-full items-center justify-center gap-2 rounded-md text-sm font-medium ${
              isProcessed
                ? "bg-[#1d4ed8] text-white hover:bg-[#1e40af]"
                : "cursor-not-allowed bg-[#98a2b3] text-white"
            }`}
            aria-disabled={!isProcessed}
          >
            <Download aria-hidden="true" size={16} />
            Download Optimized ZIP
          </button>
        </div>

        {/* SEO metadata export */}
        <div className="rounded-lg border border-[#dfe3e8] p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#edf4ff] text-[#1d4ed8]">
              <Sparkles aria-hidden="true" size={20} />
            </div>
            <div>
              <p className="text-sm font-semibold text-[#151923]">
                SEO Metadata Export
              </p>
              <p className="text-sm text-[#667085]">
                {metadataCount > 0
                  ? `${metadataCount} image${metadataCount === 1 ? "" : "s"} with metadata`
                  : "Generate metadata first"}
              </p>
            </div>
          </div>
          <button
            type="button"
            disabled={metadataCount <= 0}
            onClick={() => {
              if (metadataCount > 0) {
                downloadApiFile(metadataZipUrl, `${jobId}-seo-metadata.zip`);
              }
            }}
            className={`mt-4 inline-flex h-10 w-full items-center justify-center gap-2 rounded-md text-sm font-medium ${
              metadataCount > 0
                ? "bg-[#1d4ed8] text-white hover:bg-[#1e40af]"
                : "cursor-not-allowed bg-[#98a2b3] text-white"
            }`}
            aria-disabled={metadataCount <= 0}
          >
            <Download aria-hidden="true" size={16} />
            Download Metadata ZIP
          </button>
        </div>
      </div>

      <p className="text-sm text-[#667085]">
        Exports contain processed images renamed with SEO-friendly filenames and
        a report.csv with all metadata.
      </p>
    </div>
  );
}
