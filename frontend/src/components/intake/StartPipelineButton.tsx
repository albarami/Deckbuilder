/**
 * StartPipelineButton — Validates intake form and starts the pipeline.
 *
 * - Validates that files/text + config are present
 * - Calls POST /api/pipeline/start via usePipeline hook
 * - Navigates to /pipeline/{session_id} on success
 */

"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/routing";
import { usePipeline } from "@/hooks/use-pipeline";
import { Button } from "@/components/ui/Button";
import type { UploadedFileInfo, StartPipelineRequest } from "@/lib/types/pipeline";
import type { ProposalConfigValues } from "./ProposalConfig";
import { isConfigValid } from "./ProposalConfig";

export interface StartPipelineButtonProps {
  /** Uploaded files from FileUploadZone */
  uploadedFiles: UploadedFileInfo[];
  /** Pasted text from TextPasteArea */
  pastedText: string;
  /** Proposal configuration */
  config: ProposalConfigValues;
}

export function StartPipelineButton({
  uploadedFiles,
  pastedText,
  config,
}: StartPipelineButtonProps) {
  const t = useTranslations("intake");
  const router = useRouter();
  const { start, isStarting } = usePipeline();
  const [error, setError] = useState<string | null>(null);

  const hasInput = uploadedFiles.length > 0 || pastedText.trim().length > 0;
  const configValid = isConfigValid(config);
  const canStart = hasInput && configValid && !isStarting;

  const handleStart = useCallback(async () => {
    if (!canStart) return;

    setError(null);

    const request: StartPipelineRequest = {
      documents: uploadedFiles.map((f) => ({
        upload_id: f.upload_id,
        filename: f.filename,
      })),
      text_input: pastedText.trim() || undefined,
      language: config.language,
      proposal_mode: config.proposalMode,
      sector: config.sector,
      geography: config.geography,
    };

    try {
      const sessionId = await start(request);
      router.push(`/pipeline/${sessionId}`);
    } catch {
      setError(t("startError"));
    }
  }, [canStart, uploadedFiles, pastedText, config, start, router, t]);

  return (
    <div className="space-y-3">
      <Button
        variant="primary"
        size="lg"
        loading={isStarting}
        disabled={!canStart}
        onClick={handleStart}
        className="w-full bg-sg-teal shadow-sg-glow-teal hover:bg-sg-navy"
        data-testid="start-pipeline-btn"
      >
        {isStarting ? t("starting") : t("startPipeline")}
      </Button>

      {/* Validation hint */}
      {!hasInput && (
        <p className="text-center text-xs text-sg-slate/60 dark:text-slate-400">
          {t("needInput")}
        </p>
      )}

      {/* Error */}
      {error && (
        <p className="text-center text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
