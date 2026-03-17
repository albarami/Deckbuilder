/**
 * Dashboard page — landing page after locale routing.
 * Shows quick stats and recent proposals.
 */

import { useTranslations } from "next-intl";
import { QuickStats } from "@/components/dashboard/QuickStats";
import { RecentProposals } from "@/components/dashboard/RecentProposals";

export default function DashboardPage() {
  const t = useTranslations();

  return (
    <div className="space-y-section">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-sg-navy dark:text-slate-100">
          {t("dashboard.title")}
        </h1>
        <p className="mt-2 max-w-3xl text-sg-slate/70 dark:text-slate-300">
          {t("dashboard.subtitle")}
        </p>
      </div>

      <QuickStats />
      <RecentProposals />
    </div>
  );
}
