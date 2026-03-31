export interface ProviderRecord {
  platform: string;
  display_name: string;
  display_name_zh: string;
  category: string;
  auth_mode: string;
  configured: boolean;
  status: string;
  is_active: boolean;
  has_credentials: boolean;
  payload_keys: string[];
  payload_preview: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
}

export interface AuthorizationSession {
  id: string;
  platform: string;
  auth_kind: "link" | "qr" | "form";
  status: "pending" | "scanned" | "completed" | "expired" | "failed";
  title: string;
  instruction: string;
  detail: string;
  action_url: string | null;
  image_url: string | null;
  verification_url: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  is_terminal: boolean;
}

interface ProvidersResponse {
  status: string;
  providers: ProviderRecord[];
}

interface ProviderAuthorizationResponse {
  status: string;
  provider: ProviderRecord;
  session: AuthorizationSession | null;
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

export async function fetchProviders() {
  return requestJson<ProvidersResponse>("/api/providers/auth/");
}

export async function fetchAuthorizationSession(platform: string) {
  return requestJson<ProviderAuthorizationResponse>(`/api/providers/auth/${platform}/authorize/`);
}

export async function startAuthorization(
  platform: string,
  options: {
    force?: boolean;
    payload?: Record<string, unknown>;
  } = {},
) {
  return requestJson<ProviderAuthorizationResponse>(`/api/providers/auth/${platform}/authorize/`, {
    method: "POST",
    body: JSON.stringify({
      force: options.force ?? false,
      payload: options.payload ?? undefined,
    }),
  });
}

export async function disconnectProvider(platform: string) {
  return requestJson<{ status: string; message: string }>(`/api/providers/auth/${platform}/`, {
    method: "DELETE",
  });
}
