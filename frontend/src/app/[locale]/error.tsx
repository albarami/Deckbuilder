/**
 * Error boundary page — shown when an unhandled error occurs in a route segment.
 *
 * Next.js error boundary for the [locale] layout. Catches runtime errors
 * and displays a branded recovery UI with retry option.
 */

"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";
import { useTranslations } from "next-intl";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Link } from "@/i18n/routing";

interface ErrorPageProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function ErrorPage({ error, reset }: ErrorPageProps) {
  const t = useTranslations("common");

  // Log error in development
  useEffect(() => {
    if (process.env.NODE_ENV === "development") {
      console.error("[ErrorPage]", error);
    }
  }, [error]);

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <Card variant="default" className="max-w-md rounded-2xl text-center dark:border-slate-800 dark:bg-slate-900">
        <div className="mb-4 flex justify-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-red-100 dark:bg-red-500/10">
            <AlertTriangle className="h-8 w-8 text-red-600 dark:text-red-400" aria-hidden="true" />
          </div>
        </div>

        <h1 className="text-lg font-semibold text-sg-navy dark:text-slate-100">
          {t("somethingWentWrong")}
        </h1>

        <p className="mt-2 text-sm text-sg-slate/70 dark:text-slate-300">{t("unexpectedError")}</p>

        {error.digest && (
          <p className="mt-2 text-xs text-sg-slate/40 dark:text-slate-500">
            {t("errorId")}: {error.digest}
          </p>
        )}

        {process.env.NODE_ENV === "development" && (
          <pre className="mt-3 max-h-32 overflow-auto rounded bg-sg-mist p-2 text-left text-xs text-red-600 dark:bg-slate-950 dark:text-red-400">
            {error.message}
          </pre>
        )}

        <div className="mt-6 flex justify-center gap-3">
          <Button variant="primary" size="md" onClick={reset} className="bg-sg-teal hover:bg-sg-navy">
            {t("retry")}
          </Button>
          <Link
            href="/"
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-sg-navy px-4 py-2 text-sm font-semibold text-sg-navy transition-colors hover:bg-sg-navy hover:text-white dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            {t("goToDashboard")}
          </Link>
        </div>
      </Card>
    </div>
  );
}
