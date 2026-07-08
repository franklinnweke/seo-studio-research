"use client";

import { AppShell } from "@/components/app-shell";
import { WorkflowDashboard } from "@/components/workflow-dashboard";

export default function Home() {
  return (
    <AppShell
      active="dashboard"
      title="Dashboard"
      subtitle="Complete image optimization workflow — upload, optimize, generate metadata, resize, and export."
    >
      <WorkflowDashboard />
    </AppShell>
  );
}
