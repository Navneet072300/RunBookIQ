import { useState } from "react";

interface SettingField {
  key: string;
  label: string;
  placeholder: string;
  type?: "text" | "password" | "url";
  description?: string;
}

const SOURCE_SETTINGS: { title: string; icon: string; fields: SettingField[] }[] = [
  {
    title: "Kubernetes",
    icon: "⎈",
    fields: [
      {
        key: "k8s_namespace",
        label: "Watch Namespace",
        placeholder: "default",
        description: "Namespace to watch for events (leave blank for all)",
      },
      {
        key: "k8s_kubeconfig",
        label: "Kubeconfig Path",
        placeholder: "/path/to/.kube/config (leave blank for in-cluster)",
      },
    ],
  },
  {
    title: "Prometheus / Alertmanager",
    icon: "🔥",
    fields: [
      {
        key: "alertmanager_url",
        label: "Alertmanager URL",
        placeholder: "http://alertmanager:9093",
        type: "url",
        description: "Webhook receiver or polling endpoint",
      },
    ],
  },
  {
    title: "Zabbix",
    icon: "📊",
    fields: [
      {
        key: "zabbix_api_url",
        label: "Zabbix API URL",
        placeholder: "http://zabbix.internal/api_jsonrpc.php",
        type: "url",
      },
      { key: "zabbix_user", label: "Username", placeholder: "Admin" },
      {
        key: "zabbix_password",
        label: "Password",
        placeholder: "••••••••",
        type: "password",
      },
    ],
  },
  {
    title: "Slack",
    icon: "💬",
    fields: [
      {
        key: "slack_webhook_url",
        label: "Webhook URL",
        placeholder: "https://hooks.slack.com/services/...",
        type: "url",
        description: "Incoming webhook for incident notifications",
      },
    ],
  },
];

export function SettingsPage() {
  const [values, setValues] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);

  const handleChange = (key: string, value: string) => {
    setValues((v) => ({ ...v, [key]: value }));
    setSaved(false);
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    // In production, these would POST to a settings API
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <div className="p-6 space-y-6 max-w-2xl">
      <h1 className="text-xl font-semibold text-gray-100">Settings</h1>

      <div className="card p-4 border-brand-800/50 bg-brand-950/20">
        <p className="text-sm text-brand-300">
          Configuration is managed via environment variables in production.
          Values entered here are for local testing only and are not persisted.
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {SOURCE_SETTINGS.map((group) => (
          <div key={group.title} className="card p-5 space-y-4">
            <div className="flex items-center gap-2">
              <span className="text-xl">{group.icon}</span>
              <h2 className="text-sm font-semibold text-gray-200">
                {group.title}
              </h2>
            </div>
            {group.fields.map((field) => (
              <div key={field.key}>
                <label className="label">{field.label}</label>
                <input
                  type={field.type ?? "text"}
                  className="input"
                  placeholder={field.placeholder}
                  value={values[field.key] ?? ""}
                  onChange={(e) => handleChange(field.key, e.target.value)}
                />
                {field.description && (
                  <p className="text-xs text-gray-600 mt-1">{field.description}</p>
                )}
              </div>
            ))}
          </div>
        ))}

        <div className="flex items-center gap-3">
          <button type="submit" className="btn-primary">
            Save Settings
          </button>
          {saved && (
            <span className="text-sm text-green-400">Settings saved (local only)</span>
          )}
        </div>
      </form>

      {/* About section */}
      <div className="card p-5 space-y-3">
        <h2 className="text-sm font-semibold text-gray-200">About RunbookIQ</h2>
        <div className="space-y-1 text-xs text-gray-500">
          <p>Version: 1.0.0</p>
          <p>AI Model: gemini-2.0-flash (free via aistudio.google.com)</p>
          <p>Embeddings: text-embedding-004 (768 dims)</p>
          <p>Vector DB: PostgreSQL + pgvector (HNSW index)</p>
        </div>
      </div>
    </div>
  );
}
