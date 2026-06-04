"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Archive,
  BriefcaseBusiness,
  CheckCircle2,
  Copy,
  FileSearch,
  Gauge,
  ImageIcon,
  Settings,
  Sparkles,
  X,
} from "lucide-react";

import { HealthStatus } from "@/components/health-status";
import { getBrandContext, getImageMetadata, getJobFiles, getJobStatus } from "@/lib/api";
import { clearActiveImageJobId, useActiveImageJobId } from "@/lib/workspace";

type NavKey = "dashboard" | "image-optimizer" | "website-checker" | "seo-metadata" | "exports" | "settings";

const navigation = [
  { key: "dashboard", label: "Dashboard", icon: Gauge, href: "/" },
  { key: "image-optimizer", label: "Image Optimizer", icon: ImageIcon, href: "/image-optimizer" },
  { key: "website-checker", label: "Website Checker", icon: FileSearch, href: "#" },
  { key: "seo-metadata", label: "SEO Metadata", icon: Sparkles, href: "/seo-metadata" },
  { key: "exports", label: "Exports", icon: Archive, href: "#" },
  { key: "settings", label: "Settings", icon: Settings, href: "#" },
] satisfies Array<{ key: NavKey; label: string; icon: typeof Gauge; href: string }>;

export function AppShell({
  active,
  title,
  subtitle,
  sidebarPhase = "Phase 6 active",
  sidebarDescription = "Attach brand documents so AI metadata follows company context.",
  children,
}: {
  active: NavKey;
  title: string;
  subtitle: string;
  sidebarPhase?: string;
  sidebarDescription?: string;
  children: React.ReactNode;
}) {
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const activeImageJobId = useActiveImageJobId();

  const jobStatusQuery = useQuery({
    queryKey: ["workspace-job-status", activeImageJobId],
    queryFn: () => getJobStatus(activeImageJobId),
    enabled: Boolean(activeImageJobId),
  });

  const filesQuery = useQuery({
    queryKey: ["workspace-job-files", activeImageJobId],
    queryFn: () => getJobFiles(activeImageJobId),
    enabled: Boolean(activeImageJobId),
  });

  const metadataQuery = useQuery({
    queryKey: ["workspace-image-metadata", activeImageJobId],
    queryFn: () => getImageMetadata(activeImageJobId),
    enabled: Boolean(activeImageJobId),
  });

  const brandContextQuery = useQuery({
    queryKey: ["workspace-brand-context", activeImageJobId],
    queryFn: () => getBrandContext(activeImageJobId),
    enabled: Boolean(activeImageJobId),
  });

  const uploadedCount = filesQuery.data?.files.length ?? jobStatusQuery.data?.file_count ?? 0;
  const processedCount = jobStatusQuery.data?.status === "processed" ? jobStatusQuery.data.file_count : 0;
  const metadataResults = metadataQuery.data?.results ?? [];
  const metadataGeneratedCount = metadataResults.filter((result) => result.status === "needs_review").length;
  const metadataFailedCount = metadataResults.filter((result) => result.status === "failed").length;
  const brandDocumentCount = brandContextQuery.data?.documents.length ?? 0;

  const copyActiveJobId = async () => {
    if (!activeImageJobId) return;
    await navigator.clipboard.writeText(activeImageJobId);
  };

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
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setWorkspaceOpen(true)}
                  className="inline-flex h-10 items-center gap-2 rounded-md border border-[#dfe3e8] bg-white px-3 text-sm font-medium text-[#475467] hover:bg-[#edf4ff] hover:text-[#1d4ed8]"
                >
                  <BriefcaseBusiness aria-hidden="true" size={16} />
                  Workspace
                  {activeImageJobId ? (
                    <span className="rounded bg-[#eef6f0] px-1.5 py-0.5 text-xs text-[#20744a]">
                      Active
                    </span>
                  ) : null}
                </button>
                <HealthStatus />
              </div>
            </div>
          </header>

          <div className="flex-1 space-y-6 p-5 sm:p-8">{children}</div>
        </section>
      </div>

      {workspaceOpen ? (
        <div className="fixed inset-0 z-50">
          <button
            type="button"
            className="absolute inset-0 cursor-default bg-[#151923]/35"
            aria-label="Close workspace drawer"
            onClick={() => setWorkspaceOpen(false)}
          />
          <aside className="absolute right-0 top-0 flex h-full w-full max-w-md flex-col bg-white shadow-2xl">
            <div className="flex items-start justify-between gap-4 border-b border-[#dfe3e8] px-5 py-4">
              <div>
                <h2 className="text-base font-semibold text-[#151923]">Current Image Job</h2>
                <p className="mt-1 text-sm text-[#667085]">
                  Shared workspace for image tools.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setWorkspaceOpen(false)}
                className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-[#475467] hover:bg-[#f2f4f7]"
                aria-label="Close workspace drawer"
                title="Close"
              >
                <X aria-hidden="true" size={16} />
              </button>
            </div>

            <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
              {activeImageJobId ? (
                <>
                  <div className="rounded-lg border border-[#dfe3e8] bg-[#fafbfc] p-4">
                    <p className="text-xs font-medium uppercase text-[#667085]">Active job ID</p>
                    <div className="mt-2 flex items-center gap-2">
                      <code className="min-w-0 flex-1 truncate rounded-md bg-white px-2 py-1 text-sm text-[#151923]">
                        {activeImageJobId}
                      </code>
                      <button
                        type="button"
                        onClick={copyActiveJobId}
                        className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-[#475467] hover:bg-[#edf4ff] hover:text-[#1d4ed8]"
                        aria-label="Copy active image job ID"
                        title="Copy job ID"
                      >
                        <Copy aria-hidden="true" size={15} />
                      </button>
                    </div>
                    <div className="mt-3 flex items-center gap-2 text-sm text-[#475467]">
                      <CheckCircle2 aria-hidden="true" size={15} className="text-[#20744a]" />
                      Status: {jobStatusQuery.data?.status ?? "loading"}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-lg border border-[#dfe3e8] bg-white p-4">
                      <p className="text-xs uppercase text-[#667085]">Uploaded</p>
                      <p className="mt-2 text-2xl font-semibold text-[#151923]">{uploadedCount}</p>
                    </div>
                    <div className="rounded-lg border border-[#dfe3e8] bg-white p-4">
                      <p className="text-xs uppercase text-[#667085]">Processed</p>
                      <p className="mt-2 text-2xl font-semibold text-[#151923]">{processedCount}</p>
                    </div>
                    <div className="rounded-lg border border-[#dfe3e8] bg-white p-4">
                      <p className="text-xs uppercase text-[#667085]">Metadata</p>
                      <p className="mt-2 text-2xl font-semibold text-[#151923]">{metadataGeneratedCount}</p>
                    </div>
                    <div className="rounded-lg border border-[#dfe3e8] bg-white p-4">
                      <p className="text-xs uppercase text-[#667085]">Failed</p>
                      <p className="mt-2 text-2xl font-semibold text-[#151923]">{metadataFailedCount}</p>
                    </div>
                    <div className="rounded-lg border border-[#dfe3e8] bg-white p-4">
                      <p className="text-xs uppercase text-[#667085]">Brand docs</p>
                      <p className="mt-2 text-2xl font-semibold text-[#151923]">{brandDocumentCount}</p>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Link
                      href="/image-optimizer"
                      onClick={() => setWorkspaceOpen(false)}
                      className="flex h-10 items-center justify-center rounded-md bg-[#1d4ed8] px-4 text-sm font-medium text-white"
                    >
                      Open Image Optimizer
                    </Link>
                    <Link
                      href="/seo-metadata"
                      onClick={() => setWorkspaceOpen(false)}
                      className="flex h-10 items-center justify-center rounded-md border border-[#dfe3e8] px-4 text-sm font-medium text-[#475467] hover:bg-[#edf4ff] hover:text-[#1d4ed8]"
                    >
                      Open SEO Metadata
                    </Link>
                    <button
                      type="button"
                      onClick={clearActiveImageJobId}
                      className="flex h-10 w-full items-center justify-center rounded-md border border-[#dfe3e8] px-4 text-sm font-medium text-[#b42318] hover:bg-[#fff5f5]"
                    >
                      Clear active job
                    </button>
                  </div>
                </>
              ) : (
                <div className="rounded-lg border border-dashed border-[#b8c0cc] bg-[#fafbfc] px-4 py-10 text-center">
                  <BriefcaseBusiness aria-hidden="true" className="mx-auto text-[#667085]" size={28} />
                  <h3 className="mt-3 text-sm font-semibold text-[#151923]">No active image job</h3>
                  <p className="mt-2 text-sm text-[#667085]">
                    Upload images in Image Optimizer to start a shared job for resize, metadata, and exports.
                  </p>
                  <Link
                    href="/image-optimizer"
                    onClick={() => setWorkspaceOpen(false)}
                    className="mt-4 inline-flex h-10 items-center justify-center rounded-md bg-[#1d4ed8] px-4 text-sm font-medium text-white"
                  >
                    Upload images
                  </Link>
                </div>
              )}
            </div>
          </aside>
        </div>
      ) : null}
    </main>
  );
}
