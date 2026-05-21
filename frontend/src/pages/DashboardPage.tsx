import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchIncidents, type IncidentListItem } from "../api/incidents";
import { IncidentCard } from "../components/IncidentCard";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "#ef4444",
  high: "#f97316",
  warning: "#eab308",
  info: "#3b82f6",
  unknown: "#6b7280",
};

function useIncidents() {
  const [incidents, setIncidents] = useState<IncidentListItem[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const res = await fetchIncidents({ page_size: 50 });
      setIncidents(res.items);
    } catch {}
    setLoading(false);
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 30_000);
    return () => clearInterval(t);
  }, []);

  return { incidents, loading };
}

export function DashboardPage() {
  const { incidents, loading } = useIncidents();

  const open = incidents.filter((i) => i.status === "open");
  const acked = incidents.filter((i) => i.status === "acknowledged");
  const resolved = incidents.filter((i) => i.status === "resolved");

  const severityData = Object.entries(
    incidents.reduce(
      (acc, i) => ({ ...acc, [i.severity]: (acc[i.severity] ?? 0) + 1 }),
      {} as Record<string, number>
    )
  ).map(([name, value]) => ({ name, value }));

  const statusData = [
    { name: "Open", value: open.length, color: "#ef4444" },
    { name: "Acked", value: acked.length, color: "#eab308" },
    { name: "Resolved", value: resolved.length, color: "#22c55e" },
  ];

  const mttrHours =
    resolved.length > 0
      ? (
          resolved
            .filter((i) => i.resolved_at)
            .reduce((sum, i) => {
              const diff =
                new Date(i.resolved_at!).getTime() -
                new Date(i.opened_at).getTime();
              return sum + diff / 3_600_000;
            }, 0) / resolved.length
        ).toFixed(1)
      : "—";

  const recentOpen = open.slice(0, 8);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-100">Dashboard</h1>
        <Link to="/incidents" className="text-sm text-brand-400 hover:text-brand-300">
          View all incidents →
        </Link>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard label="Open Incidents" value={open.length} color="text-red-400" />
        <KpiCard label="Acknowledged" value={acked.length} color="text-yellow-400" />
        <KpiCard label="Resolved (total)" value={resolved.length} color="text-green-400" />
        <KpiCard label="Avg MTTR (hrs)" value={mttrHours} color="text-brand-400" />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card p-4">
          <h2 className="text-sm font-medium text-gray-400 mb-4">
            Incidents by Severity
          </h2>
          {severityData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={severityData} barCategoryGap="40%">
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis
                  dataKey="name"
                  tick={{ fill: "#9ca3af", fontSize: 11 }}
                  axisLine={false}
                />
                <YAxis tick={{ fill: "#9ca3af", fontSize: 11 }} axisLine={false} />
                <Tooltip
                  contentStyle={{
                    background: "#111827",
                    border: "1px solid #374151",
                    borderRadius: 6,
                    color: "#f3f4f6",
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {severityData.map((entry) => (
                    <Cell
                      key={entry.name}
                      fill={SEVERITY_COLORS[entry.name] ?? "#6b7280"}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <Empty />
          )}
        </div>

        <div className="card p-4">
          <h2 className="text-sm font-medium text-gray-400 mb-4">
            Status Breakdown
          </h2>
          {incidents.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={statusData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={80}
                  paddingAngle={3}
                  dataKey="value"
                  label={({ name, value }) =>
                    value > 0 ? `${name} ${value}` : ""
                  }
                  labelLine={false}
                >
                  {statusData.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: "#111827",
                    border: "1px solid #374151",
                    borderRadius: 6,
                    color: "#f3f4f6",
                    fontSize: 12,
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <Empty />
          )}
        </div>
      </div>

      {/* Live incident feed */}
      <div>
        <h2 className="text-sm font-medium text-gray-400 mb-3">
          Open Incidents
        </h2>
        {loading ? (
          <div className="text-sm text-gray-600 py-8 text-center">Loading...</div>
        ) : recentOpen.length === 0 ? (
          <div className="card p-8 text-center">
            <p className="text-gray-500 text-sm">No open incidents</p>
          </div>
        ) : (
          <div className="space-y-2">
            {recentOpen.map((incident) => (
              <IncidentCard key={incident.id} incident={incident} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function KpiCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number | string;
  color: string;
}) {
  return (
    <div className="card p-4">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
    </div>
  );
}

function Empty() {
  return (
    <div className="flex items-center justify-center h-[200px] text-gray-600 text-sm">
      No data yet
    </div>
  );
}
