import Link from "next/link";
import {
  Archive,
  FileSearch,
  Gauge,
  ImageIcon,
  Settings,
  Sparkles,
} from "lucide-react";

import { HealthStatus } from "@/components/health-status";

type NavKey = "dashboard" | "image-optimizer" | "website-checker" | "seo-metadata" | "exports" | "settings";

const navigation = [
  { key: "dashboard", label: "Dashboard", icon: Gauge, href: "/" },
  { key: "image-optimizer", label: "Image Optimizer", icon: ImageIcon, href: "/image-optimizer" },
  { key: "website-checker", label: "Website Checker", icon: FileSearch, href: "#" },
  { key: "seo-metadata", label: "SEO Metadata", icon: Sparkles, href: "#" },
  { key: "exports", label: "Exports", icon: Archive, href: "#" },
  { key: "settings", label: "Settings", icon: Settings, href: "#" },
] satisfies Array<{ key: NavKey; label: string; icon: typeof Gauge; href: string }>;

export function AppShell({
  active,
  title,
  subtitle,
  sidebarPhase = "Phase 5 active",
  sidebarDescription = "Generate AI image filenames, alt text, and captions.",
  children,
}: {
  active: NavKey;
  title: string;
  subtitle: string;
  sidebarPhase?: string;
  sidebarDescription?: string;
  children: React.ReactNode;
}) {
  return (
    <main className="min-h-screen bg-[#f6f7f9]">
      <div className="grid min-h-screen grid-cols-1 lg:grid-cols-[264px_1fr]">
        <aside className="border-b border-[#dfe3e8] bg-white lg:border-b-0 lg:border-r">
          <div className="flex h-full flex-col gap-8 p-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#1d4ed8] text-white">
                <Sparkles aria-hidden="true" size={20} />
              </div>
              <div>
                <p className="text-base font-semibold leading-5">seo-studio</p>
                <p className="text-xs text-[#667085]">Local POC</p>
              </div>
            </div>

            <nav aria-label="Main navigation" className="flex flex-col gap-1">
              {navigation.map((item) => {
                const isActive = item.key === active;
                const className = `flex h-10 items-center gap-3 rounded-md px-3 text-sm font-medium ${
                  isActive
                    ? "bg-[#edf4ff] text-[#1d4ed8]"
                    : "text-[#475467] hover:bg-[#f2f4f7] hover:text-[#151923]"
                }`;

                if (item.href === "#") {
                  return (
                    <a key={item.key} href="#" className={className}>
                      <item.icon aria-hidden="true" size={18} />
                      {item.label}
                    </a>
                  );
                }

                return (
                  <Link key={item.key} href={item.href} className={className}>
                    <item.icon aria-hidden="true" size={18} />
                    {item.label}
                  </Link>
                );
              })}
            </nav>

            <div className="mt-auto rounded-lg border border-[#dfe3e8] bg-[#fafbfc] p-4">
              <p className="text-sm font-medium">{sidebarPhase}</p>
              <p className="mt-1 text-sm text-[#667085]">{sidebarDescription}</p>
            </div>
          </div>
        </aside>

        <section className="flex min-w-0 flex-col">
          <header className="border-b border-[#dfe3e8] bg-white px-5 py-4 sm:px-8">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h1 className="text-2xl font-semibold tracking-normal text-[#151923]">{title}</h1>
                <p className="mt-1 text-sm text-[#667085]">{subtitle}</p>
              </div>
              <HealthStatus />
            </div>
          </header>

          <div className="flex-1 space-y-6 p-5 sm:p-8">{children}</div>
        </section>
      </div>
    </main>
  );
}
