import { useEffect, useState } from "react";
import { fetchIncidents, type IncidentListItem } from "../api/incidents";
import { IncidentCard } from "../components/IncidentCard";

const STATUSES = ["", "open", "acknowledged", "resolved", "suppressed"];
const SEVERITIES = ["", "critical", "high", "warning", "info"];

export function IncidentsPage() {
  const [incidents, setIncidents] = useState<IncidentListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [severity, setSeverity] = useState("");
  const [loading, setLoading] = useState(false);
  const PAGE_SIZE = 20;

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetchIncidents({
        page,
        page_size: PAGE_SIZE,
        status: status || undefined,
        severity: severity || undefined,
      });
      setIncidents(res.items);
      setTotal(res.total);
    } catch {}
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, [page, status, severity]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-100">
          Incidents
          {total > 0 && (
            <span className="ml-2 text-sm text-gray-500 font-normal">({total})</span>
          )}
        </h1>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          className="input w-40"
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>{s || "All statuses"}</option>
          ))}
        </select>
        <select
          value={severity}
          onChange={(e) => { setSeverity(e.target.value); setPage(1); }}
          className="input w-40"
        >
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>{s || "All severities"}</option>
          ))}
        </select>
      </div>

      {/* List */}
      {loading ? (
        <div className="text-sm text-gray-600 py-12 text-center">Loading...</div>
      ) : incidents.length === 0 ? (
        <div className="card p-12 text-center">
          <p className="text-gray-500">No incidents found</p>
        </div>
      ) : (
        <div className="space-y-2">
          {incidents.map((i) => (
            <IncidentCard key={i.id} incident={i} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <button
            onClick={() => setPage(page - 1)}
            disabled={page === 1}
            className="btn-ghost text-sm disabled:opacity-30"
          >
            ← Previous
          </button>
          <span className="text-sm text-gray-500">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage(page + 1)}
            disabled={page === totalPages}
            className="btn-ghost text-sm disabled:opacity-30"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
