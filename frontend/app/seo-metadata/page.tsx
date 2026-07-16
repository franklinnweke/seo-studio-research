import { AppShell } from "@/components/app-shell";
import { SeoMetadataPanel } from "@/components/seo-metadata-panel";

export default function SeoMetadataPage() {
  return (
    <AppShell
      active="seo-metadata"
      title="Context-aware metadata"
      subtitle="Confirm page evidence and image purpose before generation."
      sidebarPhase="Research workflow active"
      sidebarDescription="Prepare context, compare direct and dual-stage generation, then review every output before export."
    >
      <SeoMetadataPanel />
    </AppShell>
  );
}
