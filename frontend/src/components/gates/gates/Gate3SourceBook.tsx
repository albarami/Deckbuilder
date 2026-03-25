/**
 * Gate3SourceBook — Source Book review surface (primary Gate 3 panel).
 *
 * Presents Source Book summary, quality/evidence metrics, section previews,
 * and a prominent DOCX download CTA before Gate 3 approval.
 */

"use client";

import { useMemo, useState } from "react";
import {
  CheckCircle2,
  Download,
  FileText,
  Layers3,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { downloadDocx } from "@/lib/api/export";
import { usePipelineStore } from "@/stores/pipeline-store";
import type { Gate3SourceBookData, GateInfo } from "@/lib/types/pipeline";

export interface Gate3SourceBookProps {
  gate: GateInfo;
}

export function Gate3SourceBook({ gate }: Gate3SourceBookProps) {
  const t = useTranslations("gate");
  const locale = useLocale();
  const isRtl = locale.toLowerCase().startsWith("ar");
  const sessionId = usePipelineStore((state) => state.sessionId);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const data = useMemo(() => extractSourceBookData(gate.gate_data), [gate.gate_data]);

  const labels = isRtl ? AR_LABELS : EN_LABELS;

  const handleDownloadDocx = async () => {
    if (!sessionId || isDownloading) return;
    setDownloadError(null);
    setIsDownloading(true);
    try {
      await downloadDocx(sessionId);
    } catch {
      setDownloadError(labels.downloadError);
    } finally {
      setIsDownloading(false);
    }
  };

  if (!data) {
    return (
      <div data-testid="gate-3-source-book">
        <p className="text-sm italic text-sg-slate/50 dark:text-slate-400">{t("noData")}</p>
      </div>
    );
  }

  const score = normalizeScore(data.quality_summary?.reviewer_score);

  return (
    <div
      data-testid="gate-3-source-book"
      className="space-y-5"
      dir={isRtl ? "rtl" : "ltr"}
    >
      <div className="rounded-2xl border border-sky-200 bg-gradient-to-r from-white to-sky-50 p-5 shadow-sm dark:border-sky-900/50 dark:from-slate-900 dark:to-slate-900/60">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700 dark:text-sky-300">
              <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
              {labels.sourceBookReview}
            </p>
            <h3 className="text-xl font-bold text-sg-navy dark:text-slate-100">
              {data.source_book_title || labels.defaultTitle}
            </h3>
            <div className="flex flex-wrap gap-2">
              <Badge variant="info">{labels.wordCount(data.total_word_count)}</Badge>
              <Badge variant="default">{labels.sectionCount(data.section_count)}</Badge>
            </div>
          </div>

          <Button
            variant="primary"
            size="lg"
            onClick={handleDownloadDocx}
            loading={isDownloading}
            disabled={!sessionId || isDownloading}
            className="bg-sg-teal px-6 shadow-sg-glow-teal hover:bg-sg-navy"
            data-testid="gate-3-docx-download"
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            {labels.downloadDocx}
          </Button>
        </div>

        {downloadError ? (
          <p className="mt-3 text-xs text-red-600 dark:text-red-300">{downloadError}</p>
        ) : null}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-sg-border bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
          <p className="mb-2 inline-flex items-center gap-2 text-sm font-semibold text-sg-navy dark:text-slate-100">
            <ShieldCheck className="h-4 w-4 text-emerald-600" aria-hidden="true" />
            {labels.qualitySummary}
          </p>

          <div className="space-y-3 text-sm">
            {score !== null ? (
              <div>
                <div className="mb-1 flex items-center justify-between text-xs text-sg-slate/70 dark:text-slate-300">
                  <span>{labels.reviewerScore}</span>
                  <span className="font-semibold">{score}%</span>
                </div>
                <div className="h-2 rounded-full bg-sg-mist dark:bg-slate-800">
                  <div
                    className="h-2 rounded-full bg-sg-teal transition-all"
                    style={{ width: `${score}%` }}
                  />
                </div>
              </div>
            ) : null}

            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-sg-slate/70 dark:text-slate-300">
                {labels.benchmark}
              </span>
              <Badge variant={data.quality_summary?.benchmark_passed ? "success" : "warning"}>
                {data.quality_summary?.benchmark_passed ? labels.passed : labels.review}
              </Badge>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <MetricCard
                label={labels.evidenceCount}
                value={String(data.quality_summary?.evidence_count ?? 0)}
              />
              <MetricCard
                label={labels.blueprintCount}
                value={String(data.quality_summary?.blueprint_count ?? 0)}
              />
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-sg-border bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
          <p className="mb-3 inline-flex items-center gap-2 text-sm font-semibold text-sg-navy dark:text-slate-100">
            <FileText className="h-4 w-4 text-sky-600" aria-hidden="true" />
            {labels.evidencePackage}
          </p>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <MetricCard
              label={labels.ledgerEntries}
              value={String(data.evidence_summary?.evidence_ledger_entries ?? 0)}
            />
            <MetricCard
              label={labels.externalSources}
              value={String(data.evidence_summary?.external_source_count ?? 0)}
            />
          </div>

          <p className="mt-4 mb-2 inline-flex items-center gap-2 text-sm font-semibold text-sg-navy dark:text-slate-100">
            <Layers3 className="h-4 w-4 text-indigo-600" aria-hidden="true" />
            {labels.blueprintSummary}
          </p>
          <div className="space-y-2">
            <MetricCard
              label={labels.totalEntries}
              value={String(data.blueprint_summary?.total_entries ?? 0)}
            />
            <div className="flex flex-wrap gap-1.5">
              {(data.blueprint_summary?.covered_sections ?? []).map((sectionId) => (
                <Badge key={sectionId} variant="info" className="text-[10px] uppercase">
                  {sectionId}
                </Badge>
              ))}
              {(data.blueprint_summary?.covered_sections?.length ?? 0) === 0 ? (
                <span className="text-xs text-sg-slate/55 dark:text-slate-400">{labels.none}</span>
              ) : null}
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-sg-border bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <p className="mb-3 inline-flex items-center gap-2 text-sm font-semibold text-sg-navy dark:text-slate-100">
          <CheckCircle2 className="h-4 w-4 text-sg-teal" aria-hidden="true" />
          {labels.sectionPreview}
        </p>

        <div className="max-h-[26rem] space-y-2 overflow-y-auto pe-1">
          {data.sections.map((section, index) => (
            <details
              key={section.section_id || `${index}`}
              open={index === 0}
              className="rounded-lg border border-sg-border bg-sg-mist/30 px-3 py-2 dark:border-slate-800 dark:bg-slate-950/40"
            >
              <summary className="cursor-pointer list-none text-sm font-semibold text-sg-navy dark:text-slate-100">
                <div className="flex items-center justify-between gap-2">
                  <span className="line-clamp-1">{section.title || `${labels.section} ${index + 1}`}</span>
                  <Badge variant="default">{labels.preview}</Badge>
                </div>
              </summary>
              <p className="mt-2 text-sm leading-relaxed text-sg-slate/80 dark:text-slate-300">
                {section.preview_paragraph || labels.noPreview}
              </p>
            </details>
          ))}
          {data.sections.length === 0 ? (
            <p className="text-sm italic text-sg-slate/50 dark:text-slate-400">{labels.noPreview}</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-sg-border/70 bg-sg-mist/35 px-3 py-2 dark:border-slate-800 dark:bg-slate-950/40">
      <p className="text-[10px] font-medium uppercase tracking-wide text-sg-slate/60 dark:text-slate-400">
        {label}
      </p>
      <p className="mt-1 text-sm font-semibold text-sg-navy dark:text-slate-100">{value}</p>
    </div>
  );
}

function extractSourceBookData(data: unknown): Gate3SourceBookData | null {
  if (!data || typeof data !== "object") return null;
  const obj = data as Record<string, unknown>;
  if (!Array.isArray(obj.sections)) return null;

  const sections = obj.sections
    .filter((section): section is Record<string, unknown> => Boolean(section) && typeof section === "object")
    .map((section, index) => ({
      section_id: String(section.section_id ?? `section_${index + 1}`),
      title: String(section.title ?? ""),
      preview_paragraph: String(section.preview_paragraph ?? ""),
      word_count:
        typeof section.word_count === "number" ? section.word_count : undefined,
    }));

  const quality = toRecord(obj.quality_summary);
  const evidence = toRecord(obj.evidence_summary);
  const blueprint = toRecord(obj.blueprint_summary);

  return {
    source_book_title:
      typeof obj.source_book_title === "string" ? obj.source_book_title : undefined,
    total_word_count:
      typeof obj.total_word_count === "number" ? obj.total_word_count : 0,
    section_count:
      typeof obj.section_count === "number" ? obj.section_count : sections.length,
    sections,
    quality_summary: quality
      ? {
          reviewer_score:
            typeof quality.reviewer_score === "number" ? quality.reviewer_score : undefined,
          benchmark_passed:
            typeof quality.benchmark_passed === "boolean"
              ? quality.benchmark_passed
              : undefined,
          evidence_count:
            typeof quality.evidence_count === "number" ? quality.evidence_count : undefined,
          blueprint_count:
            typeof quality.blueprint_count === "number" ? quality.blueprint_count : undefined,
        }
      : undefined,
    evidence_summary: evidence
      ? {
          evidence_ledger_entries:
            typeof evidence.evidence_ledger_entries === "number"
              ? evidence.evidence_ledger_entries
              : 0,
          external_source_count:
            typeof evidence.external_source_count === "number"
              ? evidence.external_source_count
              : 0,
        }
      : undefined,
    blueprint_summary: blueprint
      ? {
          total_entries:
            typeof blueprint.total_entries === "number" ? blueprint.total_entries : 0,
          covered_sections: Array.isArray(blueprint.covered_sections)
            ? blueprint.covered_sections.map((item) => String(item))
            : [],
        }
      : undefined,
    docx_ready: typeof obj.docx_ready === "boolean" ? obj.docx_ready : false,
  };
}

function toRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object") return null;
  return value as Record<string, unknown>;
}

function normalizeScore(value: number | undefined): number | null {
  if (typeof value !== "number") return null;
  if (value <= 1) return Math.round(value * 100);
  if (value > 100) return 100;
  return Math.round(value);
}

const EN_LABELS = {
  sourceBookReview: "Source Book Review",
  defaultTitle: "Source Book",
  downloadDocx: "Download Source Book DOCX",
  downloadError: "Unable to download DOCX right now. Please try again.",
  qualitySummary: "Quality & Benchmark",
  reviewerScore: "Reviewer score",
  benchmark: "Benchmark",
  passed: "Passed",
  review: "Needs review",
  evidenceCount: "Evidence count",
  blueprintCount: "Blueprint count",
  evidencePackage: "Evidence Package",
  ledgerEntries: "Ledger entries",
  externalSources: "External sources",
  blueprintSummary: "Slide Blueprint Summary",
  totalEntries: "Total entries",
  none: "None",
  sectionPreview: "Section Preview",
  section: "Section",
  preview: "Preview",
  noPreview: "No section previews available.",
  wordCount: (value: number) => `${value.toLocaleString()} words`,
  sectionCount: (value: number) => `${value} sections`,
};

const AR_LABELS = {
  sourceBookReview: "مراجعة كتاب المصدر",
  defaultTitle: "كتاب المصدر",
  downloadDocx: "تنزيل ملف DOCX لكتاب المصدر",
  downloadError: "تعذر تنزيل ملف DOCX حالياً. حاول مرة أخرى.",
  qualitySummary: "الجودة والقياس المرجعي",
  reviewerScore: "درجة المراجع",
  benchmark: "القياس المرجعي",
  passed: "ناجح",
  review: "تحتاج مراجعة",
  evidenceCount: "عدد الأدلة",
  blueprintCount: "عدد المخططات",
  evidencePackage: "حزمة الأدلة",
  ledgerEntries: "سجلات الأدلة",
  externalSources: "المصادر الخارجية",
  blueprintSummary: "ملخص مخطط الشرائح",
  totalEntries: "إجمالي العناصر",
  none: "لا يوجد",
  sectionPreview: "معاينة الأقسام",
  section: "قسم",
  preview: "معاينة",
  noPreview: "لا توجد معاينات متاحة للأقسام.",
  wordCount: (value: number) => `${value.toLocaleString()} كلمة`,
  sectionCount: (value: number) => `${value} أقسام`,
};
