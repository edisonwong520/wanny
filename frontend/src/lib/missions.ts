export type MissionStatus = "pending" | "approved" | "failed";
export type MissionRisk = "high" | "medium" | "low";
export type MissionSourceType = "shell" | "device_control" | "device_clarification";

export interface MissionTimelineEntry {
  id: string;
  time: string;
  message: string;
}

export interface MissionRecord {
  id: string;
  status: MissionStatus;
  sourceType: MissionSourceType;
  risk: MissionRisk;
  createdAt: string;
  title: string;
  source: string;
  summary: string;
  rawMessage: string;
  intent: string;
  commandPreview: string;
  plan: string[];
  context: string[];
  suggestedReply: string;
  confirmMessage: string;
  resultMessage: string;
  canApprove: boolean;
  canReject: boolean;
  timeline: MissionTimelineEntry[];
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

  const payload = (await response.json().catch(() => ({})));
  if (!response.ok) {
    throw new Error(payload.error ?? `Request failed: ${response.status}`);
  }

  return payload as T;
}

export async function fetchMissions() {
  return requestJson<MissionRecord[]>("/api/comms/missions/");
}

export async function approveMission(id: string) {
  return requestJson<{ status: string; result: string }>(`/api/comms/missions/${id}/approve/`, {
    method: "POST",
  });
}

export async function rejectMission(id: string) {
  return requestJson<{ status: string }>(`/api/comms/missions/${id}/reject/`, {
    method: "POST",
  });
}
