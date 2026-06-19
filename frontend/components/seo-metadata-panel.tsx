"use client";

import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  Download,
  Eye,
  FileText,
  Loader2,
  RefreshCw,
  Search,
  Sparkles,
  Upload,
  X,
} from "lucide-react";

import {
  generateImageMetadata,
  getApiErrorMessage,
  getBrandContext,
  getImageMetadata,
  getImageMetadataZipDownloadUrl,
  getJobFiles,
  getMetadataImageDownloadUrl,
  getSettings,
  regenerateImageMetadata,
  uploadBrandContext,
  type ImageMetadataListResponse,
} from "@/lib/api";
import { setActiveImageJobId, useActiveImageJobId } from "@/lib/workspace";

type MetadataEdit = {
  suggested_filename: string;
  alt_text: string;
  caption: string;
};

const emptyEdit: MetadataEdit = {
  suggested_filename: "",
  alt_text: "",
  caption: "",
};

function confidenceLabel(confidence: number) {
  return `${Math.round(confidence * 100)}%`;
}

function displayText(value: string, fallback = "Not generated") {
  return value.trim() || fallback;
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function resultToEdit(result: {
  suggested_filename: string;
  alt_text: string;
  caption: string;
}): MetadataEdit {
  return {
    suggested_filename: result.suggested_filename,
    alt_text: result.alt_text,
    caption: result.caption,
  };
}

export function SeoMetadataPanel() {
  const queryClient = useQueryClient();
  const workspaceJobId = useActiveImageJobId();
  const [jobIdInput, setJobIdInput] = useState(workspaceJobId);
  const [activeJobId, setActiveJobId] = useState(workspaceJobId);
  const [metadataEdits, setMetadataEdits] = useState<Record<string, MetadataEdit>>({});
  const [selectedImageId, setSelectedImageId] = useState<string | null>(null);
  const [selectedBrandFiles, setSelectedBrandFiles] = useState<File[]>([]);
  const [brandUploadProgress, setBrandUploadProgress] = useState(0);
  const [selectedExportImageIds, setSelectedExportImageIds] = useState<string[]>([]);

  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: getSettings,
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

  const brandContextQuery = useQuery({
    queryKey: ["brand-context", activeJobId],
    queryFn: () => getBrandContext(activeJobId),
    enabled: Boolean(activeJobId),
  });

  const brandUploadMutation = useMutation({
    mutationFn: (files: File[]) => uploadBrandContext(activeJobId, files, setBrandUploadProgress),
    onSuccess: (brandContext) => {
      queryClient.setQueryData(["brand-context", activeJobId], brandContext);
      setSelectedBrandFiles([]);
      setBrandUploadProgress(0);
    },
  });

  const generateMutation = useMutation({
    mutationFn: async () => {
      const availableImageIds = new Set((filesQuery.data?.files ?? []).map((file) => file.id));
      const selectedImageIds = selectedExportImageIds.filter((imageId) =>
        availableImageIds.has(imageId),
      );

      if (selectedImageIds.length === 0) {
        return generateImageMetadata(activeJobId);
      }

      const generatedResults = [];
      for (const imageId of selectedImageIds) {
        generatedResults.push(await regenerateImageMetadata(activeJobId, imageId));
      }

      const current = queryClient.getQueryData<ImageMetadataListResponse>([
        "image-metadata",
        activeJobId,
      ]);
      const generatedIds = new Set(generatedResults.map((result) => result.id));

      return {
        ...(current ?? {
          job_id: activeJobId,
          provider: settingsQuery.data?.ai_provider ?? "ollama",
          model: `${settingsQuery.data?.vision_model ?? "qwen2.5vl:3b"} + ${
            settingsQuery.data?.language_model ?? "qwen3.5"
          }`,
          vision_model: settingsQuery.data?.vision_model ?? "qwen2.5vl:3b",
          language_model: settingsQuery.data?.language_model ?? "qwen3.5",
        }),
        results: [
          ...(current?.results ?? []).filter((result) => !generatedIds.has(result.id)),
          ...generatedResults,
        ],
      };
    },
    onSuccess: (metadata) => {
      queryClient.setQueryData(["image-metadata", activeJobId], metadata);
      setMetadataEdits(Object.fromEntries(metadata.results.map((result) => [result.id, resultToEdit(result)])));
    },
  });

  const regenerateMutation = useMutation({
    mutationFn: (imageId: string) => regenerateImageMetadata(activeJobId, imageId),
    onSuccess: (result) => {
      queryClient.setQueryData(
        ["image-metadata", activeJobId],
        (current: ImageMetadataListResponse | undefined) => {
          const results = current?.results ?? [];
          const nextResults = results.filter((item) => item.id !== result.id);
          return {
            ...(current ?? {
              job_id: activeJobId,
              provider: settingsQuery.data?.ai_provider ?? "ollama",
              model: `${settingsQuery.data?.vision_model ?? "qwen2.5vl:3b"} + ${
                settingsQuery.data?.language_model ?? "qwen3.5"
              }`,
              vision_model: settingsQuery.data?.vision_model ?? "qwen2.5vl:3b",
              language_model: settingsQuery.data?.language_model ?? "qwen3.5",
            }),
            results: [...nextResults, result],
          };
        },
      );
      setMetadataEdits((current) => ({
        ...current,
        [result.id]: resultToEdit(result),
      }));
    },
  });

  const metadataById = useMemo(() => {
    return new Map((metadataQuery.data?.results ?? []).map((result) => [result.id, result]));
  }, [metadataQuery.data]);

  const files = filesQuery.data?.files ?? [];
  const rows = files.map((file) => {
    const result = metadataById.get(file.id);
    const edit = metadataEdits[file.id] ?? {
      suggested_filename: result?.suggested_filename ?? "",
      alt_text: result?.alt_text ?? "",
      caption: result?.caption ?? "",
    };
    return { file, result, edit };
  });

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextJobId = jobIdInput.trim();
    setActiveJobId(nextJobId);
    setActiveImageJobId(nextJobId);
    setMetadataEdits({});
    setSelectedImageId(null);
    setSelectedBrandFiles([]);
    setBrandUploadProgress(0);
    brandUploadMutation.reset();
    generateMutation.reset();
    regenerateMutation.reset();
    setSelectedExportImageIds([]);
  };

  const updateEdit = (imageId: string, update: Partial<MetadataEdit>) => {
    const result = metadataById.get(imageId);
    setMetadataEdits((current) => ({
      ...current,
      [imageId]: {
        ...(current[imageId] ?? (result ? resultToEdit(result) : emptyEdit)),
        ...update,
      },
    }));
  };

  const selectedRow = rows.find(({ file }) => file.id === selectedImageId) ?? null;
  const selectedPreviewUrl =
    activeJobId && selectedRow
      ? getMetadataImageDownloadUrl(
          activeJobId,
          selectedRow.file.id,
          selectedRow.edit.suggested_filename,
        )
      : "";
  const brandContext = brandContextQuery.data;
  const brandDocuments = brandContext?.documents ?? [];
  const brandContextPreview = brandContext?.combined_text ?? "";
  const brandUploadDisabled =
    !activeJobId || selectedBrandFiles.length === 0 || brandUploadMutation.isPending;
  const selectedExportIds = rows
    .map(({ file }) => file.id)
    .filter((imageId) => selectedExportImageIds.includes(imageId));
  const allRowsSelected = rows.length > 0 && selectedExportIds.length === rows.length;
  const someRowsSelected = selectedExportIds.length > 0;
  const selectedZipExportUrl =
    activeJobId && selectedExportIds.length > 0
      ? getImageMetadataZipDownloadUrl(activeJobId, selectedExportIds)
      : "";

  const toggleExportImage = (imageId: string) => {
    setSelectedExportImageIds((current) =>
      current.includes(imageId)
        ? current.filter((item) => item !== imageId)
        : [...current, imageId],
    );
  };

  const toggleAllExportImages = () => {
    setSelectedExportImageIds(allRowsSelected ? [] : rows.map(({ file }) => file.id));
  };

  return (
    <section className="space-y-5">
      <div className="rounded-lg border border-[#dfe3e8] bg-white">
        <div className="border-b border-[#dfe3e8] px-5 py-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-base font-semibold">Image Metadata Job</h2>
              <p className="mt-1 text-sm text-[#667085]">
                Use an existing image job from Image Optimizer to generate AI metadata.
              </p>
            </div>
            <div className="grid gap-2 rounded-md bg-[#f2f4f7] px-3 py-2 text-sm text-[#475467] sm:grid-cols-2">
              {settingsQuery.isLoading ? (
                <span className="sm:col-span-2">Loading AI settings</span>
              ) : (
                <>
                  <span>
                    <span className="text-[#667085]">Vision</span>{" "}
                    <span className="font-medium text-[#151923]">
                      {settingsQuery.data?.vision_model ?? "qwen2.5vl:3b"}
                    </span>
                  </span>
                  <span>
                    <span className="text-[#667085]">Language</span>{" "}
                    <span className="font-medium text-[#151923]">
                      {settingsQuery.data?.language_model ?? "qwen3.5"}
                    </span>
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        <form onSubmit={onSubmit} className="flex flex-col gap-3 p-5 sm:flex-row">
          <label className="min-w-0 flex-1 space-y-2">
            <span className="text-sm font-medium text-[#151923]">Image job ID</span>
            <input
              type="text"
              value={jobIdInput}
              onChange={(event) => setJobIdInput(event.target.value)}
              placeholder="job_..."
              className="h-10 w-full rounded-md border border-[#dfe3e8] bg-white px-3 text-sm"
            />
          </label>
          <button
            type="submit"
            disabled={!jobIdInput.trim()}
            className="inline-flex h-10 items-center justify-center gap-2 self-end rounded-md bg-[#1d4ed8] px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-[#98a2b3]"
          >
            <Search aria-hidden="true" size={16} />
            Load job
          </button>
        </form>
      </div>

      {activeJobId ? (
        <>
          <div className="rounded-lg border border-[#dfe3e8] bg-white">
            <div className="flex flex-col gap-3 border-b border-[#dfe3e8] px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h2 className="text-base font-semibold">Brand Context</h2>
                <p className="mt-1 text-sm text-[#667085]">
                  Attach TXT, DOCX, or PDF files to guide AI naming, tone, and wording.
                </p>
              </div>
              <span className="rounded-md bg-[#f2f4f7] px-2.5 py-1 text-sm text-[#475467]">
                {brandDocuments.length} document{brandDocuments.length === 1 ? "" : "s"}
              </span>
            </div>

            <div className="grid gap-5 p-5 xl:grid-cols-[0.9fr_1.1fr]">
              <div className="space-y-3">
                <label className="block space-y-2">
                  <span className="text-sm font-medium text-[#151923]">Brand documents</span>
                  <input
                    type="file"
                    multiple
                    accept=".txt,.docx,.pdf,text/plain,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    onChange={(event) => setSelectedBrandFiles(Array.from(event.target.files ?? []))}
                    className="block w-full rounded-md border border-[#dfe3e8] bg-white px-3 py-2 text-sm text-[#475467] file:mr-3 file:rounded-md file:border-0 file:bg-[#edf4ff] file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-[#1d4ed8]"
                  />
                </label>

                {selectedBrandFiles.length > 0 ? (
                  <div className="rounded-md border border-[#dfe3e8] bg-[#fafbfc] p-3">
                    <p className="text-xs font-medium uppercase text-[#667085]">Selected</p>
                    <div className="mt-2 space-y-1">
                      {selectedBrandFiles.map((file) => (
                        <p key={`${file.name}-${file.size}`} className="truncate text-sm text-[#475467]" title={file.name}>
                          {file.name} · {formatBytes(file.size)}
                        </p>
                      ))}
                    </div>
                  </div>
                ) : null}

                {brandUploadMutation.isPending ? (
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs text-[#667085]">
                      <span>Uploading context</span>
                      <span>{brandUploadProgress}%</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-[#edf0f2]">
                      <div className="h-full bg-[#1d4ed8]" style={{ width: `${brandUploadProgress}%` }} />
                    </div>
                  </div>
                ) : null}

                {brandUploadMutation.isError || brandContextQuery.isError ? (
                  <div className="flex items-start gap-2 rounded-md border border-[#f2b8b5] bg-[#fff5f5] p-3 text-sm text-[#b42318]">
                    <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={16} />
                    <span>
                      {getApiErrorMessage(brandUploadMutation.error ?? brandContextQuery.error)}
                    </span>
                  </div>
                ) : null}

                <button
                  type="button"
                  disabled={brandUploadDisabled}
                  onClick={() => brandUploadMutation.mutate(selectedBrandFiles)}
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-[#1d4ed8] px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-[#98a2b3]"
                >
                  {brandUploadMutation.isPending ? (
                    <Loader2 aria-hidden="true" className="animate-spin" size={16} />
                  ) : (
                    <Upload aria-hidden="true" size={16} />
                  )}
                  Upload context
                </button>
              </div>

              <div className="space-y-3">
                <div className="rounded-lg border border-[#dfe3e8]">
                  <div className="border-b border-[#dfe3e8] px-4 py-3">
                    <h3 className="text-sm font-medium text-[#151923]">Attached documents</h3>
                  </div>
                  {brandDocuments.length > 0 ? (
                    <div className="divide-y divide-[#edf0f2]">
                      {brandDocuments.map((document) => (
                        <div key={document.id} className="flex items-start gap-3 px-4 py-3">
                          <FileText aria-hidden="true" className="mt-0.5 shrink-0 text-[#475467]" size={16} />
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium text-[#151923]" title={document.original_filename}>
                              {document.original_filename}
                            </p>
                            <p className="mt-1 text-xs text-[#667085]">
                              {formatBytes(document.size_bytes)} · {document.extracted_chars} chars extracted
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="px-4 py-6 text-sm text-[#667085]">
                      No brand context attached yet. Metadata generation will use image content only.
                    </p>
                  )}
                </div>

                {brandContextPreview ? (
                  <div className="rounded-md border border-[#dfe3e8] bg-[#fafbfc] p-3">
                    <p className="text-xs font-medium uppercase text-[#667085]">Context preview</p>
                    <p className="mt-2 max-h-24 overflow-hidden text-sm leading-6 text-[#475467]">
                      {brandContextPreview}
                    </p>
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-[#dfe3e8] bg-white">
          <div className="border-b border-[#dfe3e8]">
            <div className="flex flex-col gap-3 px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h2 className="text-base font-semibold">AI Image Metadata</h2>
                <p className="mt-1 text-sm text-[#667085]">
                  {activeJobId}
                  {brandDocuments.length > 0 ? " · using brand context" : ""}
                </p>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                {rows.length > 0 && someRowsSelected ? (
                  <a
                    href={selectedZipExportUrl}
                    className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-[#dfe3e8] px-4 text-sm font-medium text-[#475467] hover:bg-[#edf4ff] hover:text-[#1d4ed8]"
                  >
                    <Download aria-hidden="true" size={16} />
                    Download selected ({selectedExportIds.length})
                  </a>
                ) : rows.length > 0 ? (
                  <button
                    type="button"
                    disabled
                    className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-[#dfe3e8] px-4 text-sm font-medium text-[#98a2b3]"
                  >
                    <Download aria-hidden="true" size={16} />
                    Download selected
                  </button>
                ) : null}
                <button
                  type="button"
                  disabled={files.length === 0 || generateMutation.isPending || regenerateMutation.isPending}
                  onClick={() => generateMutation.mutate()}
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-[#1d4ed8] px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-[#98a2b3]"
                >
                  {generateMutation.isPending ? (
                    <Loader2 aria-hidden="true" className="animate-spin" size={16} />
                  ) : (
                    <Sparkles aria-hidden="true" size={16} />
                  )}
                  {someRowsSelected ? `Generate selected (${selectedExportIds.length})` : "Generate metadata"}
                </button>
              </div>
            </div>
          </div>

          {filesQuery.isError ||
          metadataQuery.isError ||
          generateMutation.isError ||
          regenerateMutation.isError ? (
            <div className="m-5 flex items-start gap-2 rounded-md border border-[#f2b8b5] bg-[#fff5f5] p-3 text-sm text-[#b42318]">
              <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={16} />
              <span>
                {getApiErrorMessage(
                  filesQuery.error ??
                    metadataQuery.error ??
                    generateMutation.error ??
                    regenerateMutation.error,
                )}
              </span>
            </div>
          ) : null}

          {filesQuery.isLoading || metadataQuery.isLoading ? (
            <div className="flex items-center gap-2 px-5 py-8 text-sm text-[#667085]">
              <Loader2 aria-hidden="true" className="animate-spin" size={16} />
              Loading job images
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1040px] table-fixed text-left text-sm">
                <thead className="bg-[#fafbfc] text-[#667085]">
                  <tr>
                    <th className="w-[56px] px-4 py-3 font-medium">
                      {rows.length > 0 ? (
                        <label className="inline-flex items-center justify-center" title="Select all images">
                          <input
                            type="checkbox"
                            checked={allRowsSelected}
                            ref={(input) => {
                              if (input) input.indeterminate = someRowsSelected && !allRowsSelected;
                            }}
                            onChange={toggleAllExportImages}
                            className="h-4 w-4 rounded border-[#98a2b3] text-[#1d4ed8]"
                          />
                          <span className="sr-only">Select all images</span>
                        </label>
                      ) : null}
                    </th>
                    <th className="w-[18%] px-4 py-3 font-medium">Image</th>
                    <th className="w-[30%] px-4 py-3 font-medium">
                      Filename
                    </th>
                    <th className="w-[28%] px-4 py-3 font-medium">
                      Alt Text
                    </th>
                    <th className="w-[9%] px-4 py-3 font-medium">Confidence</th>
                    <th className="w-[9%] px-4 py-3 font-medium">Status</th>
                    <th className="w-[140px] px-4 py-3 text-center font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#edf0f2]">
                  {rows.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-10 text-center text-[#667085]">
                        No images found for this job.
                      </td>
                    </tr>
                  ) : (
                    rows.map(({ file, result, edit }) => (
                      <tr key={file.id}>
                        <td className="px-4 py-3">
                          <label className="inline-flex items-center justify-center" title={`Select ${file.original_filename}`}>
                            <input
                              type="checkbox"
                              checked={selectedExportImageIds.includes(file.id)}
                              onChange={() => toggleExportImage(file.id)}
                              className="h-4 w-4 rounded border-[#98a2b3] text-[#1d4ed8]"
                            />
                            <span className="sr-only">Select {file.original_filename}</span>
                          </label>
                        </td>
                        <td className="px-4 py-3">
                          <p className="truncate font-medium text-[#151923]" title={file.original_filename}>
                            {file.original_filename}
                          </p>
                        </td>
                        <td className="px-4 py-3 text-[#475467]">
                          <p
                            className="truncate"
                            title={displayText(edit.suggested_filename)}
                          >
                            {displayText(edit.suggested_filename)}
                          </p>
                        </td>
                        <td className="px-4 py-3 text-[#475467]">
                          <p className="truncate" title={displayText(edit.alt_text)}>
                            {displayText(edit.alt_text)}
                          </p>
                        </td>
                        <td className="px-4 py-3 text-[#475467]">
                          {result ? confidenceLabel(result.confidence) : "Not generated"}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`rounded-md px-2 py-1 text-xs font-medium ${
                              result?.status === "failed"
                                ? "bg-[#fff1f0] text-[#b42318]"
                                : result
                                  ? "bg-[#eef6f0] text-[#20744a]"
                                  : "bg-[#f2f4f7] text-[#475467]"
                            }`}
                          >
                            {result?.status ?? "pending"}
                          </span>
                          {result?.error_message ? (
                            <p className="mt-2 max-w-52 text-xs text-[#b42318]">{result.error_message}</p>
                          ) : null}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-center gap-2">
                            <button
                              type="button"
                              onClick={() => setSelectedImageId(file.id)}
                              title={`View metadata details for ${file.original_filename}`}
                              aria-label={`View metadata details for ${file.original_filename}`}
                              className="inline-flex h-8 w-8 items-center justify-center rounded-md text-[#475467] hover:bg-[#edf4ff] hover:text-[#1d4ed8]"
                            >
                              <Eye aria-hidden="true" size={16} />
                            </button>
                            <a
                              href={getMetadataImageDownloadUrl(
                                activeJobId,
                                file.id,
                                edit.suggested_filename,
                              )}
                              title={`Download ${file.original_filename} with SEO filename`}
                              aria-label={`Download ${file.original_filename} with SEO filename`}
                              className="inline-flex h-8 w-8 items-center justify-center rounded-md text-[#475467] hover:bg-[#edf4ff] hover:text-[#1d4ed8]"
                            >
                              <Download aria-hidden="true" size={16} />
                            </a>
                            <button
                              type="button"
                              disabled={regenerateMutation.isPending || generateMutation.isPending}
                              onClick={() => regenerateMutation.mutate(file.id)}
                              title={`Regenerate metadata for ${file.original_filename}`}
                              aria-label={`Regenerate metadata for ${file.original_filename}`}
                              className="inline-flex h-8 w-8 items-center justify-center rounded-md text-[#475467] hover:bg-[#edf4ff] hover:text-[#1d4ed8] disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              <RefreshCw aria-hidden="true" size={16} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
          </div>
        </>
      ) : null}

      {selectedRow ? (
        <div className="fixed inset-0 z-50">
          <button
            type="button"
            className="absolute inset-0 cursor-default bg-[#151923]/35"
            aria-label="Close metadata details"
            onClick={() => setSelectedImageId(null)}
          />
          <aside className="absolute right-0 top-0 flex h-full w-full max-w-xl flex-col bg-white shadow-2xl">
            <div className="flex items-start justify-between gap-4 border-b border-[#dfe3e8] px-5 py-4">
              <div className="min-w-0">
                <h2 className="text-base font-semibold text-[#151923]">Metadata Details</h2>
                <p className="mt-1 truncate text-sm text-[#667085]">
                  {selectedRow.file.original_filename}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedImageId(null)}
                className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-[#475467] hover:bg-[#f2f4f7]"
                aria-label="Close metadata details"
                title="Close"
              >
                <X aria-hidden="true" size={16} />
              </button>
            </div>

            <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
              <div className="overflow-hidden rounded-lg border border-[#dfe3e8] bg-[#f6f7f9]">
                <div className="flex aspect-[16/10] items-center justify-center bg-[#eef2f6]">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={selectedPreviewUrl}
                    alt={
                      selectedRow.edit.alt_text.trim()
                        ? selectedRow.edit.alt_text
                        : `Preview of ${selectedRow.file.original_filename}`
                    }
                    className="h-full w-full object-contain"
                  />
                </div>
                <div className="border-t border-[#dfe3e8] px-4 py-3">
                  <p className="truncate text-sm font-medium text-[#151923]" title={selectedRow.file.original_filename}>
                    {selectedRow.file.original_filename}
                  </p>
                  <p className="mt-1 text-xs text-[#667085]">
                    Preview uses the processed image when available.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 rounded-lg border border-[#dfe3e8] bg-[#fafbfc] p-4 text-sm">
                <div>
                  <p className="text-xs font-medium uppercase text-[#667085]">Original filename</p>
                  <p className="mt-1 break-all text-[#151923]">{selectedRow.file.original_filename}</p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase text-[#667085]">Stored filename</p>
                  <p className="mt-1 break-all text-[#151923]">{selectedRow.file.stored_filename}</p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase text-[#667085]">Status</p>
                  <p className="mt-1 text-[#151923]">{selectedRow.result?.status ?? "pending"}</p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase text-[#667085]">Confidence</p>
                  <p className="mt-1 text-[#151923]">
                    {selectedRow.result ? confidenceLabel(selectedRow.result.confidence) : "Not generated"}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase text-[#667085]">Source</p>
                  <p className="mt-1 text-[#151923]">
                    {selectedRow.file.source === "zip" ? "ZIP archive" : "Direct upload"}
                  </p>
                </div>
              </div>

              <div className="rounded-md border border-[#dfe3e8] bg-[#fafbfc] p-3 text-sm text-[#667085]">
                Downloads use the processed image when available. Otherwise, the original upload is
                downloaded with the suggested filename.
              </div>

              {selectedRow.result?.error_message ? (
                <div className="flex items-start gap-2 rounded-md border border-[#f2b8b5] bg-[#fff5f5] p-3 text-sm text-[#b42318]">
                  <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={16} />
                  <span>{selectedRow.result.error_message}</span>
                </div>
              ) : null}

              <label className="block space-y-2">
                <span className="text-sm font-medium text-[#151923]">Suggested filename</span>
                <input
                  value={selectedRow.edit.suggested_filename}
                  onChange={(event) =>
                    updateEdit(selectedRow.file.id, { suggested_filename: event.target.value })
                  }
                  className="h-10 w-full rounded-md border border-[#dfe3e8] bg-white px-3 text-sm"
                />
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-[#151923]">Alt text</span>
                <textarea
                  value={selectedRow.edit.alt_text}
                  onChange={(event) => updateEdit(selectedRow.file.id, { alt_text: event.target.value })}
                  rows={5}
                  className="w-full resize-y rounded-md border border-[#dfe3e8] bg-white px-3 py-2 text-sm"
                />
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-[#151923]">Caption</span>
                <textarea
                  value={selectedRow.edit.caption}
                  onChange={(event) => updateEdit(selectedRow.file.id, { caption: event.target.value })}
                  rows={5}
                  className="w-full resize-y rounded-md border border-[#dfe3e8] bg-white px-3 py-2 text-sm"
                />
              </label>
            </div>

            <div className="flex items-center justify-between gap-3 border-t border-[#dfe3e8] px-5 py-4">
              <div className="flex items-center gap-2">
                <a
                  href={getMetadataImageDownloadUrl(
                    activeJobId,
                    selectedRow.file.id,
                    selectedRow.edit.suggested_filename,
                  )}
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-[#dfe3e8] px-4 text-sm font-medium text-[#475467] hover:bg-[#edf4ff] hover:text-[#1d4ed8]"
                >
                  <Download aria-hidden="true" size={16} />
                  Download
                </a>
                <button
                  type="button"
                  disabled={regenerateMutation.isPending || generateMutation.isPending}
                  onClick={() => regenerateMutation.mutate(selectedRow.file.id)}
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-[#dfe3e8] px-4 text-sm font-medium text-[#475467] hover:bg-[#edf4ff] hover:text-[#1d4ed8] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {regenerateMutation.isPending ? (
                    <Loader2 aria-hidden="true" className="animate-spin" size={16} />
                  ) : (
                    <RefreshCw aria-hidden="true" size={16} />
                  )}
                  Regenerate
                </button>
              </div>
              <button
                type="button"
                onClick={() => setSelectedImageId(null)}
                className="inline-flex h-10 items-center justify-center rounded-md bg-[#1d4ed8] px-4 text-sm font-medium text-white"
              >
                Done
              </button>
            </div>
          </aside>
        </div>
      ) : null}
    </section>
  );
}
