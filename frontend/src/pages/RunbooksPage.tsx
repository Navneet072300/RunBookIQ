import { useEffect, useRef, useState } from "react";
import {
  deleteRunbook,
  fetchRunbooks,
  reindexRunbook,
  uploadRunbook,
  type Runbook,
} from "../api/runbooks";

export function RunbooksPage() {
  const [runbooks, setRunbooks] = useState<Runbook[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetchRunbooks();
      setRunbooks(res.items);
    } catch {}
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file || !name.trim()) return;
    setUploading(true);
    setUploadMsg(null);
    try {
      await uploadRunbook(file, name.trim(), description.trim() || undefined);
      setUploadMsg("Runbook upload accepted — indexing in progress...");
      setName("");
      setDescription("");
      if (fileRef.current) fileRef.current.value = "";
      setTimeout(load, 3000);
    } catch (e: any) {
      setUploadMsg(`Error: ${e.message}`);
    }
    setUploading(false);
  };

  const handleReindex = async (id: string) => {
    try {
      await reindexRunbook(id);
      setUploadMsg("Re-indexing started...");
      setTimeout(load, 3000);
    } catch (e: any) {
      setUploadMsg(`Error: ${e.message}`);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Delete runbook "${name}"?`)) return;
    try {
      await deleteRunbook(id);
      setRunbooks((r) => r.filter((rb) => rb.id !== id));
    } catch (e: any) {
      setUploadMsg(`Error: ${e.message}`);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-xl font-semibold text-gray-100">Runbooks</h1>

      {/* Upload form */}
      <div className="card p-5">
        <h2 className="text-sm font-semibold text-gray-300 mb-4">
          Upload Runbook
        </h2>
        <form onSubmit={handleUpload} className="space-y-3">
          <div>
            <label className="label">Runbook Name *</label>
            <input
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., K8s OOMKill Runbook"
              required
            />
          </div>
          <div>
            <label className="label">Description</label>
            <input
              className="input"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
            />
          </div>
          <div>
            <label className="label">File *</label>
            <input
              ref={fileRef}
              type="file"
              accept=".md,.txt,.pdf,.docx"
              required
              className="block w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-3 file:rounded file:border-0 file:text-xs file:font-medium file:bg-gray-800 file:text-gray-300 hover:file:bg-gray-700 cursor-pointer"
            />
            <p className="text-xs text-gray-600 mt-1">Markdown, PDF, DOCX, or plain text (max 50MB)</p>
          </div>
          <button
            type="submit"
            disabled={uploading}
            className="btn-primary"
          >
            {uploading ? "Uploading..." : "Upload & Index"}
          </button>
        </form>
        {uploadMsg && (
          <p
            className={`mt-3 text-sm ${
              uploadMsg.startsWith("Error") ? "text-red-400" : "text-green-400"
            }`}
          >
            {uploadMsg}
          </p>
        )}
      </div>

      {/* Runbook list */}
      <div>
        <h2 className="text-sm font-semibold text-gray-400 mb-3">
          Indexed Runbooks ({runbooks.length})
        </h2>
        {loading ? (
          <div className="text-sm text-gray-600 py-8 text-center">Loading...</div>
        ) : runbooks.length === 0 ? (
          <div className="card p-8 text-center text-gray-500 text-sm">
            No runbooks indexed yet
          </div>
        ) : (
          <div className="space-y-2">
            {runbooks.map((rb) => (
              <RunbookRow
                key={rb.id}
                runbook={rb}
                onReindex={() => handleReindex(rb.id)}
                onDelete={() => handleDelete(rb.id, rb.name)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function RunbookRow({
  runbook,
  onReindex,
  onDelete,
}: {
  runbook: Runbook;
  onReindex: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="card p-4 flex items-center gap-4">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-100 truncate">{runbook.name}</p>
        {runbook.description && (
          <p className="text-xs text-gray-500 truncate mt-0.5">{runbook.description}</p>
        )}
        <div className="flex items-center gap-3 mt-1">
          <span className="text-xs text-gray-600">{runbook.chunk_count} chunks</span>
          <span className="text-xs text-gray-600">{runbook.content_type}</span>
          {runbook.last_indexed_at && (
            <span className="text-xs text-gray-600">
              Indexed {new Date(runbook.last_indexed_at).toLocaleDateString()}
            </span>
          )}
        </div>
      </div>
      <div className="flex gap-2 flex-shrink-0">
        <button
          onClick={onReindex}
          className="btn-ghost text-xs border border-gray-700"
        >
          Re-index
        </button>
        <button onClick={onDelete} className="btn-danger text-xs">
          Delete
        </button>
      </div>
    </div>
  );
}
