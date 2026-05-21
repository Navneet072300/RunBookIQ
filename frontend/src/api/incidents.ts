import { apiClient } from "./client";

export interface IncidentListItem {
  id: string;
  title: string;
  severity: "critical" | "high" | "warning" | "info" | "unknown";
  status: "open" | "acknowledged" | "resolved" | "suppressed";
  source: string;
  opened_at: string;
  resolved_at?: string;
  has_playbook: boolean;
}

export interface PlaybookStep {
  step: number;
  action: string;
  description: string;
  command?: string;
  expected_outcome?: string;
}

export interface Playbook {
  id: string;
  incident_id: string;
  probable_cause?: string;
  severity_assessment?: string;
  runbook_steps: PlaybookStep[];
  escalation_path?: string;
  auto_remediation_suggestion?: string;
  remediation_approved: boolean;
  remediation_executed_at?: string;
  remediation_result?: string;
  model_used?: string;
  created_at: string;
}

export interface IncidentDetail extends IncidentListItem {
  tenant_id: string;
  description?: string;
  assigned_to?: string;
  labels: Record<string, string>;
  alert_fingerprints: string[];
  acknowledged_at?: string;
  playbook?: Playbook;
}

export interface IncidentListResponse {
  items: IncidentListItem[];
  total: number;
  page: number;
  page_size: number;
}

export async function fetchIncidents(params?: {
  page?: number;
  page_size?: number;
  status?: string;
  severity?: string;
}): Promise<IncidentListResponse> {
  const { data } = await apiClient.get("/incidents", { params });
  return data;
}

export async function fetchIncident(id: string): Promise<IncidentDetail> {
  const { data } = await apiClient.get(`/incidents/${id}`);
  return data;
}

export async function updateIncident(
  id: string,
  update: { status?: string; assigned_to?: string }
): Promise<IncidentDetail> {
  const { data } = await apiClient.patch(`/incidents/${id}`, update);
  return data;
}

export async function approveRemediation(incidentId: string) {
  const { data } = await apiClient.post(`/remediation/${incidentId}/approve`);
  return data;
}

export async function dryRunRemediation(incidentId: string) {
  const { data } = await apiClient.post(`/remediation/${incidentId}/dry-run`);
  return data;
}
