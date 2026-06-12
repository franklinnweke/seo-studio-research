"use client";

import { useSyncExternalStore } from "react";

const ACTIVE_IMAGE_JOB_KEY = "seo-studio.activeImageJobId";
const ACTIVE_IMAGE_JOB_EVENT = "seo-studio:active-image-job";

function readActiveImageJobId() {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(ACTIVE_IMAGE_JOB_KEY) ?? "";
}

function notifyActiveImageJobChange(jobId: string) {
  window.dispatchEvent(new CustomEvent(ACTIVE_IMAGE_JOB_EVENT, { detail: jobId }));
}

function subscribeActiveImageJobId(onStoreChange: () => void) {
  const handleStorage = (event: StorageEvent) => {
    if (event.key === ACTIVE_IMAGE_JOB_KEY) {
      onStoreChange();
    }
  };

  const handleCustomEvent = () => {
    onStoreChange();
  };

  window.addEventListener("storage", handleStorage);
  window.addEventListener(ACTIVE_IMAGE_JOB_EVENT, handleCustomEvent);
  return () => {
    window.removeEventListener("storage", handleStorage);
    window.removeEventListener(ACTIVE_IMAGE_JOB_EVENT, handleCustomEvent);
  };
}

export function setActiveImageJobId(jobId: string) {
  if (typeof window === "undefined") return;
  const nextJobId = jobId.trim();
  if (!nextJobId) return;
  window.localStorage.setItem(ACTIVE_IMAGE_JOB_KEY, nextJobId);
  notifyActiveImageJobChange(nextJobId);
}

export function clearActiveImageJobId() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ACTIVE_IMAGE_JOB_KEY);
  notifyActiveImageJobChange("");
}

export function useActiveImageJobId() {
  return useSyncExternalStore(subscribeActiveImageJobId, readActiveImageJobId, () => "");
}
