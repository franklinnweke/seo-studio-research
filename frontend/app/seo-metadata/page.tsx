import { AppShell } from "@/components/app-shell";
import { SeoMetadataPanel } from "@/components/seo-metadata-panel";

export default function SeoMetadataPage() {
  return (
    <AppShell
      active="seo-metadata"
      title="SEO Metadata"
      subtitle="Generate and review AI-powered image metadata."
    >
      <SeoMetadataPanel />
    </AppShell>
  );
}
