import type { ReactNode } from "react";
import { Download } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";

export interface ArtifactViewerShellProps {
  title: string;
  subtitle?: string;
  onDownload?: () => void;
  /** Required when onDownload is provided — must be a translated string from the caller. */
  downloadLabel?: string;
  isDownloading?: boolean;
  isLoading?: boolean;
  error?: string | null;
  isEmpty?: boolean;
  /** Required when isEmpty is true — must be a translated string from the caller. */
  emptyMessage?: string;
  children: ReactNode;
}

export function ArtifactViewerShell({
  title,
  subtitle,
  onDownload,
  downloadLabel,
  isDownloading = false,
  isLoading = false,
  error,
  isEmpty = false,
  emptyMessage,
  children,
}: ArtifactViewerShellProps) {
  return (
    <Card variant="default" className="rounded-2xl dark:border-slate-800 dark:bg-slate-900">
      {/* Title bar */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-sg-navy dark:text-slate-100">{title}</h2>
          {subtitle && (
            <p className="mt-0.5 text-sm text-sg-slate/70 dark:text-slate-300">{subtitle}</p>
          )}
        </div>

        {onDownload && downloadLabel && (
          <Button
            variant="secondary"
            size="sm"
            onClick={onDownload}
            loading={isDownloading}
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            {downloadLabel}
          </Button>
        )}
      </div>

      {/* Content area: loading > error > empty > children */}
      <div className="mt-4">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Spinner size="md" />
          </div>
        ) : error ? (
          <p role="alert" className="text-sm text-red-600 dark:text-red-400">
            {error}
          </p>
        ) : isEmpty ? (
          <p className="text-sm italic text-sg-slate/50 dark:text-slate-400">
            {emptyMessage}
          </p>
        ) : (
          children
        )}
      </div>
    </Card>
  );
}
