import { useState } from "react";
import type { Playbook, PlaybookStep } from "../api/incidents";
import { approveRemediation, dryRunRemediation } from "../api/incidents";
import { ConfirmModal } from "./ConfirmModal";

interface Props {
  playbook: Playbook;
  incidentId: string;
  onPlaybookUpdate?: () => void;
}

const REMEDIATION_LABELS: Record<string, string> = {
  restart_deployment: "Restart Deployment",
  scale_deployment: "Scale Deployment",
  cordon_node: "Cordon Node",
  rollback_deployment: "Rollback Deployment",
  none: "No Auto-Remediation",
};

export function PlaybookPanel({ playbook, incidentId, onPlaybookUpdate }: Props) {
  const [checkedSteps, setCheckedSteps] = useState<Set<number>>(new Set());
  const [dryRunResult, setDryRunResult] = useState<string | null>(null);
  const [remedResult, setRemedResult] = useState<string | null>(null);
  const [loading, setLoading] = useState<"dry-run" | "approve" | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);

  const toggleStep = (step: number) =>
    setCheckedSteps((prev) => {
      const next = new Set(prev);
      next.has(step) ? next.delete(step) : next.add(step);
      return next;
    });

  const handleDryRun = async () => {
    setLoading("dry-run");
    try {
      const result = await dryRunRemediation(incidentId);
      setDryRunResult(result.dry_run_output || "Dry-run succeeded (no output)");
    } catch (e: any) {
      setDryRunResult(`Error: ${e.message}`);
    } finally {
      setLoading(null);
    }
  };

  const handleApprove = async () => {
    setLoading("approve");
    try {
      const result = await approveRemediation(incidentId);
      setRemedResult(
        result.success
          ? `Succeeded:\n${result.live_output}`
          : `Failed: ${result.error}`
      );
      onPlaybookUpdate?.();
    } catch (e: any) {
      setRemedResult(`Error: ${e.message}`);
    } finally {
      setLoading(null);
    }
  };

  const hasSuggestion =
    playbook.auto_remediation_suggestion &&
    playbook.auto_remediation_suggestion !== "none";

  return (
    <div className="space-y-6">
      {/* Probable Cause */}
      {playbook.probable_cause && (
        <section>
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
            Probable Cause
          </h3>
          <div className="card p-4">
            <p className="text-sm text-gray-200 leading-relaxed">
              {playbook.probable_cause}
            </p>
          </div>
        </section>
      )}

      {/* Triage Steps */}
      {playbook.runbook_steps?.length > 0 && (
        <section>
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
            Triage Steps
          </h3>
          <div className="space-y-2">
            {playbook.runbook_steps.map((step: PlaybookStep) => (
              <StepCard
                key={step.step}
                step={step}
                checked={checkedSteps.has(step.step)}
                onToggle={() => toggleStep(step.step)}
              />
            ))}
          </div>
        </section>
      )}

      {/* Escalation Path */}
      {playbook.escalation_path && (
        <section>
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
            Escalation Path
          </h3>
          <div className="card p-4">
            <p className="text-sm text-gray-300">{playbook.escalation_path}</p>
          </div>
        </section>
      )}

      {/* Auto-Remediation */}
      <section>
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
          Auto-Remediation
        </h3>
        <div className="card p-4 space-y-3">
          <div className="flex items-center gap-2">
            <span
              className={`badge ${
                hasSuggestion
                  ? "bg-brand-900/50 text-brand-300 border border-brand-800"
                  : "bg-gray-800 text-gray-500"
              }`}
            >
              {REMEDIATION_LABELS[playbook.auto_remediation_suggestion ?? "none"] ??
                playbook.auto_remediation_suggestion}
            </span>
            {playbook.remediation_approved && (
              <span className="badge bg-green-900/50 text-green-300 border border-green-800">
                Executed
              </span>
            )}
          </div>

          {hasSuggestion && !playbook.remediation_approved && (
            <div className="flex gap-2">
              <button
                onClick={handleDryRun}
                disabled={loading !== null}
                className="btn-ghost text-xs border border-gray-700"
              >
                {loading === "dry-run" ? "Running..." : "Dry Run"}
              </button>
              <button
                onClick={() => setShowConfirm(true)}
                disabled={loading !== null}
                className="btn-danger text-xs"
              >
                {loading === "approve" ? "Executing..." : "Approve & Execute"}
              </button>
            </div>
          )}

          {dryRunResult && (
            <pre className="text-xs text-gray-400 bg-gray-950 rounded p-3 overflow-x-auto whitespace-pre-wrap font-mono border border-gray-800">
              {dryRunResult}
            </pre>
          )}

          {remedResult && (
            <pre
              className={`text-xs rounded p-3 overflow-x-auto whitespace-pre-wrap font-mono border ${
                remedResult.startsWith("Failed") || remedResult.startsWith("Error")
                  ? "text-red-300 bg-red-950/50 border-red-900"
                  : "text-green-300 bg-green-950/50 border-green-900"
              }`}
            >
              {remedResult}
            </pre>
          )}

          {playbook.remediation_result && (
            <div className="text-xs text-gray-500">
              Result: {playbook.remediation_result.slice(0, 200)}
            </div>
          )}
        </div>
      </section>

      <div className="text-xs text-gray-600">
        Generated by {playbook.model_used ?? "Claude"} ·{" "}
        {new Date(playbook.created_at).toLocaleString()}
      </div>

      <ConfirmModal
        open={showConfirm}
        title="Execute Auto-Remediation"
        description="This will run the remediation command directly on your cluster. Make sure you've reviewed the dry-run output first."
        confirmLabel="Execute"
        cancelLabel="Cancel"
        variant="danger"
        onConfirm={() => {
          setShowConfirm(false);
          handleApprove();
        }}
        onCancel={() => setShowConfirm(false)}
      />
    </div>
  );
}

function StepCard({
  step,
  checked,
  onToggle,
}: {
  step: PlaybookStep;
  checked: boolean;
  onToggle: () => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={`card p-3 transition-opacity ${checked ? "opacity-60" : ""}`}
    >
      <div className="flex items-start gap-3">
        <button
          onClick={onToggle}
          className={`mt-0.5 w-5 h-5 rounded border flex-shrink-0 flex items-center justify-center transition-colors ${
            checked
              ? "bg-brand-600 border-brand-600"
              : "border-gray-600 hover:border-brand-500"
          }`}
        >
          {checked && (
            <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                clipRule="evenodd"
              />
            </svg>
          )}
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 font-mono">
              {String(step.step).padStart(2, "0")}
            </span>
            <p
              className={`text-sm font-medium ${
                checked ? "line-through text-gray-500" : "text-gray-100"
              }`}
            >
              {step.action}
            </p>
            <button
              onClick={() => setExpanded(!expanded)}
              className="ml-auto text-gray-600 hover:text-gray-400"
            >
              <svg
                className={`w-4 h-4 transition-transform ${expanded ? "rotate-180" : ""}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          </div>

          {expanded && (
            <div className="mt-2 space-y-2">
              <p className="text-xs text-gray-400 leading-relaxed">
                {step.description}
              </p>
              {step.command && (
                <pre className="text-xs font-mono text-green-300 bg-gray-950 rounded px-3 py-2 overflow-x-auto border border-gray-800">
                  $ {step.command}
                </pre>
              )}
              {step.expected_outcome && (
                <p className="text-xs text-gray-500 italic">
                  Expected: {step.expected_outcome}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
