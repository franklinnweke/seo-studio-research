import { Archive } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { UpcomingFeaturePanel } from "@/components/upcoming-feature-panel";

export default function ExportsPage() {
  return (
    <AppShell
      active="exports"
      title="Exports"
      subtitle="Review and download generated image, metadata, and website reports."
      sidebarPhase="Phase 7 planned"
      sidebarDescription="ZIP downloads are available in active workflows; export history is planned."
    >
      <UpcomingFeaturePanel
        icon={Archive}
        title="Exports"
        description="This page will centralize generated files across image optimization, metadata generation, and website audits."
        nextMilestone="Milestone 3 expands CSV, JSON, XLSX, and ZIP exports after review workflows are complete."
        plannedItems={[
          "Export history grouped by source job and workflow type.",
          "Download links for ZIP, CSV, JSON, and XLSX reports.",
          "File size, created date, job status, and export format metadata.",
          "Quick access to regenerate or refresh exports from the active workspace job.",
        ]}
      />
    </AppShell>
  );
}
