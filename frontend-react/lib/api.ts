/**
 * Typed API helpers.
 *
 * Login / signup / logout hit our Next.js proxy routes (/api/auth/*).
 * All other calls go through the generic passthrough (/api/proxy/*),
 * which attaches the httpOnly cookie token as Authorization: Bearer.
 */
import type { BackendChatResponse, BackendLog, BackendStats } from "./types";

const AUTH = "/api/auth";
const PROXY = "/api/proxy";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { ...init, credentials: "include" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw Object.assign(new Error(body?.detail ?? `HTTP ${res.status}`), {
      status: res.status,
      body,
    });
  }
  return res.json() as Promise<T>;
}

// ── Auth ──────────────────────────────────────────
export async function login(username: string, password: string) {
  return request<{ ok: boolean }>(`${AUTH}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
}

export async function signup(
  username: string,
  password: string,
  first_name: string,
  last_name: string,
  email: string
) {
  return request<{ ok: boolean }>(`${AUTH}/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password, first_name, last_name, email }),
  });
}

export async function logout() {
  return request<{ ok: boolean }>(`${AUTH}/logout`, { method: "POST" });
}

// ── Chat pipeline ─────────────────────────────────
export async function sendChat(
  prompt: string,
  messages: { role: "user" | "assistant"; content: string }[] = [],
  session_id?: string
): Promise<BackendChatResponse> {
  return request<BackendChatResponse>(`${PROXY}/api/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, messages, ...(session_id ? { chat_session_id: session_id } : {}) }),
  });
}

// ── Dashboard telemetry ───────────────────────────
export async function getStats(): Promise<BackendStats> {
  return request<BackendStats>(`${PROXY}/stats`);
}

export async function getActivityLogs(): Promise<BackendLog[]> {
  return request<BackendLog[]>(`${PROXY}/activity_logs`);
}

// ── Policies ──────────────────────────────────────
export interface PolicyData {
  aggressive_pii: boolean;
  semantic_cache: boolean;
  code_block: boolean;
}

export async function getPolicies(): Promise<PolicyData> {
  return request<PolicyData>(`${PROXY}/api/v1/policies`);
}

export async function setPolicies(data: PolicyData): Promise<PolicyData> {
  return request<PolicyData>(`${PROXY}/api/v1/policies`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

// ── Chat history ──────────────────────────────────
export interface ConversationTurn {
  user_message: string;
  bot_response: string;
  timestamp: string;
}

export async function getChatHistory(): Promise<ConversationTurn[]> {
  return request<ConversationTurn[]>(`${PROXY}/history`);
}

// ── Chat sessions ─────────────────────────────────
export interface ChatSession {
  session_id: string;
  title: string;
  last_message: string;
  message_count: number;
}

export interface SessionMessage {
  role: "user" | "assistant";
  content: string;
}

export async function getChatSessions(): Promise<ChatSession[]> {
  return request<ChatSession[]>(`${PROXY}/chat/sessions`);
}

export async function getSessionMessages(session_id: string): Promise<SessionMessage[]> {
  return request<SessionMessage[]>(`${PROXY}/history/${session_id}`);
}
