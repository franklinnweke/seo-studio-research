"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowRight,
  Check,
  CheckCircle2,
  Circle,
  FileText,
  Lightbulb,
  Loader2,
  Save,
  Sparkles,
} from "lucide-react";

import { useAuthenticatedObjectUrl } from "@/hooks/use-authenticated-object-url";
import {
  getApiErrorMessage,
  getImageContext,
  getMetadataImageDownloadUrl,
  getPageContext,
  suggestImagePurpose,
  updateImageContext,
  updatePageContext,
  type ImageContext,
  type ImageContextResponse,
  type ImagePurpose,
  type ImageUploadFileRecord,
  type PageContextUpdateRequest,
} from "@/lib/api";

export type ContextReadinessState = {
  pageReady: boolean;
  confirmedImageIds: string[];
  imageContexts: Record<string, ImageContext>;
  isLoading: boolean;
  hasError: boolean;
};

const purposeOptions: Array<{
  value: ImagePurpose;
  label: string;
  description: string;
}> = [
  { value: "unknown", label: "Select purpose", description: "A person must classify this image." },
  { value: "informative", label: "Informative", description: "Adds visual information to the page." },
  { value: "decorative", label: "Decorative", description: "Adds atmosphere only and needs empty alt text." },
  { value: "functional", label: "Functional", description: "Acts as a link, button, or control." },
  { value: "text", label: "Text-containing", description: "Communicates important visible words." },
  { value: "complex", label: "Complex", description: "Needs an equivalent long description." },
  { value: "redundant", label: "Redundant", description: "Repeats adjacent content and needs empty alt text." },
];

const emptyPageContext: PageContextUpdateRequest = {
  page_title: "",
  section_heading: "",
  nearby_text: "",
  page_url: "",
  audience: "",
  language: "en-CA",
};

const emptyImageContext: ImageContext = {
  purpose: "unknown",
  purpose_confirmed: false,
  suggested_purpose: null,
  purpose_confidence: null,
  purpose_suggestion_rationale: "",
  link_destination: "",
  functional_action: "",
  long_description_available: false,
  complex_description_acknowledged: false,
  notes: "",
  purpose_source: "unconfirmed",
  updated_at: null,
};

export function isPageContextReady(context: PageContextUpdateRequest) {
  return Boolean(
    context.page_title.trim() &&
      context.nearby_text.trim() &&
      context.audience.trim() &&
      context.language.trim(),
  );
}

export function isImageContextReady(context: ImageContext | undefined) {
  if (!context?.purpose_confirmed || context.purpose === "unknown") return false;
  if (
    context.purpose === "functional" &&
    !context.functional_action.trim() &&
    !context.link_destination.trim()
  ) {
    return false;
  }
  if (
    context.purpose === "complex" &&
    !context.long_description_available &&
    !context.complex_description_acknowledged
  ) {
    return false;
  }
  return true;
}

function purposeLabel(purpose: ImagePurpose | null | undefined) {
  return purposeOptions.find((option) => option.value === purpose)?.label ?? "Unknown";
}

