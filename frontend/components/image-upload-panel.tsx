"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useDropzone } from "react-dropzone";
import {
  AlertCircle,
  CheckCircle2,
  Download,
  FileArchive,
  ImageIcon,
  Loader2,
  SlidersHorizontal,
  Trash2,
  Upload,
  Repeat2,
} from "lucide-react";

import {
  getApiErrorMessage,
  getJobFiles,
  getProcessedImageDownloadUrl,
  getProcessedImagesZipDownloadUrl,
  type ImageCompressionResponse,
  type ImageCompressionSettings,
  type ImageJobCreateResponse,
  processImageJob,
  uploadImageJob,
} from "@/lib/api";
import { setActiveImageJobId } from "@/lib/workspace";

const ACCEPTED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp", ".zip"];
const ACCEPTED_MIME_TYPES = {
  "image/jpeg": [".jpg", ".jpeg"],
  "image/png": [".png"],
  "image/webp": [".webp"],
  "application/zip": [".zip"],
  "application/x-zip-compressed": [".zip"],
};

const DEFAULT_COMPRESSION_SETTINGS: ImageCompressionSettings = {
  mode: "lossy",
  quality: 80,
  resize_mode: "none",
  output_format: "keep_original",
  custom_max_width: null,
  strip_metadata: true,
  filename_overrides: {},
};

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fileExtension(file: File) {
  const index = file.name.lastIndexOf(".");
  return index >= 0 ? file.name.slice(index).toLowerCase() : "";
}

function filenameStem(filename: string) {
  const index = filename.lastIndexOf(".");
  return index > 0 ? filename.slice(0, index) : filename;
}

function targetExtension(storedFilename: string, outputFormat: ImageCompressionSettings["output_format"]) {
  if (outputFormat === "keep_original") {
    const index = storedFilename.lastIndexOf(".");
    return index >= 0 ? storedFilename.slice(index).toLowerCase() : "";
  }
  return outputFormat === "jpg" ? ".jpg" : `.${outputFormat}`;
}

function slugifyPreview(value: string) {
  const slug = value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/-{2,}/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 60)
    .replace(/-$/g, "");

  return slug || "file";
}

