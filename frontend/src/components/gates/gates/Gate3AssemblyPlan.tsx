/**
 * Gate3AssemblyPlan — Assembly Plan review panel for the template-first pipeline.
 *
 * Legacy fallback for Gate 3 payloads in pre-Source-Book workflows.
 *
 * Surfaces the assembly plan decisions: methodology phases, slide budget,
 * selected case studies, team bios, service divider, and manifest composition.
 */

"use client";

import type { GateInfo, Gate3AssemblyPlanData } from "@/lib/types/pipeline";

export interface Gate3AssemblyPlanProps {
  gate: GateInfo;
}

export function Gate3AssemblyPlan({ gate }: Gate3AssemblyPlanProps) {
  const data = gate.gate_data as Gate3AssemblyPlanData | null;

  if (!data) {
    return (
      <p className="text-sm text-sg-slate/50 italic">
        No assembly plan data available.
      </p>
    );
  }

  return (
    <div data-testid="gate-3-assembly-plan" className="space-y-5">
      <p className="mb-4 text-sm text-sg-slate/70">{gate.summary}</p>

      {/* Overview */}
      <section>
        <h3 className="mb-2 text-sm font-semibold text-sg-slate">Overview</h3>
        <div className="grid grid-cols-3 gap-3">
          <InfoCard label="Mode" value={data.proposal_mode} />
          <InfoCard label="Geography" value={data.geography} />
          <InfoCard label="Sector" value={data.sector} />
        </div>
      </section>

      {/* Methodology Phases */}
      {data.methodology_phases.length > 0 && (
        <section>
          <h3 className="mb-2 text-sm font-semibold text-sg-slate">
            Methodology ({data.methodology_phases.length} phases)
          </h3>
          <div className="space-y-1">
            {data.methodology_phases.map((phase, i) => (
              <div
                key={i}
                className="flex items-center justify-between rounded-md bg-sg-mist/40 px-3 py-2 text-xs dark:bg-slate-800"
              >
                <span className="font-medium">{phase.phase_name}</span>
                <span className="text-sg-slate/60">
                  {phase.activities_count} activities · {phase.deliverables_count} deliverables
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Slide Budget */}
      <section>
        <h3 className="mb-2 text-sm font-semibold text-sg-slate">
          Slide Budget ({data.slide_budget.total} total)
        </h3>
        <div className="grid grid-cols-4 gap-2">
          <BudgetCard label="A1 Clone" count={data.slide_budget.a1_clone} />
          <BudgetCard label="A2 Shell" count={data.slide_budget.a2_shell} />
          <BudgetCard label="B Variable" count={data.slide_budget.b_variable} />
          <BudgetCard label="Pool Clone" count={data.slide_budget.pool_clone} />
        </div>
      </section>

      {/* Case Studies */}
      {data.case_studies.length > 0 && (
        <section>
          <h3 className="mb-2 text-sm font-semibold text-sg-slate">
            Case Studies ({data.case_studies.length} selected)
          </h3>
          <div className="space-y-1">
            {data.case_studies.map((cs, i) => (
              <div
                key={i}
                className="flex items-center justify-between rounded-md bg-sg-mist/40 px-3 py-2 text-xs dark:bg-slate-800"
              >
                <span className="font-mono">{cs.asset_id}</span>
                <span className="text-sg-slate/60">score: {cs.score.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Team Bios */}
      {data.team_bios.length > 0 && (
        <section>
          <h3 className="mb-2 text-sm font-semibold text-sg-slate">
            Team Bios ({data.team_bios.length} selected)
          </h3>
          <div className="space-y-1">
            {data.team_bios.map((tb, i) => (
              <div
                key={i}
                className="flex items-center justify-between rounded-md bg-sg-mist/40 px-3 py-2 text-xs dark:bg-slate-800"
              >
                <span className="font-mono">{tb.asset_id}</span>
                <span className="text-sg-slate/60">score: {tb.score.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Service Divider */}
      {data.selected_service_divider && (
        <section>
          <h3 className="mb-2 text-sm font-semibold text-sg-slate">Service Divider</h3>
          <p className="rounded-md bg-sg-mist/40 px-3 py-2 text-xs dark:bg-slate-800">
            {data.selected_service_divider}
          </p>
        </section>
      )}

      {/* Manifest Composition */}
      <section>
        <h3 className="mb-2 text-sm font-semibold text-sg-slate">
          Manifest ({data.manifest_composition.total_entries} entries)
        </h3>
        <div className="flex flex-wrap gap-2">
          {Object.entries(data.manifest_composition.entry_type_counts).map(
            ([type, count]) => (
              <span
                key={type}
                className="rounded-full bg-sg-mist px-2.5 py-1 text-xs font-medium dark:bg-slate-800"
              >
                {type}: {count}
              </span>
            ),
          )}
        </div>
      </section>

      {/* Win Themes */}
      {data.win_themes.length > 0 && (
        <section>
          <h3 className="mb-2 text-sm font-semibold text-sg-slate">Win Themes</h3>
          <ul className="list-inside list-disc space-y-0.5 text-xs text-sg-slate/80">
            {data.win_themes.map((theme, i) => (
              <li key={i}>{theme}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-sg-mist/40 px-3 py-2 dark:bg-slate-800">
      <p className="text-[10px] font-medium uppercase tracking-wider text-sg-slate/50">
        {label}
      </p>
      <p className="text-sm font-semibold">{value || "—"}</p>
    </div>
  );
}

function BudgetCard({ label, count }: { label: string; count: number }) {
  return (
    <div className="rounded-md bg-sg-mist/40 px-3 py-2 text-center dark:bg-slate-800">
      <p className="text-lg font-bold">{count}</p>
      <p className="text-[10px] font-medium uppercase tracking-wider text-sg-slate/50">
        {label}
      </p>
    </div>
  );
}
