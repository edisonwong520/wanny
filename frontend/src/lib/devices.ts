export interface DeviceRoomRecord {
  id: string;
  name: string;
  climate: string;
  summary: string;
  device_count: number;
  anomaly_count: number;
}

export interface DeviceSnapshotRecord {
  id: string;
  room_id: string | null;
  room_name: string;
  name: string;
  category: string;
  status: "online" | "attention" | "offline";
  telemetry: string;
  note: string;
  capabilities: string[];
  last_seen: string | null;
  controls: DeviceControlRecord[];
}

export interface DeviceControlRecord {
  id: string;
  parent_id: string | null;
  source_type: "ha_entity" | "mijia_property" | "mijia_action";
  kind: "sensor" | "toggle" | "range" | "enum" | "action" | "text";
  key: string;
  label: string;
  group_label: string;
  writable: boolean;
  value: unknown;
  unit: string;
  options: Array<{ label: string; value: unknown }>;
  range_spec: { min?: number; max?: number; step?: number };
  action_params: Record<string, unknown>;
  updated_at: string;
}

export interface DeviceAnomalyRecord {
  id: string;
  room_id: string | null;
  device_id: string | null;
  severity: "high" | "medium" | "low";
  title: string;
  body: string;
  recommendation: string;
  updated_at: string;
}

export interface DeviceAutomationRuleRecord {
  id: string;
  room_id: string | null;
  device_id: string | null;
  mode_key: string;
  mode_label: string;
  target: string;
  condition: string;
  decision: "ask" | "always" | "never";
  rationale: string;
  updated_at: string;
}

export interface DeviceDashboardSnapshot {
  refreshed_at: string | null;
  source: string;
  last_trigger: string;
  pending_refresh: boolean;
  last_error: string;
  has_snapshot: boolean;
  rooms: DeviceRoomRecord[];
  devices: DeviceSnapshotRecord[];
  anomalies: DeviceAnomalyRecord[];
  rules: DeviceAutomationRuleRecord[];
}

interface DeviceDashboardResponse {
  status: string;
  snapshot: DeviceDashboardSnapshot;
}

import { getAuthHeaders } from "./auth";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

function resolveUrl(path: string) {
  return `${apiBaseUrl}${path}`;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = getAuthHeaders();
  if (init?.headers) {
    Object.assign(headers, init.headers);
  }

  const response = await fetch(resolveUrl(path), {
    ...init,
    headers,
  });

  const payload = (await response.json().catch(() => ({}))) as { error?: string };
  if (!response.ok) {
    throw new Error(payload.error ?? `Request failed: ${response.status}`);
  }

  return payload as T;
}

export async function fetchDeviceDashboard() {
  return requestJson<DeviceDashboardResponse>("/api/devices/dashboard/");
}

export async function refreshDeviceDashboard() {
  return requestJson<DeviceDashboardResponse>("/api/devices/dashboard/refresh/", {
    method: "POST",
  });
}

export async function executeDeviceControl(
  deviceId: string,
  controlId: string,
  payload: {
    action?: string;
    value?: unknown;
  },
) {
  return requestJson<DeviceDashboardResponse>(
    `/api/devices/${encodeURIComponent(deviceId)}/controls/${encodeURIComponent(controlId)}/`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
  );
}
