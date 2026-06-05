"use client";

import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useDropzone } from "react-dropzone";
import {
  AlertCircle,
  CheckCircle2,
  Crop,
  Download,
  Eye,
  FileArchive,
  ImageIcon,
  Loader2,
  Maximize2,
  RotateCcw,
  Sparkles,
  Upload,
  X,
} from "lucide-react";

import {
  getApiErrorMessage,
  getMetadataImageDownloadUrl,
  getProcessedImageDownloadUrl,
  getProcessedImagesZipDownloadUrl,
  parseResizeInstructions,
  processImageJob,
  reviewImageCrops,
  type CropReviewResponse,
  type ImageCompressionResponse,
  type ImageCompressionResult,
  type ImageCompressionSettings,
  type ImageJobCreateResponse,
  uploadImageJob,
} from "@/lib/api";
import { setActiveImageJobId } from "@/lib/workspace";

type ResizeTab = "preset" | "custom" | "instructions" | "convert";

const ACCEPTED_MIME_TYPES = {
  "image/jpeg": [".jpg", ".jpeg"],
  "image/png": [".png"],
  "image/webp": [".webp"],
  "application/zip": [".zip"],
  "application/x-zip-compressed": [".zip"],
};

const RESIZE_PRESETS = [
  { label: "Hero Banner", width: 1920, height: 800 },
  { label: "Full Width Image", width: 1600, height: 900 },
  { label: "Blog Featured Image", width: 1200, height: 630 },
  { label: "Standard Content Image", width: 900, height: 600 },
  { label: "Small Content Image", width: 600, height: 400 },
  { label: "Square Thumbnail", width: 600, height: 600 },
  { label: "Product Image", width: 1000, height: 1000 },
  { label: "Icon / Small Graphic", width: 300, height: 300 },
];

const DEFAULT_SETTINGS: ImageCompressionSettings = {
  mode: "lossy",
  quality: 80,
  resize_mode: "exact",
  output_format: "webp",
  custom_max_width: null,
  target_width: 600,
  target_height: 400,
  prevent_upscaling: true,
  crop_focus_x: 0.5,
  crop_focus_y: 0.5,
  pad_color: "#ffffff",
  strip_metadata: true,
  filename_overrides: {},
  crop_boxes: {},
  crop_subjects: {},
  crop_reasons: {},
  crop_confidences: {},
};

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function isImageFile(file: File) {
  return [".jpg", ".jpeg", ".png", ".webp", ".zip"].some((extension) =>
    file.name.toLowerCase().endsWith(extension),
  );
}