function PurposeRow({
  jobId,
  file,
  context,
  purposeSuggestionEnabled,
  pageReady,
  savingImageId,
  suggestingImageId,
  onSave,
  onSuggest,
}: {
  jobId: string;
  file: ImageUploadFileRecord;
  context: ImageContext;
  purposeSuggestionEnabled: boolean;
  pageReady: boolean;
  savingImageId: string | null;
  suggestingImageId: string | null;
  onSave: (imageId: string, context: ImageContext) => void;
  onSuggest: (imageId: string) => void;
}) {
  const [draft, setDraft] = useState(context);
  const previewUrl = useAuthenticatedObjectUrl(getMetadataImageDownloadUrl(jobId, file.id));

  const selectedPurpose = purposeOptions.find((option) => option.value === draft.purpose);
  const confirmed = isImageContextReady(context);
  const canConfirm = isImageContextReady({
    ...draft,
    purpose_confirmed: draft.purpose !== "unknown",
  });
  const isSaving = savingImageId === file.id;
  const isSuggesting = suggestingImageId === file.id;
  const showEmptyAlt = draft.purpose === "decorative" || draft.purpose === "redundant";

  const confirmPurpose = () => {
    onSave(file.id, {
      ...draft,
      purpose_confirmed: true,
      purpose_source: "human_confirmed",
    });
  };

  return (
    <article className="grid gap-4 border-t border-[#e7eaee] py-5 first:border-t-0 lg:grid-cols-[116px_minmax(0,1fr)_auto]">
      <div className="overflow-hidden rounded-lg border border-[#dfe3e8] bg-[#eef2f6]">
        <div className="aspect-[4/3]">
          {previewUrl ? (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img src={previewUrl} alt="" className="h-full w-full object-cover" />
          ) : (
            <div aria-hidden="true" className="h-full w-full animate-pulse bg-[#e4e9ef]" />
          )}
        </div>
      </div>

      <div className="min-w-0 space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <h4 className="truncate text-sm font-semibold text-[#151923]" title={file.original_filename}>
              {file.original_filename}
            </h4>
            <p className="mt-1 text-xs text-[#667085]">{selectedPurpose?.description}</p>
          </div>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
              confirmed
                ? "bg-[#eef6f0] text-[#20744a]"
                : "bg-[#fff6ed] text-[#b54708]"
            }`}
          >
            {confirmed ? <CheckCircle2 aria-hidden="true" size={13} /> : <Circle aria-hidden="true" size={13} />}
            {confirmed ? `${purposeLabel(context.purpose)} confirmed` : "Confirmation required"}
          </span>
        </div>

        {context.suggested_purpose ? (
          <div className="context-reveal flex flex-col gap-2 rounded-md border border-[#c8d7f4] bg-[#f4f7ff] p-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-[#3459a8]">AI suggestion</p>
              <p className="mt-1 text-sm text-[#263d73]">
                {purposeLabel(context.suggested_purpose)}
                {context.purpose_confidence !== null
                  ? ` · ${Math.round(context.purpose_confidence * 100)}% confidence`
                  : ""}
              </p>
              {context.purpose_suggestion_rationale ? (
                <p className="mt-1 text-xs leading-5 text-[#52658f]">
                  {context.purpose_suggestion_rationale}
                </p>
              ) : null}
            </div>
            <button
              type="button"
              onClick={() =>
                setDraft((current) => ({
                  ...current,
                  purpose: context.suggested_purpose ?? "unknown",
                  purpose_confirmed: false,
                }))
              }
              className="inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-md border border-[#9db5e8] bg-white px-3 text-xs font-medium text-[#3459a8] transition hover:border-[#1d4ed8] hover:text-[#1d4ed8]"
            >
              Use suggestion
              <ArrowRight aria-hidden="true" size={14} />
            </button>
          </div>
        ) : null}

        <div className="grid gap-3 md:grid-cols-2">
          <label className="space-y-1.5">
            <span className="text-xs font-medium text-[#344054]">Image purpose</span>
            <select
              value={draft.purpose}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  purpose: event.target.value as ImagePurpose,
                  purpose_confirmed: false,
                }))
              }
              className="h-10 w-full rounded-md border border-[#cfd5dd] bg-white px-3 text-sm text-[#151923]"
            >
              {purposeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          {draft.purpose === "functional" ? (
            <label className="context-reveal space-y-1.5">
              <span className="text-xs font-medium text-[#344054]">Action performed</span>
              <input
                value={draft.functional_action}
                onChange={(event) =>
                  setDraft((current) => ({ ...current, functional_action: event.target.value }))
                }
                placeholder="Example: Book an appointment"
                className="h-10 w-full rounded-md border border-[#cfd5dd] bg-white px-3 text-sm"
              />
            </label>
          ) : (
            <label className="space-y-1.5">
              <span className="text-xs font-medium text-[#344054]">Reviewer note (optional)</span>
              <input
                value={draft.notes}
                onChange={(event) => setDraft((current) => ({ ...current, notes: event.target.value }))}
                placeholder="Why this purpose fits the page"
                className="h-10 w-full rounded-md border border-[#cfd5dd] bg-white px-3 text-sm"
              />
            </label>
          )}
        </div>

        {draft.purpose === "functional" ? (
          <label className="context-reveal block space-y-1.5">
            <span className="text-xs font-medium text-[#344054]">Link destination (optional)</span>
            <input
              value={draft.link_destination}
              onChange={(event) =>
                setDraft((current) => ({ ...current, link_destination: event.target.value }))
              }
              placeholder="/book or https://example.com/book"
              className="h-10 w-full rounded-md border border-[#cfd5dd] bg-white px-3 text-sm"
            />
          </label>
        ) : null}

        {draft.purpose === "complex" ? (
          <div className="context-reveal flex flex-col gap-2 rounded-md border border-[#ead8ae] bg-[#fffaf0] p-3 text-sm text-[#6f5317]">
            <label className="flex items-start gap-2">
              <input
                type="checkbox"
                checked={draft.long_description_available}
                onChange={(event) =>
                  setDraft((current) => ({ ...current, long_description_available: event.target.checked }))
                }
                className="mt-0.5 h-4 w-4"
              />
              An equivalent long description is available on the page.
            </label>
            <label className="flex items-start gap-2">
              <input
                type="checkbox"
                checked={draft.complex_description_acknowledged}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    complex_description_acknowledged: event.target.checked,
                  }))
                }
                className="mt-0.5 h-4 w-4"
              />
              I acknowledge that alt text alone cannot carry the full information.
            </label>
          </div>
        ) : null}

        {showEmptyAlt ? (
          <div className="context-reveal flex items-start gap-2 rounded-md bg-[#eef6f0] p-3 text-sm text-[#236245]">
            <Lightbulb aria-hidden="true" className="mt-0.5 shrink-0" size={16} />
            <span>
              {purposeLabel(draft.purpose)} images intentionally use empty alt text so assistive
              technology does not announce unnecessary repetition.
            </span>
          </div>
        ) : null}
      </div>

      <div className="flex gap-2 lg:flex-col lg:items-stretch">
        {purposeSuggestionEnabled ? (
          <button
            type="button"
            disabled={isSuggesting || isSaving || !pageReady}
            title={pageReady ? "Request an AI purpose suggestion" : "Save page context before requesting a suggestion"}
            onClick={() => onSuggest(file.id)}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-[#d4dae2] px-3 text-xs font-medium text-[#475467] transition hover:bg-[#f4f7ff] hover:text-[#1d4ed8] disabled:opacity-50"
          >
            {isSuggesting ? <Loader2 aria-hidden="true" className="animate-spin" size={14} /> : <Sparkles aria-hidden="true" size={14} />}
            Suggest
          </button>
        ) : null}
        <button
          type="button"
          disabled={!canConfirm || isSaving || isSuggesting}
          onClick={confirmPurpose}
          className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-[#1d4ed8] px-3 text-xs font-medium text-white transition hover:bg-[#1e40af] disabled:cursor-not-allowed disabled:bg-[#98a2b3]"
        >
          {isSaving ? <Loader2 aria-hidden="true" className="animate-spin" size={14} /> : <Check aria-hidden="true" size={14} />}
          Confirm
        </button>
      </div>
    </article>
  );
}

function PageContextForm({
  initialContext,
  isPending,
  onSubmit,
}: {
  initialContext: PageContextUpdateRequest;
  isPending: boolean;
  onSubmit: (context: PageContextUpdateRequest) => void;
}) {
  const [draft, setDraft] = useState(initialContext);

  return (
    <form
      className="mt-4 grid gap-4 lg:grid-cols-2"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit(draft);
      }}
    >
      <label className="space-y-1.5">
        <span className="text-xs font-medium text-[#344054]">Page title *</span>
        <input required value={draft.page_title} onChange={(event) => setDraft((current) => ({ ...current, page_title: event.target.value }))} className="h-10 w-full rounded-md border border-[#cfd5dd] px-3 text-sm" />
      </label>
      <label className="space-y-1.5">
        <span className="text-xs font-medium text-[#344054]">Section heading</span>
        <input value={draft.section_heading} onChange={(event) => setDraft((current) => ({ ...current, section_heading: event.target.value }))} className="h-10 w-full rounded-md border border-[#cfd5dd] px-3 text-sm" />
      </label>
      <label className="space-y-1.5 lg:col-span-2">
        <span className="text-xs font-medium text-[#344054]">Nearby page text *</span>
        <textarea required rows={3} value={draft.nearby_text} onChange={(event) => setDraft((current) => ({ ...current, nearby_text: event.target.value }))} className="w-full resize-y rounded-md border border-[#cfd5dd] px-3 py-2 text-sm" />
      </label>
      <label className="space-y-1.5">
        <span className="text-xs font-medium text-[#344054]">Audience *</span>
        <input required value={draft.audience} onChange={(event) => setDraft((current) => ({ ...current, audience: event.target.value }))} className="h-10 w-full rounded-md border border-[#cfd5dd] px-3 text-sm" />
      </label>
      <label className="space-y-1.5">
        <span className="text-xs font-medium text-[#344054]">Language *</span>
        <input required value={draft.language} onChange={(event) => setDraft((current) => ({ ...current, language: event.target.value }))} className="h-10 w-full rounded-md border border-[#cfd5dd] px-3 text-sm" />
      </label>
      <label className="space-y-1.5 lg:col-span-2">
        <span className="text-xs font-medium text-[#344054]">Public page URL (optional)</span>
        <input type="url" value={draft.page_url} onChange={(event) => setDraft((current) => ({ ...current, page_url: event.target.value }))} className="h-10 w-full rounded-md border border-[#cfd5dd] px-3 text-sm" />
      </label>
      <div className="lg:col-span-2">
        <button type="submit" disabled={isPending} className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-[#cfd5dd] bg-white px-4 text-sm font-medium text-[#344054] transition hover:border-[#1d4ed8] hover:text-[#1d4ed8] disabled:opacity-50">
          {isPending ? <Loader2 aria-hidden="true" className="animate-spin" size={16} /> : <Save aria-hidden="true" size={16} />}
          Save page context
        </button>
      </div>
    </form>
  );
}

export function MetadataContextPanel({
  jobId,
  files,
  contextEnabled,
  purposeSuggestionEnabled,
  onReadinessChange,
}: {
  jobId: string;
  files: ImageUploadFileRecord[];
  contextEnabled: boolean;
  purposeSuggestionEnabled: boolean;
  onReadinessChange: (state: ContextReadinessState) => void;
}) {
  const queryClient = useQueryClient();
  const [savingImageId, setSavingImageId] = useState<string | null>(null);
  const [suggestingImageId, setSuggestingImageId] = useState<string | null>(null);

  const pageQuery = useQuery({
    queryKey: ["page-context", jobId],
    queryFn: () => getPageContext(jobId),
    enabled: Boolean(jobId && contextEnabled),
  });
  const imageQueries = useQueries({
    queries: files.map((file) => ({
      queryKey: ["image-context", jobId, file.id],
      queryFn: () => getImageContext(jobId, file.id),
      enabled: Boolean(jobId && contextEnabled),
    })),
  });

  const imageContexts = useMemo(
    () =>
      Object.fromEntries(
        files.map((file, index) => [
          file.id,
          imageQueries[index]?.data?.image_context ?? emptyImageContext,
        ]),
      ),
    [files, imageQueries],
  );
  const pageReady = isPageContextReady(pageQuery.data?.page_context ?? emptyPageContext);
  const confirmedImageIds = files
    .filter((file) => isImageContextReady(imageContexts[file.id]))
    .map((file) => file.id);
  const isLoading = pageQuery.isLoading || imageQueries.some((query) => query.isLoading);
  const hasError = pageQuery.isError || imageQueries.some((query) => query.isError);
  const readinessSignature = JSON.stringify({
    pageReady,
    confirmedImageIds,
    imageContexts,
    isLoading,
    hasError,
  });

  useEffect(() => {
    onReadinessChange({ pageReady, confirmedImageIds, imageContexts, isLoading, hasError });
  }, [readinessSignature, onReadinessChange]); // eslint-disable-line react-hooks/exhaustive-deps

  const pageMutation = useMutation({
    mutationFn: (context: PageContextUpdateRequest) => updatePageContext(jobId, context),
    onSuccess: (response) => queryClient.setQueryData(["page-context", jobId], response),
  });
  const imageMutation = useMutation({
    mutationFn: ({ imageId, context }: { imageId: string; context: ImageContext }) => {
      setSavingImageId(imageId);
      return updateImageContext(jobId, imageId, {
        purpose: context.purpose,
        purpose_confirmed: context.purpose_confirmed,
        suggested_purpose: context.suggested_purpose,
        purpose_confidence: context.purpose_confidence,
        purpose_suggestion_rationale: context.purpose_suggestion_rationale,
        link_destination: context.link_destination,
        functional_action: context.functional_action,
        long_description_available: context.long_description_available,
        complex_description_acknowledged: context.complex_description_acknowledged,
        notes: context.notes,
      });
    },
    onSuccess: (response: ImageContextResponse) => {
      queryClient.setQueryData(["image-context", jobId, response.image_id], response);
    },
    onSettled: () => setSavingImageId(null),
  });
  const suggestionMutation = useMutation({
    mutationFn: (imageId: string) => {
      setSuggestingImageId(imageId);
      return suggestImagePurpose(jobId, imageId);
    },
    onSuccess: (response) => {
      queryClient.setQueryData(["image-context", jobId, response.image_id], response);
    },
    onSettled: () => setSuggestingImageId(null),
  });

  if (!contextEnabled) {
    return (
      <section className="border-y border-[#dfe3e8] bg-[#fafbfc] px-5 py-4">
        <div className="flex items-start gap-3 text-sm text-[#667085]">
          <FileText aria-hidden="true" className="mt-0.5 shrink-0" size={17} />
          <div>
            <h2 className="font-semibold text-[#344054]">Legacy metadata mode</h2>
            <p className="mt-1">
              Context-aware generation is disabled in this environment. Existing image-only metadata generation remains available.
            </p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-[#dfe3e8] bg-white" aria-labelledby="context-workflow-title">
      <div className="border-b border-[#dfe3e8] px-5 py-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#1d4ed8]">Context workflow</p>
            <h2 id="context-workflow-title" className="mt-1 text-base font-semibold text-[#151923]">
              Prepare evidence before generation
            </h2>
            <p className="mt-1 text-sm text-[#667085]">
              Page context guides relevance. A person must confirm every image purpose.
            </p>
          </div>
          <ol className="flex flex-wrap items-center gap-2 text-xs font-medium" aria-label="Context readiness">
            <li className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 transition-colors ${pageReady ? "bg-[#eef6f0] text-[#20744a]" : "bg-[#fff6ed] text-[#b54708]"}`}>
              {pageReady ? <CheckCircle2 aria-hidden="true" size={14} /> : <Circle aria-hidden="true" size={14} />}
              Page context
            </li>
            <li className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 transition-colors ${files.length > 0 && confirmedImageIds.length === files.length ? "bg-[#eef6f0] text-[#20744a]" : "bg-[#fff6ed] text-[#b54708]"}`}>
              {files.length > 0 && confirmedImageIds.length === files.length ? <CheckCircle2 aria-hidden="true" size={14} /> : <Circle aria-hidden="true" size={14} />}
              Purposes {confirmedImageIds.length}/{files.length}
            </li>
          </ol>
        </div>
      </div>

      {(hasError || pageMutation.isError || imageMutation.isError || suggestionMutation.isError) ? (
        <div role="alert" className="m-5 flex items-start gap-2 rounded-md border border-[#f2b8b5] bg-[#fff5f5] p-3 text-sm text-[#b42318]">
          <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={16} />
          <span>{getApiErrorMessage(pageQuery.error ?? imageQueries.find((query) => query.error)?.error ?? pageMutation.error ?? imageMutation.error ?? suggestionMutation.error)}</span>
        </div>
      ) : null}

      <div className="px-5 py-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold text-[#151923]">1. Page context</h3>
            <p className="mt-1 text-sm text-[#667085]">Required fields are title, nearby text, audience, and language.</p>
          </div>
          <span aria-live="polite" className={`text-xs font-medium ${pageReady ? "text-[#20744a]" : "text-[#b54708]"}`}>
            {pageReady ? "Ready" : "Incomplete"}
          </span>
        </div>

        <PageContextForm
          key={pageQuery.data?.page_context.updated_at ?? jobId}
          initialContext={pageQuery.data?.page_context ?? emptyPageContext}
          isPending={pageMutation.isPending}
          onSubmit={(context) => pageMutation.mutate(context)}
        />
      </div>

      <div className="border-t border-[#dfe3e8] px-5 py-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold text-[#151923]">2. Confirm image purpose</h3>
            <p className="mt-1 text-sm text-[#667085]">Suggestions are optional evidence. Confirmation is always a human decision.</p>
          </div>
          {isLoading ? <Loader2 aria-label="Loading image contexts" className="animate-spin text-[#667085]" size={18} /> : null}
        </div>
        <div className="mt-3">
          {files.map((file) => (
            <PurposeRow
              key={`${file.id}-${imageContexts[file.id]?.updated_at ?? "new"}`}
              jobId={jobId}
              file={file}
              context={imageContexts[file.id] ?? emptyImageContext}
              purposeSuggestionEnabled={purposeSuggestionEnabled}
              pageReady={pageReady}
              savingImageId={savingImageId}
              suggestingImageId={suggestingImageId}
              onSave={(imageId, context) => imageMutation.mutate({ imageId, context })}
              onSuggest={(imageId) => suggestionMutation.mutate(imageId)}
            />
          ))}
          {files.length === 0 ? <p className="py-6 text-sm text-[#667085]">Upload images before assigning purpose.</p> : null}
        </div>
      </div>
    </section>
  );
}
