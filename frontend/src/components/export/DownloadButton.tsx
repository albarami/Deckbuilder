/**
 * DownloadButton — Polished download button with loading/success/error states.
 *
 * Shows a download icon, transitions to spinner during transfer,
 * flashes a checkmark on success, and shows inline error on failure.
 */

"use client";

import { useCallback, useState } from "react";
import { Button } from "@/components/ui/Button";
import type { ButtonVariant } from "@/components/ui/Button";

export interface DownloadButtonProps {
  /** Button label text */
  label: string;
  /** Download handler — called on click */
  onDownload: () => Promise<void>;
  /** Button variant */
  variant?: ButtonVariant;
  /** Whether the download is available */
  available?: boolean;
  /** Label shown when not available */
  unavailableLabel?: string;
  /** Error message to display */
  errorMessage?: string;
  /** Optional CSS class */
  className?: string;
}

type DownloadState = "idle" | "downloading" | "success" | "error";

export function DownloadButton({
  label,
  onDownload,
  variant = "primary",
  available = true,
  unavailableLabel,
  errorMessage,
  className = "",
}: DownloadButtonProps) {
  const [state, setState] = useState<DownloadState>("idle");
  const [error, setError] = useState<string | null>(null);

  const handleClick = useCallback(async () => {
    if (state === "downloading") return;

    setState("downloading");
    setError(null);

    try {
      await onDownload();
      setState("success");
      // Reset to idle after brief success flash
      setTimeout(() => setState("idle"), 2000);
    } catch {
      setState("error");
      setError(errorMessage ?? "Download failed");
      // Reset to idle after showing error
      setTimeout(() => setState("idle"), 3000);
    }
  }, [onDownload, errorMessage, state]);

  if (!available) {
    return (
      <div className={className} data-testid="download-unavailable">
        <Button variant="ghost" size="md" disabled className="w-full">
          <UnavailableIcon />
          {unavailableLabel ?? label}
        </Button>
      </div>
    );
  }

  return (
    <div className={className}>
      <Button
        variant={state === "error" ? "danger" : variant}
        size="md"
        loading={state === "downloading"}
        disabled={state === "downloading"}
        onClick={handleClick}
        className="w-full"
        data-testid="download-button"
      >
        {state === "success" ? (
          <SuccessIcon />
        ) : state === "error" ? (
          <ErrorIcon />
        ) : state === "downloading" ? null : (
          <DownloadIcon />
        )}
        {state === "success"
          ? label
          : state === "error"
            ? (error ?? "Error")
            : label}
      </Button>
    </div>
  );
}

function DownloadIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-4 w-4"
      aria-hidden="true"
    >
      <path d="M10.75 2.75a.75.75 0 00-1.5 0v8.614L6.295 8.235a.75.75 0 10-1.09 1.03l4.25 4.5a.75.75 0 001.09 0l4.25-4.5a.75.75 0 00-1.09-1.03l-2.955 3.129V2.75z" />
      <path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z" />
    </svg>
  );
}

function SuccessIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-4 w-4 text-white"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function ErrorIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-4 w-4 text-white"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function UnavailableIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-4 w-4"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zm.75-13a.75.75 0 00-1.5 0v5c0 .414.336.75.75.75h4a.75.75 0 000-1.5h-3.25V5z"
        clipRule="evenodd"
      />
    </svg>
  );
}
