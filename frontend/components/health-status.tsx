"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

import { getHealth } from "@/lib/api";

export function HealthStatus() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
  });

  if (health.isLoading) {
    return (
      <div className="inline-flex h-9 items-center gap-2 rounded-md border border-[#dfe3e8] bg-white px-3 text-sm text-[#667085]">
        <Loader2 aria-hidden="true" className="animate-spin" size={16} />
        Checking API
      </div>
    );
  }

  if (health.isSuccess) {
    return (
      <div className="inline-flex h-9 items-center gap-2 rounded-md border border-[#b7dfc5] bg-[#f0f9f3] px-3 text-sm font-medium text-[#20744a]">
        <CheckCircle2 aria-hidden="true" size={16} />
        API online
      </div>
    );
  }

  return (
    <div className="inline-flex h-9 items-center gap-2 rounded-md border border-[#f2b8b5] bg-[#fff5f5] px-3 text-sm font-medium text-[#b42318]">
      <XCircle aria-hidden="true" size={16} />
      API offline
    </div>
  );
}
