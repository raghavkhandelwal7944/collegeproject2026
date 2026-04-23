// ── Traffic stream ─────────────────────────────────
export type TrafficStatus = "CLEARED" | "REDACTED" | "BLOCKED";

export interface TrafficEntry {
  id: string;
  timestamp: Date;
  requestId: string;
  status: TrafficStatus;
  /** PII entity types found, e.g. ["PERSON", "EMAIL_ADDRESS"] */
  entityTypes: string[];
  /** Wall-clock latency for the full pipeline, ms */
  latencyMs: number;
  /** Truncated prompt excerpt (anonymized) */
  excerpt: string;
}

export interface LatencyPoint {
  /** Label shown on x-axis ("12:04:01") */
  time: string;
  latencyMs: number;
}

// ── Policy Engine ──────────────────────────────────
export interface PolicyState {
  aggressivePii: boolean;
  semanticCache: boolean;
  codeBlock: boolean;
}

// ── Playground / Chat ──────────────────────────────
export interface AnonymizedEntity {
  original_text: string;
  token: string;
  entity_type: string;
  start: number;
  end: number;
  score: number;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  firewallMeta?: {
    anonymized_prompt: string;
    entities_found: AnonymizedEntity[];
    pii_detected: boolean;
    scan_duration_ms: number;
    gatekeeper_verdict: string;
    cache_hit: boolean;
  };
  blocked?: boolean;
  error?: boolean;
}

// ── Backend API response shapes ────────────────────
export interface BackendChatResponse {
  anonymized_prompt: string;
  entities_found: AnonymizedEntity[];
  pii_detected: boolean;
  scan_duration_ms: number;
  gatekeeper_verdict: string;
  llm_response: string;
  final_response: string;
  cache_hit: boolean;
}

export interface BackendStats {
  total_requests: number;
  total_blocked: number;
  percentage_blocked: number;
}

export interface BackendLog {
  timestamp: string;
  blocked: boolean;
  violation_type: string;
  user_input: string;
}
