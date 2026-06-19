import axios, { AxiosError, type AxiosProgressEvent } from "axios";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    Accept: "application/json",
  },
});

export type HealthResponse = {
  status: string;
  app: string;
};

export type SettingsResponse = {
  ai_provider: string;
  ollama_base_url: string;
  ollama_model: string;
  vision_model: string;
  language_model: string;
  ollama_timeout_seconds: number;
  ai_language_timeout_seconds: number;
  ai_crop_timeout_seconds: number;
  ai_preview_max_width: number;
  frontend_origin: string;
  storage_root: string;
};

export type ImageUploadFileRecord = {
  id: string;
  original_filename: string;
  stored_filename: string;
  relative_path: string;
  content_type: string;
  size_bytes: number;
  source: "upload" | "zip";
  source_archive: string | null;
};

export type ImageJobCreateResponse = {
  id: string;
  type: "image";
  status: "pending" | "processing" | "processed" | "needs_review" | "accepted" | "failed";
  accepted_extensions: string[];
  files: ImageUploadFileRecord[];
};

export type JobStatusResponse = {
  id: string;
  type: "image" | "website";
  status: "pending" | "processing" | "processed" | "needs_review" | "accepted" | "failed";
  file_count: number;
};

export type JobFileListResponse = {
  job_id: string;
  files: ImageUploadFileRecord[];
};

export type BrandContextDocument = {
  id: string;
  original_filename: string;
  stored_filename: string;
  content_type: string;
  size_bytes: number;
  extracted_chars: number;
};

export type BrandContextResponse = {
  job_id: string;
  documents: BrandContextDocument[];
  combined_text: string;
  max_chars: number;
};

export type ImageCompressionSettings = {
  mode: "lossy" | "lossless";
  quality: number;
  resize_mode: "none" | "max_1920" | "max_1200" | "custom" | "exact" | "fit_inside";
  output_format: "keep_original" | "webp" | "jpg" | "png";
  custom_max_width: number | null;
  target_width: number | null;
  target_height: number | null;
  prevent_upscaling: boolean;
  crop_focus_x: number;
  crop_focus_y: number;
  pad_color: string;
  strip_metadata: boolean;
  filename_overrides: Record<string, string>;
  crop_boxes: Record<string, CropBox>;
  crop_subjects: Record<string, string>;
  crop_reasons: Record<string, string>;
  crop_confidences: Record<string, number>;
};

export type CropBox = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type ImageCompressionResult = {
  id: string;
  original_filename: string;
  stored_filename: string;
  processed_filename: string;
  relative_path: string;
  original_format: string;
  new_format: string;
  original_size_bytes: number;
  processed_size_bytes: number;
  reduction_percent: number;
  width: number;
  height: number;
  status: "processed";
};

export type ImageCompressionResponse = {
  job_id: string;
  status: "processed";
  settings: ImageCompressionSettings;
  results: ImageCompressionResult[];
};

export type ResizeInstructionResponse = {
  instruction: string;
  settings: ImageCompressionSettings;
  notes: string[];
  warnings: string[];
};

export type CropReviewItem = {
  id: string;
  original_filename: string;
  width: number;
  height: number;
  target_width: number;
  target_height: number;
  needs_review: boolean;
  focus_x: number;
  focus_y: number;
  confidence: number;
  source: "center" | "preset" | "ai";
  crop_box: CropBox | null;
  subject: string;
  reason: string;
};

export type CropReviewResponse = {
  job_id: string;
  target_width: number;
  target_height: number;
  items: CropReviewItem[];
};

export type ImageMetadataResult = {
  id: string;
  original_filename: string;
  suggested_filename: string;
  alt_text: string;
  caption: string;
  confidence: number;
  status: "needs_review" | "failed";
  error_message: string;
};

export type ImageMetadataListResponse = {
  job_id: string;
  provider: string;
  model: string;
  vision_model: string;
  language_model: string;
  results: ImageMetadataResult[];
};

export async function getHealth(): Promise<HealthResponse> {
  const response = await apiClient.get<HealthResponse>("/health");
  return response.data;
}

export async function getSettings(): Promise<SettingsResponse> {
  const response = await apiClient.get<SettingsResponse>("/api/settings");
  return response.data;
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const response = await apiClient.get<JobStatusResponse>(`/api/jobs/${jobId}`);
  return response.data;
}

export async function uploadImageJob(
  files: File[],
  onUploadProgress?: (progress: number) => void,
): Promise<ImageJobCreateResponse> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }

  const response = await apiClient.post<ImageJobCreateResponse>("/api/jobs/images", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (event: AxiosProgressEvent) => {
      if (!event.total || !onUploadProgress) return;
      onUploadProgress(Math.round((event.loaded * 100) / event.total));
    },
  });

  return response.data;
}

