import { useTranslations } from "next-intl";

/**
 * Dashboard page — landing page after locale routing.
 * Shows recent proposals and a quick-start button.
 */
export default function DashboardPage() {
  const t = useTranslations();

  return (
    <div className="space-y-section">
      {/* Page heading */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          {t("dashboard.title")}
        </h1>
        <p className="mt-2 text-sg-slate/70">
          {t("app.tagline")}
        </p>
      </div>

      {/* Quick stats row */}
      <div className="grid grid-cols-1 gap-compact sm:grid-cols-3">
        <StatCard label="Active" value="0" accent="sg-blue" />
        <StatCard label="Completed" value="0" accent="sg-teal" />
        <StatCard label="Total" value="0" accent="sg-navy" />
      </div>

      {/* Empty state — recent proposals */}
      <div className="sg-card p-card text-center">
        <p className="text-sg-slate/60">{t("dashboard.noProposals")}</p>
        <a
          href="new"
          className="mt-4 inline-block rounded-lg bg-sg-blue px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-sg-teal"
        >
          {t("dashboard.startNew")}
        </a>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent: string;
}) {
  return (
    <div className="sg-card p-card">
      <p className="text-sm font-medium text-sg-slate/60">{label}</p>
      <p className={`mt-1 text-2xl font-bold text-${accent}`}>{value}</p>
    </div>
  );
}
