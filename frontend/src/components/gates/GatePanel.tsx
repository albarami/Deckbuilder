/**
 * GatePanel — Master gate container that dispatches by gate number.
 *
 * Composes:
 * - GateHeader (title, number, prompt)
 * - Gate-specific review panel (Gate1Context through Gate5QA)
 * - GateActions (approve/reject with feedback)
 *
 * Wired to the useGate hook for API integration.
 */

"use client";

import { useState, useCallback } from "react";
import { Card } from "@/components/ui/Card";
import { useGate } from "@/hooks/use-gate";
import { GateHeader } from "./GateHeader";
import { GateActions } from "./GateActions";
import { Gate1Context } from "./gates/Gate1Context";
import { Gate2Sources, type SourceModifications } from "./gates/Gate2Sources";
import { Gate3Research } from "./gates/Gate3Research";
import { Gate4Slides } from "./gates/Gate4Slides";
import { Gate5QA } from "./gates/Gate5QA";
import type { GateInfo } from "@/lib/types/pipeline";

export interface GatePanelProps {
  /** Gate information from the pipeline store */
  gate: GateInfo;
}

export function GatePanel({ gate }: GatePanelProps) {
  const { approve, reject, isDecidingGate } = useGate();
  const [modifications, setModifications] = useState<SourceModifications | null>(null);

  const handleApprove = useCallback(async () => {
    await approve();
  }, [approve]);

  const handleReject = useCallback(
    async (feedback: string) => {
      await reject(feedback);
    },
    [reject],
  );

  const handleModificationsChange = useCallback(
    (mods: SourceModifications) => {
      setModifications(mods);
    },
    [],
  );

  return (
    <Card variant="elevated" data-testid="gate-panel">
      {/* Header */}
      <GateHeader gate={gate} />

      {/* Divider */}
      <hr className="my-4 border-sg-border" />

      {/* Gate-specific content */}
      <div className="mb-6">
        <GateContent
          gate={gate}
          onModificationsChange={handleModificationsChange}
        />
      </div>

      {/* Divider */}
      <hr className="mb-4 border-sg-border" />

      {/* Actions */}
      <GateActions
        onApprove={handleApprove}
        onReject={handleReject}
        modifications={modifications}
        isDeciding={isDecidingGate}
      />
    </Card>
  );
}

// ── Gate Content Dispatcher ─────────────────────────────────────────────

interface GateContentProps {
  gate: GateInfo;
  onModificationsChange: (mods: SourceModifications) => void;
}

function GateContent({ gate, onModificationsChange }: GateContentProps) {
  switch (gate.gate_number) {
    case 1:
      return <Gate1Context gate={gate} />;
    case 2:
      return (
        <Gate2Sources
          gate={gate}
          onModificationsChange={onModificationsChange}
        />
      );
    case 3:
      return <Gate3Research gate={gate} />;
    case 4:
      return <Gate4Slides gate={gate} />;
    case 5:
      return <Gate5QA gate={gate} />;
    default:
      return (
        <p className="text-sm text-sg-slate/50 italic">
          Unknown gate: {gate.gate_number}
        </p>
      );
  }
}
