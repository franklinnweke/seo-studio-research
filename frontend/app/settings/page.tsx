import { Settings } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { UpcomingFeaturePanel } from "@/components/upcoming-feature-panel";

export default function SettingsPage() {
  return (
    <AppShell
      active="settings"
      title="Settings"
      subtitle="Configure AI models, image defaults, crawler limits, and cleanup behavior."
      sidebarPhase="Phase 7 planned"
      sidebarDescription="Runtime settings are currently configured through local environment variables."
    >
      <UpcomingFeaturePanel
        icon={Settings}
        title="Settings"
        description="This page will expose safe runtime defaults for local AI, image processing, crawler behavior, and temporary file cleanup."
        nextMilestone="POC hardening adds configurable model names, Ollama endpoint visibility, cleanup defaults, and clearer failure states."
        plannedItems={[
          "Ollama endpoint, vision model, language model, and timeout defaults.",
          "Default image quality, output format, resize behavior, and max batch size.",
          "Crawler defaults for max pages, depth, timeout, include paths, and exclude paths.",
          "Temporary file cleanup controls and storage usage visibility.",
        ]}
      />
    </AppShell>
  );
}
