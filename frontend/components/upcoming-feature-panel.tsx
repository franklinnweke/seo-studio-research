import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { ArrowRight, Clock3 } from "lucide-react";

export function UpcomingFeaturePanel({
  icon: Icon,
  title,
  description,
  nextMilestone,
  plannedItems,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  nextMilestone: string;
  plannedItems: string[];
}) {
  return (
    <section className="grid gap-5 xl:grid-cols-[1fr_360px]">
      <div className="rounded-lg border border-[#dfe3e8] bg-white">
        <div className="border-b border-[#dfe3e8] px-5 py-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex items-start gap-3">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-[#edf4ff] text-[#1d4ed8]">
                <Icon aria-hidden="true" size={22} />
              </div>
              <div>
                <h2 className="text-base font-semibold text-[#151923]">{title}</h2>
                <p className="mt-1 max-w-2xl text-sm leading-6 text-[#667085]">{description}</p>
              </div>
            </div>
            <span className="inline-flex h-7 items-center rounded-md bg-[#fff4e5] px-2.5 text-xs font-medium text-[#b45309]">
              Coming soon
            </span>
          </div>
        </div>

        <div className="space-y-4 p-5">
          <div className="rounded-lg border border-dashed border-[#b8c0cc] bg-[#fafbfc] px-5 py-8 text-center">
            <Clock3 aria-hidden="true" className="mx-auto text-[#667085]" size={28} />
            <h3 className="mt-3 text-sm font-semibold text-[#151923]">Not available in this build</h3>
            <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-[#667085]">
              This page is reserved for the next workflow slice. Current work is focused on the image upload,
              optimization, AI metadata, and resize flow.
            </p>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-[#151923]">Planned capabilities</h3>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              {plannedItems.map((item) => (
                <div key={item} className="rounded-lg border border-[#dfe3e8] bg-white p-4 text-sm text-[#475467]">
                  {item}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <aside className="space-y-5">
        <div className="rounded-lg border border-[#dfe3e8] bg-white p-5">
          <p className="text-sm font-semibold text-[#151923]">Current recommendation</p>
          <p className="mt-2 text-sm leading-6 text-[#667085]">
            Continue the active image workflow, then return here once this feature is promoted from planned to active.
          </p>
          <Link
            href="/"
            className="mt-4 inline-flex h-10 items-center justify-center gap-2 rounded-md bg-[#1d4ed8] px-4 text-sm font-medium text-white"
          >
            Open dashboard
            <ArrowRight aria-hidden="true" size={16} />
          </Link>
        </div>

        <div className="rounded-lg border border-[#dfe3e8] bg-white p-5">
          <p className="text-sm font-semibold text-[#151923]">Milestone</p>
          <p className="mt-2 text-sm leading-6 text-[#667085]">{nextMilestone}</p>
        </div>
      </aside>
    </section>
  );
}
