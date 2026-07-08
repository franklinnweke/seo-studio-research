import { FileSearch } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { UpcomingFeaturePanel } from "@/components/upcoming-feature-panel";

export default function WebsiteCheckerPage() {
  return (
    <AppShell
      active="website-checker"
      title="Website Checker"
      subtitle="Crawl websites, inspect page content, and find broken links."
      sidebarPhase="Phase 9 planned"
      sidebarDescription="Website crawling and broken link checks are planned after the active image workflow."
    >
      <UpcomingFeaturePanel
        icon={FileSearch}
        title="Website Checker"
        description="This workflow will crawl same-domain pages, support Basic Auth, extract page content, and report broken links."
        nextMilestone="Milestone 4 introduces crawling and protected URL access. Milestone 5 adds broken link checking and exports."
        plannedItems={[
          "Website URL form with optional Basic Auth credentials.",
          "Same-domain crawl limits for max pages, max depth, include paths, and exclude paths.",
          "Crawled pages table with titles, headings, status codes, and extracted content.",
          "Broken link report with filters for redirects, timeouts, internal links, and external links.",
        ]}
      />
    </AppShell>
  );
}
