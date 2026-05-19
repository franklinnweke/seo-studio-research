export type JobStatus = "pending" | "processing" | "needs_review" | "accepted" | "failed";

export type JobType = "image" | "website";

export type Job = {
  id: string;
  type: JobType;
  status: JobStatus;
  settings: Record<string, unknown>;
};
