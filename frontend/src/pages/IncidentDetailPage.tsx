import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { fetchIncident, updateIncident, type IncidentDetail } from "../api/incidents";
import { PlaybookPanel } from "../components/PlaybookPanel";
import { SeverityBadge } from "../components/SeverityBadge";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

export function IncidentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [incident, setIncident] = useState<IncidentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [streamedText, setStreamedText] = useState("");
  const [streaming, setStreaming] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  const load = async () => {
    if (!id) return;
    try {
      const data = await fetchIncident(id);
      setIncident(data);
    } catch {
      navigate("/incidents");
    }
    setLoading(false);
  };

  useEffect(() => {
    load();
    return () => eventSourceRef.current?.close();
  }, [id]);

  const startStream = () => {
    if (!id || streaming) return;
    setStreamedText("");
    setStreaming(true);

    const es = new EventSource(
      `${API_BASE}/api/v1/incidents/${id}/playbook/stream`
    );
    eventSourceRef.current = es;

    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.token) setStreamedText((t) => t + data.token);
        if (data.done) {
          setStreaming(false);
          es.close();
          load();
        }
        if (data.error) {
          setStreaming(false);
          es.close();
        }
      } catch {}
    };

    es.onerror = () => {
      setStreaming(false);
      es.close();
    };
  };

  const handleStatusChange = async (newStatus: string) => {
    if (!id) return;
    try {
      const updated = await updateIncident(id, { status: newStatus });
      setIncident(updated);
    } catch {}
  };

  if (loading) {
    return (
      <div className="p-6 text-sm text-gray-600">Loading incident...</div>
    );
  }

  if (!incident) return null;

  return (
    <div className="p-6 space-y-6">
      {/* Back */}
      <button
        onClick={() => navigate(-1)}
        className="text-sm text-gray-500 hover:text-gray-300 flex items-center gap-1"
      >
        ← Back
      </button>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <SeverityBadge severity={incident.severity} pulse={incident.status === "open"} />
            <span className="text-xs text-gray-500">{incident.source}</span>
          </div>
          <h1 className="text-lg font-semibold text-gray-100 leading-snug">
            {incident.title}
          </h1>
          {incident.description && (
            <p className="text-sm text-gray-400 mt-1">{incident.description}</p>
          )}
        </div>
        <div className="flex gap-2 flex-shrink-0">
          {incident.status === "open" && (
            <button
              onClick={() => handleStatusChange("acknowledged")}
              className="btn-ghost text-xs border border-gray-700"
            >
              Acknowledge
            </button>
          )}
          {incident.status !== "resolved" && (
            <button
              onClick={() => handleStatusChange("resolved")}
              className="btn-ghost text-xs border border-gray-700"
            >
              Resolve
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Alert context */}
        <div className="lg:col-span-1 space-y-4">
          <section className="card p-4 space-y-3">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
              Alert Context
            </h3>
            <MetaRow label="Status" value={incident.status} />
            <MetaRow label="Severity" value={incident.severity} />
            <MetaRow label="Source" value={incident.source} />
            <MetaRow
              label="Opened"
              value={new Date(incident.opened_at).toLocaleString()}
            />
            {incident.acknowledged_at && (
              <MetaRow
                label="Acknowledged"
                value={new Date(incident.acknowledged_at).toLocaleString()}
              />
            )}
            {incident.resolved_at && (
              <MetaRow
                label="Resolved"
                value={new Date(incident.resolved_at).toLocaleString()}
              />
            )}
            {incident.assigned_to && (
              <MetaRow label="Assigned to" value={incident.assigned_to} />
            )}
          </section>

          {Object.keys(incident.labels).length > 0 && (
            <section className="card p-4">
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                Labels
              </h3>
              <div className="space-y-1">
                {Object.entries(incident.labels).map(([k, v]) => (
                  <div key={k} className="flex gap-2 text-xs">
                    <span className="text-gray-500 font-mono">{k}:</span>
                    <span className="text-gray-300 font-mono truncate">{String(v)}</span>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        {/* Right: Playbook */}
        <div className="lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-300">
              AI Triage Playbook
            </h2>
            <button
              onClick={startStream}
              disabled={streaming}
              className="btn-primary text-xs"
            >
              {streaming ? "Generating..." : incident.playbook ? "Regenerate" : "Generate Playbook"}
            </button>
          </div>

          {streaming && (
            <div className="card p-4 mb-4">
              <pre
                className={`text-xs text-gray-300 font-mono whitespace-pre-wrap leading-relaxed ${
                  streaming ? "streaming-cursor" : ""
                }`}
              >
                {streamedText}
              </pre>
            </div>
          )}

          {!streaming && incident.playbook ? (
            <PlaybookPanel
              playbook={incident.playbook}
              incidentId={incident.id}
              onPlaybookUpdate={load}
            />
          ) : !streaming ? (
            <div className="card p-8 text-center text-gray-500 text-sm">
              Click "Generate Playbook" to run the AI triage analysis
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2 text-xs">
      <span className="text-gray-500">{label}</span>
      <span className="text-gray-300 text-right">{value}</span>
    </div>
  );
}
