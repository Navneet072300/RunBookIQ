import { formatDistanceToNow } from "date-fns";
import { Link } from "react-router-dom";
import type { IncidentListItem } from "../api/incidents";
import { SeverityBadge } from "./SeverityBadge";

const SOURCE_ICONS: Record<string, string> = {
  kubernetes: "⎈",
  prometheus: "🔥",
  zabbix: "📊",
  manual: "✋",
};

const STATUS_STYLES: Record<string, string> = {
  open: "bg-red-900/30 text-red-400 border border-red-900",
  acknowledged: "bg-yellow-900/30 text-yellow-400 border border-yellow-900",
  resolved: "bg-green-900/30 text-green-400 border border-green-900",
  suppressed: "bg-gray-800 text-gray-500 border border-gray-700",
};

interface Props {
  incident: IncidentListItem;
}

export function IncidentCard({ incident }: Props) {
  const sourceIcon = SOURCE_ICONS[incident.source] ?? "⚠️";
  const statusStyle = STATUS_STYLES[incident.status] ?? STATUS_STYLES.open;
  const timeAgo = formatDistanceToNow(new Date(incident.opened_at), {
    addSuffix: true,
  });

  return (
    <Link to={`/incidents/${incident.id}`} className="block group">
      <div className="card p-4 hover:border-gray-700 transition-colors group-hover:bg-gray-900/80">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3 min-w-0">
            <span className="text-xl mt-0.5 flex-shrink-0" title={incident.source}>
              {sourceIcon}
            </span>
            <div className="min-w-0">
              <p className="text-sm font-medium text-gray-100 truncate leading-snug">
                {incident.title}
              </p>
              <p className="text-xs text-gray-500 mt-0.5">{timeAgo}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <SeverityBadge
              severity={incident.severity}
              pulse={incident.status === "open"}
            />
            <span className={`badge ${statusStyle}`}>
              {incident.status}
            </span>
          </div>
        </div>

        {incident.has_playbook && (
          <div className="mt-2 flex items-center gap-1 text-xs text-brand-400">
            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
              <path d="M9 4.804A7.968 7.968 0 005.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 015.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0114.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0014.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 11-2 0V4.804z" />
            </svg>
            Playbook ready
          </div>
        )}
      </div>
    </Link>
  );
}
