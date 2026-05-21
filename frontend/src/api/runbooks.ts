import { apiClient } from "./client";

export interface Runbook {
  id: string;
  name: string;
  description?: string;
  content_type: string;
  chunk_count: number;
  last_indexed_at?: string;
  created_at: string;
}

export interface RunbookListResponse {
  items: Runbook[];
  total: number;
}

export async function fetchRunbooks(): Promise<RunbookListResponse> {
  const { data } = await apiClient.get("/runbooks");
  return data;
}

export async function uploadRunbook(
  file: File,
  name: string,
  description?: string
): Promise<{ message: string; job_id: string; name: string }> {
  const form = new FormData();
  form.append("file", file);
  form.append("name", name);
  if (description) form.append("description", description);

  const { data } = await apiClient.post("/runbooks/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function reindexRunbook(
  id: string
): Promise<{ message: string; job_id: string }> {
  const { data } = await apiClient.post(`/runbooks/${id}/reindex`);
  return data;
}

export async function deleteRunbook(id: string): Promise<void> {
  await apiClient.delete(`/runbooks/${id}`);
}
