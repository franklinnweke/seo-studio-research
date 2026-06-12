import Link from "next/link";
import {
  Activity,
  Archive,
  Camera,
  FileSearch,
  ImageIcon,
  Link2,
  Maximize2,
  Search,
  Settings,
  Sparkles,
} from "lucide-react";

import { AppShell } from "@/components/app-shell";

const metrics = [
  { label: "Images processed", value: "0", detail: "Upload and compression are ready" },
  { label: "Average savings", value: "0%", detail: "Shown after image compression" },
  { label: "Broken links", value: "0", detail: "Crawler starts in Phase 11" },
  { label: "Metadata generated", value: "0", detail: "AI starts in Phase 5" },
];

const phases = [
  ["Phase 0", "Project setup", "Complete"],
  ["Phase 0.5", "Swagger and OpenAPI", "Complete"],
  ["Phase 1", "Image upload system", "Complete"],
  ["Phase 2", "Image compression", "Complete"],
  ["Phase 3", "Image conversion", "Complete"],
  ["Phase 4", "Filename cleanup", "Complete"],
  ["Phase 5", "AI image metadata", "Complete"],
  ["Phase 6", "Brand context documents", "Complete"],
  ["Phase 7", "Dual-model AI metadata", "Complete"],
  ["Phase 8", "AI focus-aware crop", "Active"],
  ["Phase 9", "Review UI", "Planned"],
  ["Phase 10", "Export system", "Planned"],
  ["Phase 11", "Website crawler", "Planned"],
  ["Phase 12", "Broken links and bulk URLs", "Planned"],
  ["Phase 13", "Website screenshots", "Planned"],
  ["Phase 14", "AI SEO metadata generator", "Planned"],
  ["Phase 15", "POC hardening", "Planned"],
  ["Phase 16", "Beta persistence", "Planned"],
];

const statusClassNames: Record<string, string> = {
  Complete: "bg-[#eef6f0] text-[#20744a]",
  Active: "bg-[#fff4e5] text-[#b45309]",
  Planned: "bg-[#f2f4f7] text-[#475467]",
};

const tools = [
  {
    title: "Image Optimizer",
    description: "Upload, compress, convert, rename, and download optimized image files.",
    icon: ImageIcon,
    href: "/image-optimizer",
    status: "Active",
  },
  {
    title: "SEO Metadata",
    description: "Generate filenames, alt text, captions, and downloadable SEO-ready images.",
    icon: Sparkles,
    href: "/seo-metadata",
    status: "Active",
  },
  {
    title: "Image Compressor",
    description: "Lossy and lossless compression controls for smaller production assets.",
    icon: Archive,
    href: null,
    status: "Coming soon",
  },
  {
    title: "AI Image Resizer",
    description: "Resize and crop around image focal points for fixed website dimensions.",
    icon: Maximize2,
    href: "/image-resizer",
    status: "Active",
  },
  {
    title: "Website Checker",
    description: "Crawl pages, inspect content, and prepare website quality reports.",
    icon: FileSearch,
    href: null,
    status: "Coming soon",
  },
  {
    title: "Bulk URL Checker",
    description: "Check status codes and redirects across lists of URLs.",
    icon: Link2,
    href: null,
    status: "Coming soon",
  },
  {
    title: "Website Screenshot Tool",
    description: "Capture page screenshots for review, reporting, and client work.",
    icon: Camera,
    href: null,
    status: "Coming soon",
  },
  {
    title: "SEO Quick Checker",
    description: "Pull headings, meta tags, alt tags, and core page signals from a URL.",
    icon: Search,
    href: null,
    status: "Coming soon",
  },
  {
    title: "Settings",
    description: "Configure AI runtime, image defaults, and local processing limits.",
    icon: Settings,
    href: null,
    status: "Coming soon",
  },
] as const;

