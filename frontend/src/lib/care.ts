import { getAuthHeaders } from "./auth";

export type CareSuggestionStatus = "pending" | "approved" | "rejected" | "ignored" | "executed" | "failed";
export type CareSuggestionType = "inspection" | "care";

export interface CareConfirmDetail {
  deviceId: string;
  deviceName: string;
  controlId: string;
  controlLabel: string;
  action: string;
  value: unknown;
  missionId: number | null;
}

export interface CareSuggestionRecord {
  id: number;
  suggestionType: CareSuggestionType;
  title: string;
  body: string;
  priority: number;
  status: CareSuggestionStatus;
  aggregatedCount: number;
  aggregatedFrom: Array<number | string>;
  aggregationSources: Array<{
    kind: "rule" | "data_source" | "event";
    id: number | null;
    label: string;
    detail: string;
  }>;
  device: { id: string; name: string; category: string } | null;
  control: { id: string; key: string; label: string } | null;
  actionSpec: Record<string, unknown>;
  missionId: number | null;
  createdAt: string;
  updatedAt: string;
  pushAudit: {
    level: "high" | "medium" | "low";
    pushCount: number;
    lastPushedAt: string | null;
    repeatEligibleAt: string | null;
    ignoredUntil: string | null;
    consoleOnly: boolean;
    suppressReason: "console_only" | "ignored_cooldown" | "repeat_gap" | null;
  };
  canApprove: boolean;
  canReject: boolean;
  canIgnore: boolean;
  canExecute: boolean;
}

export interface CareRuleRecord {
  id: number;
  ruleType: "maintenance" | "health" | "custom";
  deviceCategory: string;
  name: string;
  description: string;
  checkFrequency: string;
  conditionSpec: Record<string, unknown>;
  actionSpec: Record<string, unknown>;
  suggestionTemplate: string;
  priority: number;
  cooldownHours: number;
  isSystemDefault: boolean;
  isActive: boolean;
}

export interface CareDataSourceRecord {
  id: number;
  sourceType: "weather_api" | "ha_entity" | "other";
  name: string;
  config: Record<string, unknown>;
  fetchFrequency: string;
  lastFetchAt: string | null;
  lastData: Record<string, unknown>;
  isActive: boolean;
}

export interface WeatherSnapshot {
  provider?: string;
  temperature?: number | null;
  previous_temperature?: number | null;
  condition?: string;
  humidity?: number | null;
  feels_like?: number | null;
  air_quality?: {
    aqi?: string | number | null;
    category?: string;
    primaryPollutant?: string;
    healthAdvice?: string;
  };
  indices?: Array<{
    name?: string;
    category?: string;
    text?: string;
  }>;
  forecast?: Array<{
    date?: string;
    textDay?: string;
    tempMin?: number | null;
    tempMax?: number | null;
    uvIndex?: string;
    precip?: string;
  }>;
  hourly_forecast?: Array<{
    time?: string;
    text?: string;
    icon?: string;
    temp?: number | null;
    pop?: string;
  }>;
  warnings?: Array<{
    title?: string;
    severity?: string;
    typeName?: string;
    text?: string;
  }>;
  fetched_at?: string;
  previous_fetched_at?: string;
  raw?: Record<string, unknown>;
}

function toRulePayload(payload: Partial<CareRuleRecord>) {
  const next: Record<string, unknown> = {};
  if ("ruleType" in payload) next.rule_type = payload.ruleType;
  if ("deviceCategory" in payload) next.device_category = payload.deviceCategory;
  if ("name" in payload) next.name = payload.name;
  if ("description" in payload) next.description = payload.description;
  if ("checkFrequency" in payload) next.check_frequency = payload.checkFrequency;
  if ("conditionSpec" in payload) next.condition_spec = payload.conditionSpec;
  if ("actionSpec" in payload) next.action_spec = payload.actionSpec;
  if ("suggestionTemplate" in payload) next.suggestion_template = payload.suggestionTemplate;
  if ("priority" in payload) next.priority = payload.priority;
  if ("cooldownHours" in payload) next.cooldown_hours = payload.cooldownHours;
  if ("isActive" in payload) next.is_active = payload.isActive;
  return next;
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

function resolveUrl(path: string) {
  return `${apiBaseUrl}${path}`;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = getAuthHeaders();
  if (init?.headers) {
    Object.assign(headers, init.headers);
  }
  const response = await fetch(resolveUrl(path), { ...init, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error ?? `Request failed: ${response.status}`);
  }
  return payload as T;
}

export async function fetchCareSuggestions(filters: { status?: string; suggestionType?: string; priority?: string } = {}) {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.suggestionType) params.set("suggestion_type", filters.suggestionType);
  if (filters.priority) params.set("priority", filters.priority);
  const query = params.toString();
  return requestJson<{ suggestions: CareSuggestionRecord[] }>(`/api/care/suggestions/${query ? `?${query}` : ""}`);
}