export async function getJobFiles(jobId: string): Promise<JobFileListResponse> {
  const response = await apiClient.get<JobFileListResponse>(`/api/jobs/${jobId}/files`);
  return response.data;
}

export async function getBrandContext(jobId: string): Promise<BrandContextResponse> {
  const response = await apiClient.get<BrandContextResponse>(`/api/jobs/${jobId}/brand-context`);
  return response.data;
}

export async function uploadBrandContext(
  jobId: string,
  files: File[],
  onUploadProgress?: (progress: number) => void,
): Promise<BrandContextResponse> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }

  const response = await apiClient.post<BrandContextResponse>(
    `/api/jobs/${jobId}/brand-context`,
    formData,
    {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (event: AxiosProgressEvent) => {
        if (!event.total || !onUploadProgress) return;
        onUploadProgress(Math.round((event.loaded * 100) / event.total));
      },
    },
  );

  return response.data;
}

export async function processImageJob(
  jobId: string,
  settings: ImageCompressionSettings,
): Promise<ImageCompressionResponse> {
  const response = await apiClient.post<ImageCompressionResponse>(
    `/api/jobs/${jobId}/process`,
    settings,
  );
  return response.data;
}

export async function parseResizeInstructions(
  jobId: string,
  instruction: string,
): Promise<ResizeInstructionResponse> {
  const response = await apiClient.post<ResizeInstructionResponse>(
    `/api/jobs/${jobId}/resize-instructions`,
    { instruction },
  );
  return response.data;
}

export async function suggestAiCrop(
  jobId: string,
  instruction: string,
  settings: ImageCompressionSettings,
): Promise<ResizeInstructionResponse> {
  const response = await apiClient.post<ResizeInstructionResponse>(
    `/api/jobs/${jobId}/resize-ai-crop`,
    { instruction, settings },
    { timeout: 60000 },
  );
  return response.data;
}

export async function reviewImageCrops(
  jobId: string,
  settings: ImageCompressionSettings,
): Promise<CropReviewResponse> {
  const response = await apiClient.post<CropReviewResponse>(
    `/api/jobs/${jobId}/resize-review`,
    settings,
  );
  return response.data;
}

export function getProcessedImageDownloadUrl(jobId: string, filename: string): string {
  return `${API_BASE_URL}/api/jobs/${encodeURIComponent(jobId)}/processed/${encodeURIComponent(filename)}`;
}

export function getProcessedImagesZipDownloadUrl(jobId: string): string {
  return `${API_BASE_URL}/api/jobs/${encodeURIComponent(jobId)}/export.zip`;
}

export function getMetadataImageDownloadUrl(
  jobId: string,
  imageId: string,
  filename?: string,
): string {
  const url = new URL(
    `${API_BASE_URL}/api/jobs/${encodeURIComponent(jobId)}/images/${encodeURIComponent(imageId)}/download`,
  );
  if (filename?.trim()) {
    url.searchParams.set("filename", filename.trim());
  }
  return url.toString();
}

export function getImageMetadataCsvDownloadUrl(jobId: string, fields: string[]): string {
  const url = new URL(
    `${API_BASE_URL}/api/jobs/${encodeURIComponent(jobId)}/images/metadata.csv`,
  );
  for (const field of fields) {
    url.searchParams.append("fields", field);
  }
  return url.toString();
}

export function getImageMetadataZipDownloadUrl(jobId: string, imageIds: string[]): string {
  const url = new URL(
    `${API_BASE_URL}/api/jobs/${encodeURIComponent(jobId)}/images/metadata.zip`,
  );
  for (const imageId of imageIds) {
    url.searchParams.append("image_ids", imageId);
  }
  return url.toString();
}

export async function getImageMetadata(jobId: string): Promise<ImageMetadataListResponse> {
  const response = await apiClient.get<ImageMetadataListResponse>(
    `/api/jobs/${jobId}/images/metadata`,
  );
  return response.data;
}

export async function generateImageMetadata(jobId: string): Promise<ImageMetadataListResponse> {
  const response = await apiClient.post<ImageMetadataListResponse>(
    `/api/jobs/${jobId}/images/metadata`,
  );
  return response.data;
}

export async function regenerateImageMetadata(
  jobId: string,
  imageId: string,
): Promise<ImageMetadataResult> {
  const response = await apiClient.post<ImageMetadataResult>(
    `/api/jobs/${jobId}/images/${imageId}/metadata`,
  );
  return response.data;
}

export function getApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    return getAxiosErrorMessage(error);
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Something went wrong.";
}

function getAxiosErrorMessage(error: AxiosError): string {
  if (error.code === "ECONNABORTED") {
    return "The AI crop request timed out. Try manual crop review, reduce preview size, or use a faster vision model.";
  }

  const data = error.response?.data;

  if (typeof data === "object" && data !== null && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return "The request did not pass validation.";
  }

  if (error.response?.status) {
    return `Request failed with status ${error.response.status}.`;
  }

  return error.message;
}
