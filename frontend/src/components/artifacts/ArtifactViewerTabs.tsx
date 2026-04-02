/**
 * ArtifactViewerTabs — tabbed artifact viewer with lazy-fetch and download.
 *
 * Renders a tab bar for the four Source Book artifacts and lazy-loads
 * each artifact's data on first visit. Wraps each viewer in
 * ArtifactViewerShell for consistent loading/error/empty states.
 */

"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { getArtifact } from "@/lib/api/artifacts";
import {
  downloadEvidenceLedger,
  downloadSlideBlueprint,
  downloadExternalEvidence,
  downloadRoutingReport,
} from "@/lib/api/export";
import { ArtifactViewerShell } from "./ArtifactViewerShell";
import { EvidenceLedgerViewer } from "./EvidenceLedgerViewer";
import { BlueprintViewer } from "./BlueprintViewer";
import { EvidencePackViewer } from "./EvidencePackViewer";
import { RoutingReportViewer } from "./RoutingReportViewer";
import type { ArtifactTab, EvidenceLedgerData, BlueprintData, EvidencePackData, RoutingReportData } from "./types";

// ── Constants ────────────────────────────────────────────────────────────

const TABS: ArtifactTab[] = [
  "evidence_ledger",
  "slide_blueprint",
  "external_evidence",
  "routing_report",
];

const TAB_I18N: Record<ArtifactTab, string> = {
  evidence_ledger: "evidenceLedger",
  slide_blueprint: "slideBlueprints",
  external_evidence: "externalEvidence",
  routing_report: "routingReport",
};

const DOWNLOAD_FN: Record<ArtifactTab, (id: string) => Promise<void>> = {
  evidence_ledger: downloadEvidenceLedger,
  slide_blueprint: downloadSlideBlueprint,
  external_evidence: downloadExternalEvidence,
  routing_report: downloadRoutingReport,
};

// ── Helpers ──────────────────────────────────────────────────────────────

function isEmptyData(data: unknown): boolean {
  if (data == null) return true;
  if (typeof data === "object") {
    // Check common array-bearing shapes
    const obj = data as Record<string, unknown>;
    if (Array.isArray(obj.entries) && obj.entries.length === 0) return true;
    if (Array.isArray(obj.contract_entries) && obj.contract_entries.length === 0) return true;
    if (Array.isArray(obj.sources) && obj.sources.length === 0) return true;
  }
  return false;
}

// ── Component ────────────────────────────────────────────────────────────

export interface ArtifactViewerTabsProps {
  sessionId: string;
}

export function ArtifactViewerTabs({ sessionId }: ArtifactViewerTabsProps) {
  const t = useTranslations("artifacts");

  const [activeTab, setActiveTab] = useState<ArtifactTab>("evidence_ledger");
  const [cache, setCache] = useState<Partial<Record<ArtifactTab, unknown>>>({});
  const [loading, setLoading] = useState<Partial<Record<ArtifactTab, boolean>>>({});
  const [errors, setErrors] = useState<Partial<Record<ArtifactTab, string>>>({});
  const [downloading, setDownloading] = useState<ArtifactTab | null>(null);

  // ── Lazy fetch on tab change ─────────────────────────────────────────

  useEffect(() => {
    if (cache[activeTab] !== undefined) return;

    let cancelled = false;

    async function fetchTab() {
      setLoading((prev) => ({ ...prev, [activeTab]: true }));
      setErrors((prev) => ({ ...prev, [activeTab]: undefined }));

      try {
        const data = await getArtifact(sessionId, activeTab);
        if (!cancelled) {
          setCache((prev) => ({ ...prev, [activeTab]: data }));
        }
      } catch (err) {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : t("loadError");
          setErrors((prev) => ({ ...prev, [activeTab]: message }));
        }
      } finally {
        if (!cancelled) {
          setLoading((prev) => ({ ...prev, [activeTab]: false }));
        }
      }
    }

    fetchTab();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, sessionId]);

  // ── Download handler ─────────────────────────────────────────────────

  const handleDownload = useCallback(async () => {
    if (downloading) return;
    setDownloading(activeTab);
    try {
      await DOWNLOAD_FN[activeTab](sessionId);
    } finally {
      setDownloading(null);
    }
  }, [activeTab, downloading, sessionId]);

  // ── Render viewer for active tab ─────────────────────────────────────

  function renderViewer() {
    const data = cache[activeTab];
    if (!data) return null;

    switch (activeTab) {
      case "evidence_ledger":
        return <EvidenceLedgerViewer data={data as EvidenceLedgerData} />;
      case "slide_blueprint":
        return <BlueprintViewer data={data as BlueprintData} />;
      case "external_evidence":
        return <EvidencePackViewer data={data as EvidencePackData} />;
      case "routing_report":
        return <RoutingReportViewer data={data as RoutingReportData} />;
    }
  }

  // ── JSX ──────────────────────────────────────────────────────────────

  const tabData = cache[activeTab];
  const tabLoading = loading[activeTab] ?? false;
  const tabError = errors[activeTab] ?? null;
  const tabEmpty = tabData !== undefined && !tabLoading && !tabError && isEmptyData(tabData);

  return (
    <div className="space-y-4">
      {/* Tab bar */}
      <div
        className="flex gap-1 border-b border-sg-border/40 dark:border-slate-700"
        role="tablist"
      >
        {TABS.map((tab) => {
          const isActive = tab === activeTab;
          return (
            <button
              key={tab}
              role="tab"
              aria-selected={isActive}
              data-testid={`tab-${tab}`}
              onClick={() => setActiveTab(tab)}
              className={`
                px-4 py-2 text-sm font-medium transition-colors
                ${
                  isActive
                    ? "border-b-2 border-sg-teal text-sg-teal dark:border-sky-400 dark:text-sky-300"
                    : "text-sg-slate/60 hover:text-sg-navy dark:text-slate-400 dark:hover:text-slate-200"
                }
              `}
            >
              {t(TAB_I18N[tab])}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      <ArtifactViewerShell
        title={t(TAB_I18N[activeTab])}
        isLoading={tabLoading}
        error={tabError}
        isEmpty={tabEmpty}
        emptyMessage={t("noData")}
        onDownload={handleDownload}
        downloadLabel={t("downloadJson")}
        isDownloading={downloading === activeTab}
      >
        {renderViewer()}
      </ArtifactViewerShell>
    </div>
  );
}