export async function sendCareSuggestionFeedback(id: number, action: "approve" | "reject" | "ignore", reason = "") {
  return requestJson<{ status: string; missionId?: number; suggestion: CareSuggestionRecord }>(`/api/care/suggestions/${id}/feedback/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, reason }),
  });
}

export async function fetchCareConfirmDetail(id: number) {
  return requestJson<{
    suggestion: CareSuggestionRecord;
    confirmDetail: CareConfirmDetail;
  }>(`/api/care/suggestions/${id}/confirm-detail/`);
}

export async function executeCareSuggestion(id: number) {
  return requestJson<{ status: string; result: { success?: boolean; message?: string }; suggestion: CareSuggestionRecord }>(
    `/api/care/suggestions/${id}/execute/`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmed: true }),
    },
  );
}

export async function fetchCareRules() {
  return requestJson<{ rules: CareRuleRecord[] }>("/api/care/rules/");
}

export async function createCareRule(payload: Partial<CareRuleRecord>) {
  return requestJson<{ rule: CareRuleRecord }>("/api/care/rules/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(toRulePayload(payload)),
  });
}

export async function updateCareRule(id: number, payload: Partial<CareRuleRecord>) {
  return requestJson<{ rule: CareRuleRecord }>(`/api/care/rules/${id}/`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(toRulePayload(payload)),
  });
}

export async function deleteCareRule(id: number) {
  return requestJson<{ status: string }>(`/api/care/rules/${id}/`, {
    method: "DELETE",
  });
}

export async function runCareInspection() {
  return requestJson<{ created: CareSuggestionRecord[] }>("/api/care/run-inspection/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
}

function toDataSourcePayload(payload: Partial<CareDataSourceRecord>) {
  const next: Record<string, unknown> = {};
  if ("sourceType" in payload) next.source_type = payload.sourceType;
  if ("name" in payload) next.name = payload.name;
  if ("config" in payload) next.config = payload.config;
  if ("fetchFrequency" in payload) next.fetch_frequency = payload.fetchFrequency;
  if ("isActive" in payload) next.is_active = payload.isActive;
  return next;
}

export async function fetchCareDataSources() {
  return requestJson<{ dataSources: CareDataSourceRecord[] }>("/api/care/data-sources/");
}

export async function createCareDataSource(payload: Partial<CareDataSourceRecord>) {
  return requestJson<{ id: number }>("/api/care/data-sources/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(toDataSourcePayload(payload)),
  });
}

export async function updateCareDataSource(id: number, payload: Partial<CareDataSourceRecord>) {
  return requestJson<{ status: string }>(`/api/care/data-sources/${id}/`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(toDataSourcePayload(payload)),
  });
}

export async function deleteCareDataSource(id: number) {
  return requestJson<{ status: string }>(`/api/care/data-sources/${id}/`, {
    method: "DELETE",
  });
}

export async function fetchCurrentWeather() {
  return requestJson<{ weather: WeatherSnapshot; sourceId: number | null }>("/api/care/weather/current/");
}

export async function refreshCurrentWeather() {
  return requestJson<{ weather: WeatherSnapshot; sourceId: number | null; suggestionId: number | null }>(
    "/api/care/weather/refresh/",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    },
  );
}

export async function reverseGeocode(longitude: number, latitude: number, apiKey: string, endpoint: string) {
  const params = new URLSearchParams({
    longitude: String(longitude),
    latitude: String(latitude),
    api_key: apiKey,
    endpoint,
  });
  return requestJson<{ name: string; adm1: string; adm2: string; country: string; locationId: string }>(
    `/api/care/geocode/?${params.toString()}`,
  );
}