export default function Home() {
  return (
    <AppShell
      active="dashboard"
      title="Dashboard"
      subtitle="Build status for the image and website optimization POC."
    >
      <section>
        <div>
          <h2 className="text-xl font-semibold text-[#151923]">Welcome back</h2>
          <p className="mt-1 text-sm text-[#667085]">Pick a tool to continue the current image workflow.</p>
        </div>
        <div className="mt-5 grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {tools.map((tool) => {
            const Icon = tool.icon;
            const isActive = tool.status === "Active";
            const cardClassName =
              "group flex min-h-48 flex-col rounded-lg border border-[#dfe3e8] bg-white p-5 text-left transition hover:border-[#b8c0cc] hover:shadow-sm";
            const content = (
              <>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#f2f4f7] text-[#475467] group-hover:bg-[#edf4ff] group-hover:text-[#1d4ed8]">
                    <Icon aria-hidden="true" size={20} />
                  </div>
                  <span
                    className={`rounded-md px-2.5 py-1 text-xs font-semibold uppercase ${
                      isActive ? "bg-[#fff4e5] text-[#b45309]" : "bg-[#f2f4f7] text-[#667085]"
                    }`}
                  >
                    {tool.status}
                  </span>
                </div>
                <div className="mt-7">
                  <h3 className="text-base font-semibold text-[#151923]">{tool.title}</h3>
                  <p className="mt-3 max-w-md text-sm leading-6 text-[#667085]">{tool.description}</p>
                </div>
                <div className="mt-auto pt-6 text-sm font-medium text-[#1d4ed8]">
                  {isActive ? "Open tool" : "Planned"}
                </div>
              </>
            );

            if (tool.href) {
              return (
                <Link key={tool.title} href={tool.href} className={cardClassName}>
                  {content}
                </Link>
              );
            }

            return (
              <div key={tool.title} className={`${cardClassName} opacity-75`}>
                {content}
              </div>
            );
          })}
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <div key={metric.label} className="rounded-lg border border-[#dfe3e8] bg-white p-5">
            <p className="text-sm text-[#667085]">{metric.label}</p>
            <p className="mt-3 text-3xl font-semibold text-[#151923]">{metric.value}</p>
            <p className="mt-2 text-sm text-[#667085]">{metric.detail}</p>
          </div>
        ))}
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.35fr_0.65fr]">
        <div className="rounded-lg border border-[#dfe3e8] bg-white">
          <div className="border-b border-[#dfe3e8] px-5 py-4">
            <h2 className="text-base font-semibold">Implementation Queue</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead className="bg-[#fafbfc] text-[#667085]">
                <tr>
                  <th className="px-5 py-3 font-medium">Phase</th>
                  <th className="px-5 py-3 font-medium">Focus</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#edf0f2]">
                {phases.map(([phase, focus, status]) => (
                  <tr key={phase}>
                    <td className="px-5 py-4 font-medium text-[#151923]">{phase}</td>
                    <td className="px-5 py-4 text-[#475467]">{focus}</td>
                    <td className="px-5 py-4">
                      <span
                        className={`rounded-md px-2 py-1 text-xs font-medium ${
                          statusClassNames[status] ?? statusClassNames.Planned
                        }`}
                      >
                        {status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="rounded-lg border border-[#dfe3e8] bg-white p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#fff4e5] text-[#b45309]">
              <Activity aria-hidden="true" size={19} />
            </div>
            <div>
              <h2 className="text-base font-semibold">Current Target</h2>
              <p className="text-sm text-[#667085]">Phase 8 image resizer</p>
            </div>
          </div>
          <div className="mt-5 space-y-3 text-sm text-[#475467]">
            <p>Upload, compression, conversion, and AI metadata are implemented.</p>
            <p>Brand documents now guide AI filename, alt text, and caption wording.</p>
            <p>Current target adds exact website-size resizing with crop review before processing.</p>
          </div>
        </div>
      </section>
    </AppShell>
  );
}
