import { Activity } from "lucide-react";

import { AppShell } from "@/components/app-shell";

const metrics = [
  { label: "Images processed", value: "0", detail: "Upload and compression are ready" },
  { label: "Average savings", value: "0%", detail: "Shown after image compression" },
  { label: "Broken links", value: "0", detail: "Crawler starts in Phase 8" },
  { label: "Metadata generated", value: "0", detail: "AI starts in Phase 5" },
];

const phases = [
  ["Phase 0", "Project setup", "Complete"],
  ["Phase 0.5", "Swagger and OpenAPI", "Complete"],
  ["Phase 1", "Image upload system", "Complete"],
  ["Phase 2", "Image compression", "Complete"],
  ["Phase 3", "Image conversion", "Complete"],
  ["Phase 4", "Filename cleanup", "Complete"],
  ["Phase 5", "AI image metadata", "Active"],
  ["Phase 6", "Review UI", "Planned"],
  ["Phase 7", "Export system", "Planned"],
  ["Phase 8", "Website crawler", "Planned"],
  ["Phase 9", "Broken link checker", "Planned"],
  ["Phase 10", "AI SEO metadata generator", "Planned"],
];

const statusClassNames: Record<string, string> = {
  Complete: "bg-[#eef6f0] text-[#20744a]",
  Active: "bg-[#fff4e5] text-[#b45309]",
  Planned: "bg-[#f2f4f7] text-[#475467]",
};

export default function Home() {
  return (
    <AppShell
      active="dashboard"
      title="Dashboard"
      subtitle="Build status for the image and website optimization POC."
    >
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
              <p className="text-sm text-[#667085]">Phase 5 AI image metadata</p>
            </div>
          </div>
          <div className="mt-5 space-y-3 text-sm text-[#475467]">
            <p>Upload, compression, and conversion are implemented.</p>
            <p>Image Optimizer now includes editable cleaned filename stems.</p>
            <p>Next phase adds AI-generated image filenames, alt text, and captions.</p>
          </div>
        </div>
      </section>
    </AppShell>
  );
}
