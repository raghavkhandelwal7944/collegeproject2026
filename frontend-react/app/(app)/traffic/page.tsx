"use client";

import { getActivityLogs } from "@/lib/api";
import { pageStore } from "@/lib/pageStore";
import type { BackendLog, TrafficEntry } from "@/lib/types";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

const POLL_MS = 5_000;

function mapLog(log: BackendLog, idx: number): TrafficEntry {
  const status: TrafficEntry["status"] = log.blocked
    ? "BLOCKED"
    : log.violation_type
    ? "REDACTED"
    : "CLEARED";
  return {
    id: `backend-${idx}-${log.timestamp}`,
    timestamp: new Date(log.timestamp),
    requestId: `req-${idx}`,
    status,
    entityTypes: log.violation_type ? [log.violation_type] : [],
    latencyMs: null as unknown as number, // real logs have no latency
    excerpt: log.user_input ?? "(no content)",
  };
}

const STATUS_STYLES: Record<TrafficEntry["status"], string> = {
  BLOCKED: "bg-red-500/15 text-red-400 border-red-500/30",
  REDACTED: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  CLEARED: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
};

export default function TrafficPage() {
  const cached = pageStore.isFresh("traffic")
    ? pageStore.get<TrafficEntry[]>("traffic") ?? []
    : [];
  const [entries, setEntries] = useState<TrafficEntry[]>(cached);
  const [error, setError] = useState(false);
  const seenIds = useRef(new Set<string>(cached.map((e) => e.id)));

  useEffect(() => {
    const poll = async () => {
      try {
        const logs: BackendLog[] = await getActivityLogs();
        const mapped = logs
          .map((l, i) => mapLog(l, i))
          .filter((e) => !seenIds.current.has(e.id));
        mapped.forEach((e) => seenIds.current.add(e.id));
        if (mapped.length > 0) {
          setEntries((prev) => {
            const next = [...mapped.reverse(), ...prev].slice(0, 200);
            pageStore.set("traffic", next);
            return next;
          });
        }
        setError(false);
      } catch {
        setError(true);
      }
    };
    poll();
    const id = setInterval(poll, POLL_MS);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="p-6 space-y-4 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-xl font-semibold">Live Traffic</h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            Real requests passing through the firewall
          </p>
        </div>
        {error && (
          <span className="text-xs text-amber-400 border border-amber-500/30 rounded px-2 py-1 bg-amber-500/10">
            backend unreachable — waiting…
          </span>
        )}
      </div>

      {/* Table */}
      <div className="flex-1 overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900 flex flex-col">
        {/* Column headers */}
        <div className="grid grid-cols-[140px_100px_1fr_160px_90px] gap-3 px-4 py-2.5 border-b border-zinc-800 text-[11px] font-semibold uppercase tracking-widest text-zinc-500 shrink-0">
          <span>Timestamp</span>
          <span>Status</span>
          <span>Prompt Excerpt</span>
          <span>Entities Detected</span>
          <span className="text-right">Latency</span>
        </div>

        {/* Rows */}
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          {entries.length === 0 && !error && (
            <div className="flex items-center justify-center h-40 text-zinc-600 text-sm">
              No traffic yet — send a chat message in Playground
            </div>
          )}
          <AnimatePresence initial={false}>
            {entries.map((e) => (
              <motion.div
                key={e.id}
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.25 }}
                className="grid grid-cols-[140px_100px_1fr_160px_90px] gap-3 px-4 py-3 border-b border-zinc-800/60 hover:bg-zinc-800/40 transition-colors items-start"
              >
                {/* Timestamp */}
                <span className="font-mono text-[11px] text-zinc-500 pt-0.5">
                  {new Date(e.timestamp).toLocaleTimeString("en-US", {
                    hour12: false,
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })}
                </span>

                {/* Status badge */}
                <span
                  className={`inline-flex items-center justify-center text-[10px] font-bold px-2 py-0.5 rounded border w-fit ${
                    STATUS_STYLES[e.status]
                  }`}
                >
                  {e.status}
                </span>

                {/* Excerpt */}
                <span className="text-xs text-zinc-300 truncate leading-relaxed">
                  {e.excerpt}
                </span>

                {/* Entities */}
                <div className="flex flex-wrap gap-1">
                  {e.entityTypes.length > 0 ? (
                    e.entityTypes.map((et) => (
                      <span
                        key={et}
                        className="text-[10px] bg-zinc-800 border border-zinc-700 rounded px-1.5 py-0.5 text-zinc-400"
                      >
                        {et}
                      </span>
                    ))
                  ) : (
                    <span className="text-zinc-700 text-[11px]">—</span>
                  )}
                </div>

                {/* Latency */}
                <span className="text-right font-mono text-[11px] text-zinc-500">
                  {e.latencyMs ? `${e.latencyMs}ms` : "—"}
                </span>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
