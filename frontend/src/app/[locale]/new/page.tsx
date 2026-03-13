/**
 * New Proposal (RFP Intake) page.
 *
 * Entry point for the user journey:
 * 1. Upload RFP files or paste text
 * 2. Configure proposal parameters
 * 3. Start pipeline
 *
 * Navigates to /pipeline/{session_id} on success.
 */

"use client";

import { useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import { FileUploadZone } from "@/components/intake/FileUploadZone";
import { TextPasteArea } from "@/components/intake/TextPasteArea";
import { ProposalConfig, type ProposalConfigValues } from "@/components/intake/ProposalConfig";
import { StartPipelineButton } from "@/components/intake/StartPipelineButton";
import { Card } from "@/components/ui/Card";
import type { UploadedFileInfo } from "@/lib/types/pipeline";
import { usePipelineStore } from "@/stores/pipeline-store";

const DEFAULT_CONFIG: ProposalConfigValues = {
  language: "en",
  proposalMode: "standard",
  sector: "",
  geography: "",
};

export default function NewProposalPage() {
  const t = useTranslations("intake");
  const isStarting = usePipelineStore((s) => s.isStarting);

  // Form state
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFileInfo[]>([]);
  const [pastedText, setPastedText] = useState("");
  const [config, setConfig] = useState<ProposalConfigValues>(DEFAULT_CONFIG);

  // File upload handlers
  const handleFilesUploaded = useCallback((newFiles: UploadedFileInfo[]) => {
    setUploadedFiles((prev) => [...prev, ...newFiles]);
  }, []);

  const handleFileRemoved = useCallback((uploadId: string) => {
    setUploadedFiles((prev) => prev.filter((f) => f.upload_id !== uploadId));
  }, []);

  return (
    <div className="space-y-section">
      {/* Page heading */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        <p className="mt-2 text-sg-slate/70">{t("subtitle")}</p>
      </div>

      {/* Upload + Paste section */}
      <Card variant="default">
        <div className="space-y-6">
          <FileUploadZone
            onFilesUploaded={handleFilesUploaded}
            uploadedFiles={uploadedFiles}
            onFileRemoved={handleFileRemoved}
            disabled={isStarting}
          />

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-sg-border" />
            </div>
            <div className="relative flex justify-center">
              <span className="bg-sg-white px-3 text-xs uppercase text-sg-slate/50">
                {t("or")}
              </span>
            </div>
          </div>

          <TextPasteArea
            value={pastedText}
            onChange={setPastedText}
            disabled={isStarting}
          />
        </div>
      </Card>

      {/* Configuration section */}
      <Card variant="default">
        <ProposalConfig
          values={config}
          onChange={setConfig}
          disabled={isStarting}
        />
      </Card>

      {/* Start button */}
      <StartPipelineButton
        uploadedFiles={uploadedFiles}
        pastedText={pastedText}
        config={config}
      />
    </div>
  );
}
