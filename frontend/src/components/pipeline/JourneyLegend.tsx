"use client";

import { CheckCircle2, FileText, ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { Card } from "@/components/ui/Card";
import { useIsPptEnabled } from "@/hooks/use-is-ppt-enabled";

export function JourneyLegend() {
  const t = useTranslations("pipeline");
  const isPptEnabled = useIsPptEnabled();

  const items = [
    {
      icon: <FileText className="h-4 w-4" aria-hidden="true" />,
      value: isPptEnabled ? t("journeyLegendSteps") : t("journeyLegendStepsSourceBook"),
    },
    {
      icon: <CheckCircle2 className="h-4 w-4" aria-hidden="true" />,
      value: isPptEnabled ? t("journeyLegendGates") : t("journeyLegendGatesSourceBook"),
    },
    {
      icon: <ShieldCheck className="h-4 w-4" aria-hidden="true" />,
      value: t("journeyLegendGovernance"),
    },
  ];

  return (
    <Card
      variant="flat"
      className="rounded-2xl border-sg-border/80 bg-white/80 dark:border-slate-800 dark:bg-slate-900/80"
      data-testid="journey-legend"
    >
      <div className="space-y-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-sg-slate/55 dark:text-slate-400">
            {t("journeyLegendTitle")}
          </p>
          <p className="mt-2 text-sm text-sg-slate/75 dark:text-slate-300">
            {isPptEnabled ? t("journeyLegendSummary") : t("journeyLegendSummarySourceBook")}
          </p>
        </div>

        <div className="grid gap-2 md:grid-cols-3">
          {items.map((item) => (
            <div
              key={item.value}
              className="flex items-center gap-2 rounded-xl border border-sg-border/70 bg-sg-mist/60 px-3 py-3 text-sm text-sg-slate dark:border-slate-800 dark:bg-slate-950/60 dark:text-slate-200"
            >
              <span className="text-sg-blue dark:text-sky-300">{item.icon}</span>
              {item.value}
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
