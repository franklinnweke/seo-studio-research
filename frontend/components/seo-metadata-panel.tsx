"use client";

import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Download, Eye, Loader2, RefreshCw, Search, Sparkles, X } from "lucide-react";

import {
  generateImageMetadata,
  getApiErrorMessage,
  getImageMetadata,
  getJobFiles,
  getMetadataImageDownloadUrl,
  getSettings,
  regenerateImageMetadata,
  type ImageMetadataListResponse,
} from "@/lib/api";

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
  const [jobIdInput, setJobIdInput] = useState("");
  const [activeJobId, setActiveJobId] = useState("");
  const [metadataEdits, setMetadataEdits] = useState<Record<string, MetadataEdit>>({});
  const [selectedImageId, setSelectedImageId] = useState<string | null>(null);

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

  const generateMutation = useMutation({
    mutationFn: () => generateImageMetadata(activeJobId),
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
              model: settingsQuery.data?.ollama_model ?? "moondream",
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
    setActiveJobId(jobIdInput.trim());
    setMetadataEdits({});
    setSelectedImageId(null);
    generateMutation.reset();
    regenerateMutation.reset();
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
            <div className="rounded-md bg-[#f2f4f7] px-3 py-2 text-sm text-[#475467]">
              {settingsQuery.isLoading ? (
                "Loading AI settings"
              ) : (
                <>
                  {settingsQuery.data?.ai_provider ?? "ollama"} ·{" "}
                  {settingsQuery.data?.ollama_model ?? "moondream"}
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
        <div className="rounded-lg border border-[#dfe3e8] bg-white">
          <div className="flex flex-col gap-3 border-b border-[#dfe3e8] px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-base font-semibold">AI Image Metadata</h2>
              <p className="mt-1 text-sm text-[#667085]">{activeJobId}</p>
            </div>
            <button
              type="button"
              disabled={files.length === 0 || generateMutation.isPending}
              onClick={() => generateMutation.mutate()}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-[#1d4ed8] px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-[#98a2b3]"
            >
              {generateMutation.isPending ? (
                <Loader2 aria-hidden="true" className="animate-spin" size={16} />
              ) : (
                <Sparkles aria-hidden="true" size={16} />
              )}
              Generate metadata
            </button>
          </div>

          {filesQuery.isError || metadataQuery.isError || generateMutation.isError ? (
            <div className="m-5 flex items-start gap-2 rounded-md border border-[#f2b8b5] bg-[#fff5f5] p-3 text-sm text-[#b42318]">
              <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={16} />
              <span>
                {getApiErrorMessage(
                  filesQuery.error ?? metadataQuery.error ?? generateMutation.error,
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
              <table className="w-full min-w-[960px] table-fixed text-left text-sm">
                <thead className="bg-[#fafbfc] text-[#667085]">
                  <tr>
                    <th className="w-[18%] px-4 py-3 font-medium">Image</th>
                    <th className="w-[30%] px-4 py-3 font-medium">Filename</th>
                    <th className="w-[28%] px-4 py-3 font-medium">Alt Text</th>
                    <th className="w-[9%] px-4 py-3 font-medium">Confidence</th>
                    <th className="w-[9%] px-4 py-3 font-medium">Status</th>
                    <th className="w-[140px] px-4 py-3 text-center font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#edf0f2]">
                  {rows.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-10 text-center text-[#667085]">
                        No images found for this job.
                      </td>
                    </tr>
                  ) : (
                    rows.map(({ file, result, edit }) => (
                      <tr key={file.id}>
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
                              disabled={regenerateMutation.isPending}
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
                  disabled={regenerateMutation.isPending}
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
