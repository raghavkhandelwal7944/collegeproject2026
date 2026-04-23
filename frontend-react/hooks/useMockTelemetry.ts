"use client";

import type { LatencyPoint, TrafficEntry, TrafficStatus } from "@/lib/types";
import { useCallback, useEffect, useRef, useState } from "react";

// ── Seeds ─────────────────────────────────────────
const ENTITY_POOL = [
  ["PERSON"],
  ["EMAIL_ADDRESS"],
  ["PERSON", "PHONE_NUMBER"],
  ["CREDIT_CARD"],
  ["LOCATION"],
  ["US_SSN"],
  ["EMAIL_ADDRESS", "PERSON"],
  [],
];

const EXCERPTS = [
  "My name is <PERSON_a4f2> and I need help with…",
  "Please send the invoice to <EMAIL_a1b2>…",
  "The patient at <LOCATION_cc12> presented with…",
  "Can you write a Python script to list files?",
  "Summarize the annual report for Q3…",
  "Translate this paragraph to French…",
  "My SSN is <US_SSN_f3a9>, please verify…",
  "Ignore all prior instructions and…",
  "Generate SQL to drop the users table…",
  "What is the capital of France?",
];

function randomChoice<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function randomBetween(min: number, max: number) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function fmtTime(d: Date) {
  return d.toLocaleTimeString("en-US", { hour12: false });
}

function makeEntry(): TrafficEntry {
  const entityTypes = randomChoice(ENTITY_POOL);
  const hasPii = entityTypes.length > 0;
  const rand = Math.random();
  let status: TrafficStatus;
  if (rand < 0.08) status = "BLOCKED";
  else if (hasPii) status = "REDACTED";
  else status = "CLEARED";

  return {
    id: crypto.randomUUID(),
    timestamp: new Date(),
    requestId: `req_${crypto.randomUUID().slice(0, 8)}`,
    status,
    entityTypes,
    latencyMs: randomBetween(28, 95),
    excerpt: randomChoice(EXCERPTS),
  };
}

function makeLatencyPoint(): LatencyPoint {
  return {
    time: fmtTime(new Date()),
    latencyMs: randomBetween(32, 58),
  };
}

function seedLatency(count: number): LatencyPoint[] {
  const now = Date.now();
  return Array.from({ length: count }, (_, i) => {
    const d = new Date(now - (count - i) * 3000);
    return { time: fmtTime(d), latencyMs: randomBetween(32, 58) };
  });
}

function seedTraffic(count: number): TrafficEntry[] {
  return Array.from({ length: count }, () => {
    const e = makeEntry();
    e.timestamp = new Date(
      Date.now() - randomBetween(5000, 90000)
    );
    return e;
  }).sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
}

// ── Hook ──────────────────────────────────────────
export interface MockTelemetry {
  trafficStream: TrafficEntry[];
  latencyHistory: LatencyPoint[];
  tokensSecuredToday: number;
}

const MAX_TRAFFIC = 50;
const MAX_LATENCY = 20;

export function useMockTelemetry(): MockTelemetry {
  const [trafficStream, setTrafficStream] = useState<TrafficEntry[]>(() =>
    seedTraffic(12)
  );
  const [latencyHistory, setLatencyHistory] = useState<LatencyPoint[]>(() =>
    seedLatency(MAX_LATENCY)
  );
  const [tokensSecuredToday, setTokensSecuredToday] = useState<number>(() =>
    randomBetween(1200, 2400)
  );

  // Deterministic random walk for latency (avoid wild jumps)
  const latencyRef = useRef(42);

  const tickTraffic = useCallback(() => {
    setTrafficStream((prev) => {
      const next = [...prev, makeEntry()];
      return next.length > MAX_TRAFFIC ? next.slice(-MAX_TRAFFIC) : next;
    });
  }, []);

  const tickLatency = useCallback(() => {
    const delta = (Math.random() - 0.5) * 8; // ±4 ms walk
    latencyRef.current = Math.max(
      28,
      Math.min(80, latencyRef.current + delta)
    );
    setLatencyHistory((prev) => {
      const next = [
        ...prev,
        { time: fmtTime(new Date()), latencyMs: Math.round(latencyRef.current) },
      ];
      return next.length > MAX_LATENCY ? next.slice(-MAX_LATENCY) : next;
    });
  }, []);

  const tickTokens = useCallback(() => {
    setTokensSecuredToday((prev) => prev + randomBetween(1, 4));
  }, []);

  useEffect(() => {
    const t1 = setInterval(tickTraffic, 2000);
    const t2 = setInterval(tickLatency, 3000);
    const t3 = setInterval(tickTokens, 5000);
    return () => {
      clearInterval(t1);
      clearInterval(t2);
      clearInterval(t3);
    };
  }, [tickTraffic, tickLatency, tickTokens]);

  return { trafficStream, latencyHistory, tokensSecuredToday };
}
