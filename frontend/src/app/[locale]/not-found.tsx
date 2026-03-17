/**
 * 404 Not Found page — shown when a route doesn't match.
 *
 * Branded Strategic Gears 404 with navigation back to dashboard.
 */

import { AlertTriangle } from "lucide-react";
import { useTranslations } from "next-intl";
import { Card } from "@/components/ui/Card";
import { Link } from "@/i18n/routing";

export default function NotFoundPage() {
  const t = useTranslations("common");

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <Card variant="default" className="max-w-md rounded-2xl text-center dark:border-slate-800 dark:bg-slate-900">
        <div className="mb-4 flex justify-center">
          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-sg-mist dark:bg-slate-950">
            <AlertTriangle className="h-10 w-10 text-sg-slate/40 dark:text-slate-500" aria-hidden="true" />
          </div>
        </div>

        <p className="text-4xl font-bold text-sg-navy dark:text-slate-100">404</p>

        <h1 className="mt-2 text-lg font-semibold text-sg-navy dark:text-slate-100">
          {t("pageNotFound")}
        </h1>

        <p className="mt-2 text-sm text-sg-slate/70 dark:text-slate-300">{t("pageNotFoundMessage")}</p>

        <Link
          href="/"
          className="mt-6 inline-flex items-center justify-center gap-2 rounded-lg bg-sg-teal px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-sg-navy"
        >
          {t("goToDashboard")}
        </Link>
      </Card>
    </div>
  );
}