export function ImageUploadPanel() {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [clientError, setClientError] = useState("");
  const [lastJob, setLastJob] = useState<ImageJobCreateResponse | null>(null);
  const [compressionSettings, setCompressionSettings] = useState<ImageCompressionSettings>(
    DEFAULT_COMPRESSION_SETTINGS,
  );
  const [compressionResult, setCompressionResult] = useState<ImageCompressionResponse | null>(null);
  const [filenameOverrides, setFilenameOverrides] = useState<Record<string, string>>({});

  const uploadMutation = useMutation({
    mutationFn: async (files: File[]) => {
      setUploadProgress(0);
      return uploadImageJob(files, setUploadProgress);
    },
    onSuccess: (job) => {
      setLastJob(job);
      setActiveImageJobId(job.id);
      setCompressionResult(null);
      setFilenameOverrides(
        Object.fromEntries(job.files.map((file) => [file.id, filenameStem(file.stored_filename)])),
      );
      setUploadProgress(100);
    },
  });

  const compressionMutation = useMutation({
    mutationFn: async () => {
      if (!lastJob) throw new Error("Upload images before processing.");
      return processImageJob(lastJob.id, {
        ...compressionSettings,
        filename_overrides: filenameOverrides,
      });
    },
    onSuccess: (result) => {
      setCompressionResult(result);
    },
  });

  const filesQuery = useQuery({
    queryKey: ["image-job-files", lastJob?.id],
    queryFn: () => getJobFiles(lastJob?.id ?? ""),
    enabled: Boolean(lastJob?.id),
  });

  const totalSize = useMemo(
    () => selectedFiles.reduce((total, file) => total + file.size, 0),
    [selectedFiles],
  );

  const onDrop = (acceptedFiles: File[]) => {
    setClientError("");
    setLastJob(null);
    setCompressionResult(null);
    setFilenameOverrides({});
    uploadMutation.reset();
    compressionMutation.reset();

    const unsupported = acceptedFiles.find(
      (file) => !ACCEPTED_EXTENSIONS.includes(fileExtension(file)),
    );

    if (unsupported) {
      setSelectedFiles([]);
      setClientError(`${unsupported.name} is not a supported file type.`);
      return;
    }

    setSelectedFiles(acceptedFiles);
  };

  const removeSelectedFile = (fileToRemove: File) => {
    setClientError("");
    setLastJob(null);
    setCompressionResult(null);
    setFilenameOverrides({});
    uploadMutation.reset();
    compressionMutation.reset();
    setSelectedFiles((files) => files.filter((file) => file !== fileToRemove));
  };

  const clearSelectedFiles = () => {
    setClientError("");
    setLastJob(null);
    setCompressionResult(null);
    setFilenameOverrides({});
    uploadMutation.reset();
    compressionMutation.reset();
    setSelectedFiles([]);
  };

  const dropzone = useDropzone({
    onDrop,
    accept: ACCEPTED_MIME_TYPES,
    multiple: true,
    onDropRejected: (rejections) => {
      const first = rejections[0];
      setClientError(first ? `${first.file.name} is not a supported file type.` : "Upload rejected.");
    },
  });

  const uploadDisabled = selectedFiles.length === 0 || uploadMutation.isPending;
  const uploadedFiles = filesQuery.data?.files ?? lastJob?.files ?? [];
  const processDisabled = !lastJob || compressionMutation.isPending;
  const showJpgTransparencyNote =
    compressionSettings.output_format === "jpg" &&
    selectedFiles.some((file) => fileExtension(file) === ".png");

  return (
    <section className="rounded-lg border border-[#dfe3e8] bg-white">
      <div className="flex flex-col gap-2 border-b border-[#dfe3e8] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold">Image Upload</h2>
          <p className="mt-1 text-sm text-[#667085]">Images and ZIP archives for Phase 1.</p>
        </div>
        {lastJob ? (
          <span className="inline-flex h-8 items-center gap-2 rounded-md bg-[#eef6f0] px-3 text-sm font-medium text-[#20744a]">
            <CheckCircle2 aria-hidden="true" size={16} />
            {lastJob.id}
          </span>
        ) : null}
      </div>

      <div className="grid gap-5 p-5 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="space-y-4">
          <div
            {...dropzone.getRootProps()}
            className={`flex min-h-56 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed px-5 py-8 text-center transition ${
              dropzone.isDragActive
                ? "border-[#1d4ed8] bg-[#edf4ff]"
                : "border-[#b8c0cc] bg-[#fafbfc] hover:border-[#1d4ed8]"
            }`}
          >
            <input {...dropzone.getInputProps()} />
            <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-white text-[#1d4ed8] shadow-sm">
              <Upload aria-hidden="true" size={21} />
            </div>
            <p className="mt-4 text-sm font-medium text-[#151923]">
              Drop files here or click to browse
            </p>
            <p className="mt-2 max-w-sm text-sm text-[#667085]">
              JPG, PNG, WebP, and ZIP. Direct images and ZIP entries are limited to 5MB each.
            </p>
          </div>

          {clientError || uploadMutation.isError ? (
            <div className="flex items-start gap-2 rounded-md border border-[#f2b8b5] bg-[#fff5f5] p-3 text-sm text-[#b42318]">
              <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={16} />
              <span>{clientError || getApiErrorMessage(uploadMutation.error)}</span>
            </div>
          ) : null}

          {uploadMutation.isPending ? (
            <div>
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="font-medium">Uploading</span>
                <span className="text-[#667085]">{uploadProgress}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-[#edf0f2]">
                <div
                  className="h-full rounded-full bg-[#1d4ed8] transition-all"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          ) : null}

          <button
            type="button"
            disabled={uploadDisabled}
            onClick={() => uploadMutation.mutate(selectedFiles)}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-[#1d4ed8] px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-[#98a2b3]"
          >
            {uploadMutation.isPending ? (
              <Loader2 aria-hidden="true" className="animate-spin" size={16} />
            ) : (
              <Upload aria-hidden="true" size={16} />
            )}
            Upload files
          </button>
        </div>

        <div className="min-w-0 rounded-lg border border-[#dfe3e8]">
          <div className="flex items-center justify-between border-b border-[#dfe3e8] px-4 py-3">
            <div>
              <p className="text-sm font-medium">Selected Files</p>
              <p className="mt-0.5 text-xs text-[#667085]">
                {selectedFiles.length} file{selectedFiles.length === 1 ? "" : "s"} ·{" "}
                {formatBytes(totalSize)}
              </p>
            </div>
            {selectedFiles.length > 0 ? (
              <button
                type="button"
                disabled={uploadMutation.isPending}
                onClick={clearSelectedFiles}
                className="inline-flex h-8 items-center gap-2 rounded-md border border-[#dfe3e8] px-2.5 text-xs font-medium text-[#475467] hover:bg-[#f2f4f7] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Trash2 aria-hidden="true" size={14} />
                Clear
              </button>
            ) : null}
          </div>
          <div className="max-h-72 overflow-auto">
            {selectedFiles.length === 0 ? (
              <div className="px-4 py-10 text-center text-sm text-[#667085]">
                No files selected.
              </div>
            ) : (
              <ul className="divide-y divide-[#edf0f2]">
                {selectedFiles.map((file) => {
                  const isZip = fileExtension(file) === ".zip";
                  const Icon = isZip ? FileArchive : ImageIcon;
                  return (
                    <li key={`${file.name}-${file.size}`} className="flex items-center gap-3 px-4 py-3">
                      <Icon aria-hidden="true" className="shrink-0 text-[#475467]" size={18} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-[#151923]">{file.name}</p>
                        <p className="text-xs text-[#667085]">{formatBytes(file.size)}</p>
                      </div>
                      <button
                        type="button"
                        disabled={uploadMutation.isPending}
                        onClick={() => removeSelectedFile(file)}
                        aria-label={`Remove ${file.name}`}
                        title={`Remove ${file.name}`}
                        className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-[#667085] hover:bg-[#fff1f0] hover:text-[#b42318] disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <Trash2 aria-hidden="true" size={16} />
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      </div>

      {lastJob ? (
        <div className="border-t border-[#dfe3e8] px-5 py-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold">Filename Cleanup</h3>
            {filesQuery.isFetching ? (
              <span className="inline-flex items-center gap-2 text-xs text-[#667085]">
                <Loader2 aria-hidden="true" className="animate-spin" size={14} />
                Refreshing
              </span>
            ) : null}
          </div>
          <div className="overflow-x-auto rounded-lg border border-[#dfe3e8]">
            <table className="w-full min-w-[920px] text-left text-sm">
              <thead className="bg-[#fafbfc] text-[#667085]">
                <tr>
                  <th className="px-4 py-3 font-medium">Original</th>
                  <th className="px-4 py-3 font-medium">Filename Stem</th>
                  <th className="px-4 py-3 font-medium">Output Filename</th>
                  <th className="px-4 py-3 font-medium">Source</th>
                  <th className="px-4 py-3 font-medium">Size</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#edf0f2]">
                {uploadedFiles.map((file) => {
                  const currentStem = filenameOverrides[file.id] ?? filenameStem(file.stored_filename);
                  const outputFilename = `${slugifyPreview(currentStem)}${targetExtension(
                    file.stored_filename,
                    compressionSettings.output_format,
                  )}`;

                  return (
                    <tr key={file.id}>
                      <td className="px-4 py-3 text-[#151923]">{file.original_filename}</td>
                      <td className="px-4 py-3">
                        <input
                          type="text"
                          value={currentStem}
                          onChange={(event) =>
                            setFilenameOverrides((overrides) => ({
                              ...overrides,
                              [file.id]: event.target.value,
                            }))
                          }
                          className="h-9 w-full rounded-md border border-[#dfe3e8] bg-white px-3 text-sm text-[#151923]"
                          aria-label={`Filename stem for ${file.original_filename}`}
                        />
                      </td>
                      <td className="px-4 py-3 font-medium text-[#475467]">{outputFilename}</td>
                      <td className="px-4 py-3 text-[#475467]">
                        {file.source === "zip" ? `ZIP: ${file.source_archive}` : "Direct upload"}
                      </td>
                      <td className="px-4 py-3 text-[#475467]">{formatBytes(file.size_bytes)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      <div className="border-t border-[#dfe3e8] px-5 py-4">
        <div className="mb-5 flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#edf4ff] text-[#1d4ed8]">
            <SlidersHorizontal aria-hidden="true" size={18} />
          </div>
          <div>
            <h3 className="text-sm font-semibold">Processing Settings</h3>
            <p className="text-sm text-[#667085]">
              Compress and optionally convert uploaded images in one processing step.
            </p>
          </div>
        </div>

        <div className="rounded-lg border border-[#dfe3e8] bg-[#fafbfc] p-4">
          <div className="mb-4 flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white text-[#1d4ed8] shadow-sm">
              <Repeat2 aria-hidden="true" size={16} />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-[#151923]">Image Conversion</h4>
              <p className="text-sm text-[#667085]">Choose the output format for processed files.</p>
            </div>
          </div>

          <label className="block max-w-sm space-y-2">
            <span className="text-sm font-medium text-[#151923]">Output format</span>
            <select
              value={compressionSettings.output_format}
              onChange={(event) =>
                setCompressionSettings((settings) => ({
                  ...settings,
                  output_format: event.target.value as ImageCompressionSettings["output_format"],
                }))
              }
              className="h-10 w-full rounded-md border border-[#dfe3e8] bg-white px-3 text-sm"
            >
              <option value="keep_original">Keep original</option>
              <option value="webp">WebP</option>
              <option value="jpg">JPG</option>
              <option value="png">PNG</option>
            </select>
          </label>
        </div>

        {showJpgTransparencyNote ? (
          <div className="mt-3 flex items-start gap-2 rounded-md border border-[#f9d7a8] bg-[#fff8ed] p-3 text-sm text-[#92400e]">
            <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={16} />
            <span>Transparent PNG areas will be flattened onto a white background when converting to JPG.</span>
          </div>
        ) : null}

        <div className="mt-5 rounded-lg border border-[#dfe3e8] bg-white p-4">
          <div className="mb-4">
            <h4 className="text-sm font-semibold text-[#151923]">Compression Settings</h4>
            <p className="text-sm text-[#667085]">
              RFC defaults: lossy, quality 80, no resize, strip metadata.
            </p>
          </div>

          <div className="grid gap-4 lg:grid-cols-4">

          <label className="space-y-2">
            <span className="text-sm font-medium text-[#151923]">Mode</span>
            <select
              value={compressionSettings.mode}
              onChange={(event) =>
                setCompressionSettings((settings) => ({
                  ...settings,
                  mode: event.target.value as ImageCompressionSettings["mode"],
                }))
              }
              className="h-10 w-full rounded-md border border-[#dfe3e8] bg-white px-3 text-sm"
            >
              <option value="lossy">Lossy</option>
              <option value="lossless">Lossless</option>
            </select>
          </label>

          <label className="space-y-2 lg:col-span-2">
            <span className="flex items-center justify-between text-sm font-medium text-[#151923]">
              Quality
              <span className="text-[#667085]">{compressionSettings.quality}</span>
            </span>
            <input
              type="range"
              min="60"
              max="90"
              step="10"
              value={compressionSettings.quality}
              onChange={(event) =>
                setCompressionSettings((settings) => ({
                  ...settings,
                  quality: Number(event.target.value),
                }))
              }
              className="w-full accent-[#1d4ed8]"
            />
            <div className="flex justify-between text-xs text-[#667085]">
              <span>More compression</span>
              <span>Higher quality</span>
            </div>
          </label>

          <label className="space-y-2">
            <span className="text-sm font-medium text-[#151923]">Resize</span>
            <select
              value={compressionSettings.resize_mode}
              onChange={(event) =>
                setCompressionSettings((settings) => ({
                  ...settings,
                  resize_mode: event.target.value as ImageCompressionSettings["resize_mode"],
                  custom_max_width: event.target.value === "custom" ? settings.custom_max_width ?? 1600 : null,
                }))
              }
              className="h-10 w-full rounded-md border border-[#dfe3e8] bg-white px-3 text-sm"
            >
              <option value="none">None</option>
              <option value="max_1920">Max width 1920px</option>
              <option value="max_1200">Max width 1200px</option>
              <option value="custom">Custom max width</option>
              </select>
            </label>
          </div>
        </div>

        <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
            {compressionSettings.resize_mode === "custom" ? (
              <label className="space-y-2">
                <span className="text-sm font-medium text-[#151923]">Custom width</span>
                <input
                  type="number"
                  min="1"
                  max="10000"
                  value={compressionSettings.custom_max_width ?? 1600}
                  onChange={(event) =>
                    setCompressionSettings((settings) => ({
                      ...settings,
                      custom_max_width: Number(event.target.value),
                    }))
                  }
                  className="h-10 w-40 rounded-md border border-[#dfe3e8] bg-white px-3 text-sm"
                />
              </label>
            ) : null}

            <label className="flex items-center gap-2 text-sm font-medium text-[#151923]">
              <input
                type="checkbox"
                checked={compressionSettings.strip_metadata}
                onChange={(event) =>
                  setCompressionSettings((settings) => ({
                    ...settings,
                    strip_metadata: event.target.checked,
                  }))
                }
                className="h-4 w-4 accent-[#1d4ed8]"
              />
              Strip metadata
            </label>
          </div>

          <button
            type="button"
            disabled={processDisabled}
            onClick={() => compressionMutation.mutate()}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-[#1d4ed8] px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-[#98a2b3]"
          >
            {compressionMutation.isPending ? (
              <Loader2 aria-hidden="true" className="animate-spin" size={16} />
            ) : (
              <SlidersHorizontal aria-hidden="true" size={16} />
            )}
            Process images
          </button>
        </div>

        {!lastJob ? (
          <p className="mt-3 text-sm text-[#667085]">
            Upload at least one image before processing.
          </p>
        ) : null}

        {compressionMutation.isError ? (
          <div className="mt-4 flex items-start gap-2 rounded-md border border-[#f2b8b5] bg-[#fff5f5] p-3 text-sm text-[#b42318]">
            <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={16} />
            <span>{getApiErrorMessage(compressionMutation.error)}</span>
          </div>
        ) : null}
      </div>

      {compressionResult ? (
        <div className="border-t border-[#dfe3e8] px-5 py-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold">Optimization Results</h3>
            <div className="flex items-center gap-3">
              <span className="rounded-md bg-[#eef6f0] px-2 py-1 text-xs font-medium text-[#20744a]">
                {compressionResult.results.length} processed
              </span>
              <a
                href={getProcessedImagesZipDownloadUrl(compressionResult.job_id)}
                download={`${compressionResult.job_id}-processed-images.zip`}
                className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-[#dfe3e8] px-3 text-sm font-medium text-[#475467] hover:bg-[#edf4ff] hover:text-[#1d4ed8]"
              >
                <FileArchive aria-hidden="true" size={16} />
                Download ZIP
              </a>
            </div>
          </div>
          <div className="overflow-x-auto rounded-lg border border-[#dfe3e8]">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead className="bg-[#fafbfc] text-[#667085]">
                <tr>
                  <th className="px-4 py-3 font-medium">File</th>
                  <th className="px-4 py-3 font-medium">Format</th>
                  <th className="px-4 py-3 font-medium">Original</th>
                  <th className="px-4 py-3 font-medium">Processed</th>
                  <th className="px-4 py-3 font-medium">Savings</th>
                  <th className="px-4 py-3 font-medium">Dimensions</th>
                  <th className="px-4 py-3 text-center font-medium">Download</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#edf0f2]">
                {compressionResult.results.map((result) => (
                  <tr key={result.id}>
                    <td className="px-4 py-3 text-[#151923]">{result.processed_filename}</td>
                    <td className="px-4 py-3 text-[#475467]">
                      {result.original_format.toUpperCase()} {"->"} {result.new_format.toUpperCase()}
                    </td>
                    <td className="px-4 py-3 text-[#475467]">
                      {formatBytes(result.original_size_bytes)}
                    </td>
                    <td className="px-4 py-3 text-[#475467]">
                      {formatBytes(result.processed_size_bytes)}
                    </td>
                    <td className="px-4 py-3 text-[#475467]">
                      {result.reduction_percent.toFixed(2)}%
                    </td>
                    <td className="px-4 py-3 text-[#475467]">
                      {result.width} x {result.height}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <a
                        href={getProcessedImageDownloadUrl(
                          compressionResult.job_id,
                          result.processed_filename,
                        )}
                        download={result.processed_filename}
                        title={`Download ${result.processed_filename}`}
                        aria-label={`Download ${result.processed_filename}`}
                        className="mx-auto inline-flex h-8 w-8 items-center justify-center rounded-md text-[#475467] hover:bg-[#edf4ff] hover:text-[#1d4ed8]"
                      >
                        <Download aria-hidden="true" size={16} />
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
}
