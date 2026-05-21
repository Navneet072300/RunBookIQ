type Severity = "critical" | "high" | "warning" | "info" | "unknown";

const STYLES: Record<Severity, string> = {
  critical: "bg-red-900/50 text-red-300 border border-red-800",
  high: "bg-orange-900/50 text-orange-300 border border-orange-800",
  warning: "bg-yellow-900/50 text-yellow-300 border border-yellow-800",
  info: "bg-blue-900/50 text-blue-300 border border-blue-800",
  unknown: "bg-gray-800 text-gray-400 border border-gray-700",
};

const DOTS: Record<Severity, string> = {
  critical: "bg-red-400",
  high: "bg-orange-400",
  warning: "bg-yellow-400",
  info: "bg-blue-400",
  unknown: "bg-gray-500",
};

interface Props {
  severity: string;
  pulse?: boolean;
}

export function SeverityBadge({ severity, pulse = false }: Props) {
  const s = (severity?.toLowerCase() ?? "unknown") as Severity;
  const style = STYLES[s] ?? STYLES.unknown;
  const dot = DOTS[s] ?? DOTS.unknown;

  return (
    <span className={`badge ${style}`}>
      <span
        className={`w-1.5 h-1.5 rounded-full mr-1.5 ${dot} ${
          pulse && (s === "critical" || s === "high") ? "animate-pulse" : ""
        }`}
      />
      {s.toUpperCase()}
    </span>
  );
}
