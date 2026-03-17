"use client";

import {
  BookCheck,
  FileCheck2,
  FileOutput,
  GitBranch,
  SearchCheck,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { Card } from "@/components/ui/Card";

export function PipelinePreview() {
  const t = useTranslations("intake");

  const steps = [
    { icon: <SearchCheck className="h-4 w-4" aria-hidden="true" />, label: t("journeyStepsContext") },
    { icon: <Workflow className="h-4 w-4" aria-hidden="true" />, label: t("journeyStepsSources") },
    { icon: <BookCheck className="h-4 w-4" aria-hidden="true" />, label: t("journeyStepsReport") },
    { icon: <GitBranch className="h-4 w-4" aria-hidden="true" />, label: t("journeyStepsSlides") },
    { icon: <ShieldCheck className="h-4 w-4" aria-hidden="true" />, label: t("journeyStepsQa") },
  ];

  const outputs = [
    t("journeyOutputDeck"),
    t("journeyOutputReport"),
    t("journeyOutputSources"),
    t("journeyOutputGap"),
  ];

  return (
    <Card
      variant="elevated"
      className="sg-interactive space-y-5 rounded-2xl border-sg-border/80 dark:border-slate-800 dark:bg-slate-900"
      data-testid="pipeline-preview"
    >
      <div className="flex items-start gap-3">
        <div className="rounded-xl bg-sg-blue/10 p-3 text-sg-blue dark:bg-sky-500/10 dark:text-sky-300">
          <Sparkles className="h-5 w-5" aria-hidden="true" />
        </div>
        <div>
          <h3 className="text-base font-semibold tracking-tight text-sg-navy dark:text-slate-100">
            {t("journeyTitle")}
          </h3>
          <p className="mt-1 text-sm text-sg-slate/70 dark:text-slate-300">
            {t("journeySubtitle")}
          </p>
          <p className="mt-2 text-sm font-medium text-sg-blue dark:text-sky-300">
            {t("journeySummary")}
          </p>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.45fr_1fr]">
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-sg-slate/55 dark:text-slate-400">
            {t("journeyStepsTitle")}
          </p>
          <ul className="space-y-2">
            {steps.map((step, index) => (
              <li
                key={index}
                className="flex items-start gap-3 rounded-xl border border-sg-border/80 bg-sg-mist/70 px-4 py-3 dark:border-slate-800 dark:bg-slate-950/60"
              >
                <span className="mt-0.5 rounded-full bg-white p-2 text-sg-teal shadow-sm dark:bg-slate-900 dark:text-sky-300">
                  {step.icon}
                </span>
                <span className="text-sm text-sg-slate dark:text-slate-200">{step.label}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-sg-border/80 bg-white/80 px-4 py-4 dark:border-slate-800 dark:bg-slate-950/60">
            <div className="mb-2 inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-sg-slate/55 dark:text-slate-400">
              <ShieldCheck className="h-4 w-4 text-sg-teal dark:text-sky-300" aria-hidden="true" />
              {t("journeyGovernanceTitle")}
            </div>
            <p className="text-sm text-sg-slate dark:text-slate-200">
              {t("journeyGovernanceBody")}
            </p>
          </div>

          <div className="rounded-xl border border-sg-border/80 bg-white/80 px-4 py-4 dark:border-slate-800 dark:bg-slate-950/60">
            <div className="mb-3 inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-sg-slate/55 dark:text-slate-400">
              <FileOutput className="h-4 w-4 text-sg-blue dark:text-sky-300" aria-hidden="true" />
              {t("journeyOutputsTitle")}
            </div>
            <ul className="space-y-2">
              {outputs.map((output) => (
                <li
                  key={output}
                  className="flex items-center gap-2 text-sm text-sg-slate dark:text-slate-200"
                >
                  <FileCheck2 className="h-4 w-4 text-sg-teal dark:text-sky-300" aria-hidden="true" />
                  {output}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </Card>
  );
}