export function ImageResizerPanel() {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [lastJob, setLastJob] = useState<ImageJobCreateResponse | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [clientError, setClientError] = useState("");
  const [settings, setSettings] = useState<ImageCompressionSettings>(DEFAULT_SETTINGS);
  const [activeTab, setActiveTab] = useState<ResizeTab>("preset");
  const [instruction, setInstruction] = useState("");
  const [instructionNotes, setInstructionNotes] = useState<string[]>([]);
  const [instructionWarnings, setInstructionWarnings] = useState<string[]>([]);
  const [cropReview, setCropReview] = useState<CropReviewResponse | null>(null);
  const [cropModalOpen, setCropModalOpen] = useState(false);
  const [result, setResult] = useState<ImageCompressionResponse | null>(null);
  const [selectedResult, setSelectedResult] = useState<ImageCompressionResult | null>(null);

  const totalSize = useMemo(
    () => selectedFiles.reduce((total, file) => total + file.size, 0),
    [selectedFiles],
  );

  const uploadMutation = useMutation({
    mutationFn: async (files: File[]) => {
      setUploadProgress(0);
      return uploadImageJob(files, setUploadProgress);
    },
    onSuccess: (job) => {
      setLastJob(job);
      setActiveImageJobId(job.id);
      setResult(null);
      setSelectedResult(null);
      setCropReview(null);
      setUploadProgress(100);
    },
  });

  const instructionMutation = useMutation({
    mutationFn: async () => {
      if (!lastJob) throw new Error("Upload images before parsing instructions.");
      return parseResizeInstructions(lastJob.id, instruction);
    },
    onSuccess: async (response) => {
      const nextSettings = { ...settings, ...response.settings };
      setSettings(nextSettings);
      setInstructionNotes(response.notes);
      setInstructionWarnings(response.warnings ?? []);
      if (response.settings.resize_mode === "fit_inside") setActiveTab("custom");
      if (response.settings.resize_mode === "exact" && lastJob) {
        const review = await reviewImageCrops(lastJob.id, nextSettings);
        setCropReview(review);
        setCropModalOpen(true);
      }
    },
  });

  const cropReviewMutation = useMutation({
    mutationFn: async () => {
      if (!lastJob) throw new Error("Upload images before reviewing crops.");
      return reviewImageCrops(lastJob.id, settings);
    },
    onSuccess: (response) => {
      setCropReview(response);
      if (response.items.some((item) => item.needs_review)) {
        setCropModalOpen(true);
      } else {
        processMutation.mutate();
      }
    },
  });

  const processMutation = useMutation({
    mutationFn: async () => {
      if (!lastJob) throw new Error("Upload images before resizing.");
      return processImageJob(lastJob.id, settings);
    },
    onSuccess: (response) => {
      setResult(response);
      setCropModalOpen(false);
    },
  });

  const dropzone = useDropzone({
    accept: ACCEPTED_MIME_TYPES,
    multiple: true,
    onDrop: (files) => {
      setClientError("");
      setLastJob(null);
      setResult(null);
      setSelectedResult(null);
      setCropReview(null);
      setInstructionWarnings([]);
      setInstructionNotes([]);
      uploadMutation.reset();
      instructionMutation.reset();
      processMutation.reset();
      cropReviewMutation.reset();

      const unsupported = files.find((file) => !isImageFile(file));
      if (unsupported) {
        setSelectedFiles([]);
        setClientError(`${unsupported.name} is not a supported image or ZIP file.`);
        return;
      }

      setSelectedFiles(files);
    },
    onDropRejected: (rejections) => {
      const first = rejections[0];
      setClientError(first ? `${first.file.name} is not a supported image or ZIP file.` : "Upload rejected.");
    },
  });

  const targetLabel =
    settings.target_width && settings.target_height
      ? `${settings.target_width} x ${settings.target_height}`
      : "No target";
  const reviewCount = cropReview?.items.filter((item) => item.needs_review).length ?? 0;
  const busy = uploadMutation.isPending || cropReviewMutation.isPending || processMutation.isPending;

  const applyPreset = (width: number, height: number) => {
    setActiveTab("preset");
    setSettings((current) => ({
      ...current,
      resize_mode: "exact",
      target_width: width,
      target_height: height,
    }));
  };

  const setCropFocus = (focusX: number, focusY: number) => {
    setSettings((current) => ({ ...current, crop_focus_x: focusX, crop_focus_y: focusY }));
  };

  const setManualCropFocus = (imageId: string, focusX: number, focusY: number) => {
    setSettings((current) => {
      const { [imageId]: _cropBox, ...cropBoxes } = current.crop_boxes;
      const { [imageId]: _subject, ...cropSubjects } = current.crop_subjects;
      const { [imageId]: _reason, ...cropReasons } = current.crop_reasons;
      const { [imageId]: _confidence, ...cropConfidences } = current.crop_confidences;
      return {
        ...current,
        crop_focus_x: focusX,
        crop_focus_y: focusY,
        crop_boxes: cropBoxes,
        crop_subjects: cropSubjects,
        crop_reasons: cropReasons,
        crop_confidences: cropConfidences,
      };
    });
    setCropReview((current) => {
      if (!current) return current;
      return {
        ...current,
        items: current.items.map((item) =>
          item.id === imageId
            ? {
                ...item,
                focus_x: focusX,
                focus_y: focusY,
                source: "center",
                crop_box: null,
                subject: "",
                reason: "",
                confidence: 0.5,
              }
            : item,
        ),
      };
    });
  };

  const runReviewOrProcess = () => {
    if (settings.resize_mode === "exact") {
      cropReviewMutation.mutate();
      return;
    }
    processMutation.mutate();
  };

  return (
    <>
      <section className="space-y-6">
          <div className="rounded-lg border border-[#dfe3e8] bg-white">
            <div className="border-b border-[#dfe3e8] px-5 py-4">
              <h2 className="text-base font-semibold">1. Upload Images</h2>
              <p className="mt-1 text-sm text-[#667085]">
                Upload direct images or ZIP archives before choosing resize settings.
              </p>
            </div>
            <div className="space-y-5 p-5">
              <div
                {...dropzone.getRootProps()}
                className={`flex min-h-64 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed px-5 py-10 text-center transition ${
                  dropzone.isDragActive
                    ? "border-[#1d4ed8] bg-[#edf4ff]"
                    : "border-[#b8c0cc] bg-[#fafbfc] hover:border-[#1d4ed8]"
                }`}
              >
                <input {...dropzone.getInputProps()} />
                <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-white text-[#1d4ed8] shadow-sm">
                  <Upload aria-hidden="true" size={21} />
                </div>
                <p className="mt-4 text-sm font-medium text-[#151923]">Drop files here or click to browse</p>
                <p className="mt-2 max-w-sm text-sm text-[#667085]">JPG, PNG, WebP, and ZIP files.</p>
              </div>

              <div className="rounded-lg border border-[#dfe3e8]">
                <div className="border-b border-[#dfe3e8] px-4 py-3">
                  <p className="text-sm font-medium">Selected Files</p>
                  <p className="mt-0.5 text-xs text-[#667085]">
                    {selectedFiles.length} file{selectedFiles.length === 1 ? "" : "s"} · {formatBytes(totalSize)}
                  </p>
                </div>
                <div className="max-h-52 overflow-auto">
                  {selectedFiles.length === 0 ? (
                    <p className="px-4 py-10 text-center text-sm text-[#667085]">No files selected.</p>
                  ) : (
                    <ul className="divide-y divide-[#edf0f2]">
                      {selectedFiles.map((file) => (
                        <li key={`${file.name}-${file.size}`} className="flex items-center gap-3 px-4 py-3">
                          <ImageIcon aria-hidden="true" className="shrink-0 text-[#475467]" size={18} />
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium text-[#151923]">{file.name}</p>
                            <p className="text-xs text-[#667085]">{formatBytes(file.size)}</p>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </div>
            <div className="flex items-center justify-between gap-4 border-t border-[#dfe3e8] px-5 py-4">
              <div className="min-w-0">
                {clientError || uploadMutation.isError ? (
                  <p className="flex items-center gap-2 text-sm text-[#b42318]">
                    <AlertCircle aria-hidden="true" size={16} />
                    {clientError || getApiErrorMessage(uploadMutation.error)}
                  </p>
                ) : lastJob ? (
                  <p className="flex items-center gap-2 text-sm text-[#20744a]">
                    <CheckCircle2 aria-hidden="true" size={16} />
                    Job ready: {lastJob.id}
                  </p>
                ) : (
                  <p className="text-sm text-[#667085]">Upload at least one image to enable resize.</p>
                )}
              </div>
              <button
                type="button"
                disabled={selectedFiles.length === 0 || uploadMutation.isPending}
                onClick={() => uploadMutation.mutate(selectedFiles)}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-[#1d4ed8] px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-[#98a2b3]"
              >
                {uploadMutation.isPending ? <Loader2 className="animate-spin" size={16} /> : <Upload size={16} />}
                Upload images
              </button>
            </div>
          </div>

          <div className="rounded-lg border border-[#dfe3e8] bg-white p-5">
            <div className="mb-4">
              <h2 className="text-base font-semibold">2. Resize Method</h2>
            </div>
            <div className="grid rounded-lg bg-[#f2f0eb] p-1 text-sm font-medium sm:grid-cols-4">
              {[
                ["preset", "Preset"],
                ["custom", "Custom"],
                ["instructions", "AI Instructions"],
                ["convert", "Convert only"],
              ].map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => {
                    setActiveTab(key as ResizeTab);
                    if (key === "convert") {
                      setSettings((current) => ({ ...current, resize_mode: "none" }));
                    }
                  }}
                  className={`h-10 rounded-md transition ${
                    activeTab === key ? "bg-white text-[#151923] shadow-sm" : "text-[#475467] hover:text-[#151923]"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {activeTab === "preset" ? (
              <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {RESIZE_PRESETS.map((preset) => {
                  const selected =
                    settings.resize_mode === "exact" &&
                    settings.target_width === preset.width &&
                    settings.target_height === preset.height;
                  return (
                    <button
                      key={preset.label}
                      type="button"
                      onClick={() => applyPreset(preset.width, preset.height)}
                      className={`rounded-lg border p-4 text-left transition ${
                        selected
                          ? "border-[#173f3f] bg-[#f7faf9]"
                          : "border-[#dfe3e8] bg-white hover:border-[#b8c0cc]"
                      }`}
                    >
                      <p className="font-medium text-[#151923]">{preset.label}</p>
                      <p className="mt-1 text-sm text-[#667085]">
                        {preset.width} x {preset.height}
                      </p>
                    </button>
                  );
                })}
              </div>
            ) : null}

            {activeTab === "custom" ? (
              <div className="mt-5 grid gap-5 lg:grid-cols-2">
                <label className="space-y-2">
                  <span className="text-sm font-medium">Width (px)</span>
                  <input
                    type="number"
                    min="1"
                    value={settings.target_width ?? 600}
                    onChange={(event) =>
                      setSettings((current) => ({
                        ...current,
                        resize_mode: current.resize_mode === "none" ? "exact" : current.resize_mode,
                        target_width: Number(event.target.value),
                      }))
                    }
                    className="h-10 w-full rounded-md border border-[#dfe3e8] px-3 text-sm"
                  />
                </label>
                <label className="space-y-2">
                  <span className="text-sm font-medium">Height (px)</span>
                  <input
                    type="number"
                    min="1"
                    value={settings.target_height ?? 400}
                    onChange={(event) =>
                      setSettings((current) => ({
                        ...current,
                        resize_mode: current.resize_mode === "none" ? "exact" : current.resize_mode,
                        target_height: Number(event.target.value),
                      }))
                    }
                    className="h-10 w-full rounded-md border border-[#dfe3e8] px-3 text-sm"
                  />
                </label>
                <label className="flex items-center justify-between gap-4 text-sm font-medium lg:col-span-2">
                  Crop to exact size
                  <input
                    type="checkbox"
                    checked={settings.resize_mode === "exact"}
                    onChange={(event) =>
                      setSettings((current) => ({
                        ...current,
                        resize_mode: event.target.checked ? "exact" : "fit_inside",
                      }))
                    }
                    className="h-5 w-5 accent-[#173f3f]"
                  />
                </label>
                <label className="flex items-center justify-between gap-4 text-sm font-medium lg:col-span-2">
                  Fit inside dimensions
                  <input
                    type="checkbox"
                    checked={settings.resize_mode === "fit_inside"}
                    onChange={(event) =>
                      setSettings((current) => ({
                        ...current,
                        resize_mode: event.target.checked ? "fit_inside" : "exact",
                      }))
                    }
                    className="h-5 w-5 accent-[#173f3f]"
                  />
                </label>
                <label className="flex items-center justify-between gap-4 text-sm font-medium lg:col-span-2">
                  Prevent upscaling
                  <input
                    type="checkbox"
                    checked={settings.prevent_upscaling}
                    onChange={(event) =>
                      setSettings((current) => ({ ...current, prevent_upscaling: event.target.checked }))
                    }
                    className="h-5 w-5 accent-[#173f3f]"
                  />
                </label>
              </div>
            ) : null}

            {activeTab === "instructions" ? (
              <div className="mt-5 space-y-4">
                <textarea
                  value={instruction}
                  onChange={(event) => setInstruction(event.target.value)}
                  rows={4}
                  placeholder="Resize the 10 large JPG photos over 2000px wide into 600 x 400 WEBP files for website content sections."
                  className="w-full rounded-lg border border-[#dfe3e8] px-3 py-2 text-sm"
                />
                <button
                  type="button"
                  disabled={!lastJob || instruction.trim().length === 0 || instructionMutation.isPending}
                  onClick={() => instructionMutation.mutate()}
                  className="inline-flex h-10 items-center gap-2 rounded-md border border-[#dfe3e8] px-4 text-sm font-medium text-[#475467] hover:bg-[#edf4ff] hover:text-[#1d4ed8] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {instructionMutation.isPending ? <Loader2 className="animate-spin" size={16} /> : <Sparkles size={16} />}
                  Interpret instructions
                </button>
                {instructionMutation.isError ? (
                  <div className="flex items-start gap-2 rounded-md border border-[#f2b8b5] bg-[#fff5f5] p-3 text-sm text-[#b42318]">
                    <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={16} />
                    <span>{getApiErrorMessage(instructionMutation.error)}</span>
                  </div>
                ) : null}
                {instructionWarnings.length > 0 ? (
                  <div className="flex items-start gap-2 rounded-md border border-[#f2b8b5] bg-[#fff5f5] p-3 text-sm text-[#b42318]">
                    <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={16} />
                    <div>
                      <p className="font-medium">AI crop targeting could not be applied.</p>
                      {instructionWarnings.map((warning) => (
                        <p key={warning} className="mt-1">{warning}</p>
                      ))}
                      <p className="mt-1">Use crop review to adjust the crop manually before resizing.</p>
                    </div>
                  </div>
                ) : null}
                {instructionNotes.length > 0 ? (
                  <div className="rounded-lg border border-[#dfe3e8] bg-[#fafbfc] p-3 text-sm text-[#475467]">
                    {instructionNotes.map((note) => (
                      <p key={note}>{note}</p>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}

            <div className="mt-5 grid gap-4 border-t border-[#edf0f2] pt-5 md:grid-cols-3">
              <label className="space-y-2">
                <span className="text-sm font-medium">Output format</span>
                <select
                  value={settings.output_format}
                  onChange={(event) =>
                    setSettings((current) => ({
                      ...current,
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
              <label className="space-y-2">
                <span className="text-sm font-medium">Quality</span>
                <input
                  type="range"
                  min="60"
                  max="90"
                  step="10"
                  value={settings.quality}
                  onChange={(event) => setSettings((current) => ({ ...current, quality: Number(event.target.value) }))}
                  className="mt-3 w-full accent-[#1d4ed8]"
                />
              </label>
              <div className="rounded-lg border border-[#dfe3e8] bg-[#fafbfc] p-3">
                <p className="text-xs uppercase text-[#667085]">Current target</p>
                <p className="mt-1 font-semibold text-[#151923]">{activeTab === "convert" ? "Convert only" : targetLabel}</p>
              </div>
            </div>
          </div>

          <div className="grid gap-5 lg:grid-cols-[1fr_0.85fr]">
            <div className="rounded-lg border border-[#f9d7a8] bg-[#fff8ed] p-5">
              <div className="flex items-start gap-3">
                <Crop aria-hidden="true" className="mt-0.5 text-[#b45309]" size={18} />
                <div>
                  <p className="font-semibold text-[#151923]">
                    {reviewCount > 0 ? `${reviewCount} image${reviewCount === 1 ? "" : "s"} need crop review` : "Crop review ready"}
                  </p>
                  <p className="mt-2 text-sm leading-6 text-[#667085]">
                    Exact-size crops are reviewed before processing. Use fit-inside if you want to keep the whole image.
                  </p>
                </div>
              </div>

              {cropReviewMutation.isError || processMutation.isError ? (
                <div className="mt-4 flex items-start gap-2 rounded-md border border-[#f2b8b5] bg-white p-3 text-sm text-[#b42318]">
                  <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={16} />
                  <span>
                    {getApiErrorMessage(cropReviewMutation.error ?? processMutation.error)}
                  </span>
                </div>
              ) : null}

              <div className="mt-4 flex justify-end">
                <button
                  type="button"
                  disabled={!lastJob || busy}
                  onClick={runReviewOrProcess}
                  className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-[#173f3f] px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-[#98a2b3] sm:w-auto"
                >
                  {busy ? <Loader2 className="animate-spin" size={16} /> : <Crop size={16} />}
                  Review crops & resize
                </button>
              </div>
            </div>

            <div className="rounded-lg border border-[#dfe3e8] bg-white p-5">
              <p className="text-sm font-semibold">Example use case</p>
              <p className="mt-2 text-sm leading-6 text-[#667085]">
                Upload 10 large JPG photos over 2000px wide and resize them into 600 x 400 WEBP files for website content sections.
              </p>
            </div>
          </div>
      </section>

      {result ? (
        <section className="rounded-lg border border-[#dfe3e8] bg-white">
          <div className="flex items-center justify-between gap-4 border-b border-[#dfe3e8] px-5 py-4">
            <h2 className="text-base font-semibold">Resize Results</h2>
            <a
              href={getProcessedImagesZipDownloadUrl(result.job_id)}
              download={`${result.job_id}-resized-images.zip`}
              className="inline-flex h-9 items-center gap-2 rounded-md border border-[#dfe3e8] px-3 text-sm font-medium text-[#475467] hover:bg-[#edf4ff] hover:text-[#1d4ed8]"
            >
              <FileArchive aria-hidden="true" size={16} />
              Download ZIP
            </a>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-left text-sm">
              <thead className="bg-[#fafbfc] text-[#667085]">
                <tr>
                  <th className="px-5 py-3 font-medium">File</th>
                  <th className="px-5 py-3 font-medium">Format</th>
                  <th className="px-5 py-3 font-medium">Dimensions</th>
                  <th className="px-5 py-3 font-medium">Size</th>
                  <th className="w-32 px-5 py-3 text-center font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#edf0f2]">
                {result.results.map((item) => (
                  <tr key={item.id}>
                    <td className="px-5 py-3 font-medium text-[#151923]">{item.processed_filename}</td>
                    <td className="px-5 py-3 text-[#475467]">
                      {item.original_format.toUpperCase()} {"->"} {item.new_format.toUpperCase()}
                    </td>
                    <td className="px-5 py-3 text-[#475467]">
                      {item.width} x {item.height}
                    </td>
                    <td className="px-5 py-3 text-[#475467]">{formatBytes(item.processed_size_bytes)}</td>
                    <td className="px-5 py-3 text-center">
                      <div className="mx-auto flex items-center justify-center gap-2">
                        <button
                          type="button"
                          onClick={() => setSelectedResult(item)}
                          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-[#475467] hover:bg-[#edf4ff] hover:text-[#1d4ed8]"
                          aria-label={`Preview ${item.processed_filename}`}
                          title={`Preview ${item.processed_filename}`}
                        >
                          <Eye aria-hidden="true" size={16} />
                        </button>
                        <a
                          href={getProcessedImageDownloadUrl(result.job_id, item.processed_filename)}
                          download={item.processed_filename}
                          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-[#475467] hover:bg-[#edf4ff] hover:text-[#1d4ed8]"
                          aria-label={`Download ${item.processed_filename}`}
                          title={`Download ${item.processed_filename}`}
                        >
                          <Download aria-hidden="true" size={16} />
                        </a>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {selectedResult && result ? (
        <ResizeResultDrawer
          jobId={result.job_id}
          result={selectedResult}
          onClose={() => setSelectedResult(null)}
        />
      ) : null}

      {cropModalOpen && cropReview && lastJob ? (
        <CropReviewModal
          cropReview={cropReview}
          jobId={lastJob.id}
          focusX={settings.crop_focus_x}
          focusY={settings.crop_focus_y}
          onFocusChange={setManualCropFocus}
          onClose={() => setCropModalOpen(false)}
          onApply={() => processMutation.mutate()}
          isProcessing={processMutation.isPending}
        />
      ) : null}
    </>
  );
}

function ResizeResultDrawer({
  jobId,
  result,
  onClose,
}: {
  jobId: string;
  result: ImageCompressionResult;
  onClose: () => void;
}) {
  const previewUrl = getProcessedImageDownloadUrl(jobId, result.processed_filename);

  return (
    <div className="fixed inset-0 z-50">
      <button
        type="button"
        className="absolute inset-0 cursor-default bg-[#151923]/35"
        aria-label="Close resize preview"
        onClick={onClose}
      />
      <aside className="absolute right-0 top-0 flex h-full w-full max-w-xl flex-col bg-white shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-[#dfe3e8] px-5 py-4">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-[#151923]">Resize Preview</h2>
            <p className="mt-1 truncate text-sm text-[#667085]" title={result.processed_filename}>
              {result.processed_filename}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-[#475467] hover:bg-[#f2f4f7]"
            aria-label="Close resize preview"
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
                src={previewUrl}
                alt={`Preview of ${result.processed_filename}`}
                className="h-full w-full object-contain"
              />
            </div>
            <div className="border-t border-[#dfe3e8] px-4 py-3">
              <p className="truncate text-sm font-medium text-[#151923]" title={result.original_filename}>
                {result.original_filename}
              </p>
              <p className="mt-1 text-xs text-[#667085]">
                Processed output preview.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 rounded-lg border border-[#dfe3e8] bg-[#fafbfc] p-4 text-sm">
            <div>
              <p className="text-xs font-medium uppercase text-[#667085]">Original filename</p>
              <p className="mt-1 break-all text-[#151923]">{result.original_filename}</p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-[#667085]">Processed filename</p>
              <p className="mt-1 break-all text-[#151923]">{result.processed_filename}</p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-[#667085]">Format</p>
              <p className="mt-1 text-[#151923]">
                {result.original_format.toUpperCase()} {"->"} {result.new_format.toUpperCase()}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-[#667085]">Dimensions</p>
              <p className="mt-1 text-[#151923]">
                {result.width} x {result.height}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-[#667085]">Original size</p>
              <p className="mt-1 text-[#151923]">{formatBytes(result.original_size_bytes)}</p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-[#667085]">Processed size</p>
              <p className="mt-1 text-[#151923]">{formatBytes(result.processed_size_bytes)}</p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-[#667085]">Savings</p>
              <p className="mt-1 text-[#151923]">{result.reduction_percent}%</p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-[#667085]">Status</p>
              <p className="mt-1 text-[#151923]">{result.status}</p>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-[#dfe3e8] px-5 py-4">
          <a
            href={previewUrl}
            download={result.processed_filename}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-[#dfe3e8] px-4 text-sm font-medium text-[#475467] hover:bg-[#edf4ff] hover:text-[#1d4ed8]"
          >
            <Download aria-hidden="true" size={16} />
            Download
          </a>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-10 items-center justify-center rounded-md bg-[#1d4ed8] px-4 text-sm font-medium text-white"
          >
            Done
          </button>
        </div>
      </aside>
    </div>
  );
}

function CropReviewModal({
  cropReview,
  jobId,
  focusX,
  focusY,
  onFocusChange,
  onClose,
  onApply,
  isProcessing,
}: {
  cropReview: CropReviewResponse;
  jobId: string;
  focusX: number;
  focusY: number;
  onFocusChange: (imageId: string, focusX: number, focusY: number) => void;
  onClose: () => void;
  onApply: () => void;
  isProcessing: boolean;
}) {
  const item = cropReview.items.find((reviewItem) => reviewItem.needs_review) ?? cropReview.items[0];
  const previewUrl = getMetadataImageDownloadUrl(jobId, item.id);
  const activeFocusX = item.focus_x ?? focusX;
  const activeFocusY = item.focus_y ?? focusY;
  const objectPosition = `${Math.round(activeFocusX * 100)}% ${Math.round(activeFocusY * 100)}%`;
  const updateFocus = (nextFocusX: number, nextFocusY: number) => {
    onFocusChange(item.id, nextFocusX, nextFocusY);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#151923]/55 p-4">
      <div className="w-full max-w-5xl rounded-lg bg-white shadow-2xl">
        <div className="flex items-start justify-between gap-4 px-5 py-4">
          <div>
            <h2 className="text-base font-semibold">Crop review - Image 1 of {cropReview.items.length}</h2>
            <p className="mt-1 text-sm text-[#667085]">
              {item.original_filename} · original {item.width} x {item.height} · target {item.target_width} x {item.target_height}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-[#475467] hover:bg-[#f2f4f7]"
            aria-label="Close crop review"
            title="Close"
          >
            <X aria-hidden="true" size={16} />
          </button>
        </div>

        <div className="grid gap-5 px-5 pb-5 lg:grid-cols-[1fr_280px]">
          <div
            className="relative overflow-hidden rounded-lg border border-[#dfe3e8] bg-[#151923]"
            style={{ aspectRatio: `${item.target_width} / ${item.target_height}` }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={previewUrl}
              alt=""
              className="h-full w-full object-cover"
              style={{ objectPosition }}
            />
            <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.32)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.32)_1px,transparent_1px)] bg-[size:33.333%_33.333%]" />
          </div>

          <div className="space-y-4">
            <div>
              <p className="text-xs font-semibold uppercase text-[#667085]">Crop position preset</p>
              <select
                value={`${activeFocusX}-${activeFocusY}`}
                onChange={(event) => {
                  const [nextX, nextY] = event.target.value.split("-").map(Number);
                  updateFocus(nextX, nextY);
                }}
                className="mt-2 h-10 w-full rounded-md border border-[#dfe3e8] bg-white px-3 text-sm"
              >
                <option value="0.5-0.5">Center</option>
                <option value="0.5-0">Top</option>
                <option value="0.5-1">Bottom</option>
                <option value="0-0.5">Left</option>
                <option value="1-0.5">Right</option>
                <option value="0-0">Top left</option>
                <option value="1-1">Bottom right</option>
              </select>
              <p className="mt-3 text-xs leading-5 text-[#667085]">
                Use presets to shift the crop toward the image focal point before processing.
              </p>
              {item.source === "ai" ? (
                <div className="mt-3 rounded-md border border-[#dfe3e8] bg-[#fafbfc] p-3 text-xs leading-5 text-[#667085]">
                  <p className="font-semibold uppercase text-[#475467]">AI crop target</p>
                  <p className="mt-1 text-[#151923]">{item.subject || "Requested subject"}</p>
                  {item.reason ? <p className="mt-1">{item.reason}</p> : null}
                  <p className="mt-1">Confidence: {Math.round(item.confidence * 100)}%</p>
                </div>
              ) : null}
            </div>

            <div className="space-y-3 rounded-md border border-[#dfe3e8] p-3">
              <div>
                <div className="flex items-center justify-between text-xs font-medium text-[#667085]">
                  <span>Horizontal focus</span>
                  <span>{Math.round(activeFocusX * 100)}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.01"
                  value={activeFocusX}
                  onChange={(event) => updateFocus(Number(event.target.value), activeFocusY)}
                  className="mt-2 w-full accent-[#173f3f]"
                />
              </div>
              <div>
                <div className="flex items-center justify-between text-xs font-medium text-[#667085]">
                  <span>Vertical focus</span>
                  <span>{Math.round(activeFocusY * 100)}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.01"
                  value={activeFocusY}
                  onChange={(event) => updateFocus(activeFocusX, Number(event.target.value))}
                  className="mt-2 w-full accent-[#173f3f]"
                />
              </div>
              <p className="text-xs leading-5 text-[#667085]">
                Moving these sliders switches this image to manual crop control.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => updateFocus(0.5, 0.5)}
                className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-[#dfe3e8] px-3 text-sm font-medium text-[#475467] hover:bg-[#f2f4f7]"
              >
                <RotateCcw aria-hidden="true" size={15} />
                Reset
              </button>
              <button
                type="button"
                onClick={onClose}
                className="inline-flex h-9 items-center justify-center rounded-md border border-[#dfe3e8] px-3 text-sm font-medium text-[#475467] hover:bg-[#f2f4f7]"
              >
                Skip review
              </button>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-[#dfe3e8] px-5 py-4">
          <button
            type="button"
            onClick={() => updateFocus(0.5, 0.5)}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-[#dfe3e8] px-4 text-sm font-medium text-[#475467] hover:bg-[#f2f4f7]"
          >
            <Maximize2 aria-hidden="true" size={16} />
            Reset to center
          </button>
          <button
            type="button"
            disabled={isProcessing}
            onClick={onApply}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-[#173f3f] px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-[#98a2b3]"
          >
            {isProcessing ? <Loader2 className="animate-spin" size={16} /> : <Crop size={16} />}
            Apply crop
          </button>
        </div>
      </div>
    </div>
  );
}
