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
      {/* Page heading */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          {t("dashboard.title")}
        </h1>
        <p className="mt-2 text-sg-slate/70">{t("app.tagline")}</p>
      </div>

      {/* Quick stats row */}
      <QuickStats />

      {/* Recent proposals */}
      <RecentProposals />
    </div>
  );
}
