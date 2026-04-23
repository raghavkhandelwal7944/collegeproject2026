"use client";

import type { TrafficEntry, TrafficStatus } from "@/lib/types";
import { AnimatePresence, motion } from "framer-motion";
import { Radio } from "lucide-react";
import { useEffect, useRef } from "react";

interface LiveTrafficStreamProps {
  entries: TrafficEntry[];
}

const STATUS_META: Record<
  TrafficStatus,
  { label: string; className: string }
> = {
  CLEARED: {
    label: "CLEARED",
    className:
      "text-emerald-400 border-emerald-800 bg-emerald-950/60",
  },
  REDACTED: {
    label: "REDACTED",
    className:
      "text-amber-400 border-amber-800 bg-amber-950/60",
  },
  BLOCKED: {
    label: "BLOCKED",
    className: "text-red-400 border-red-800 bg-red-950/60",
  },
};

export function LiveTrafficStream({ entries }: LiveTrafficStreamProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries]);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Widget header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-zinc-800 shrink-0">
        <div className="flex items-center gap-2">
          <Radio className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-xs font-medium tracking-widest uppercase text-zinc-400">
            Live Traffic
          </span>
        </div>
        <span className="text-xs text-zinc-600 font-mono">
          {entries.length} entries
        </span>
      </div>

      {/* Scrollable terminal body */}
      <div className="flex-1 overflow-y-auto scrollbar-thin font-mono text-xs px-3 py-2 space-y-0.5">
        <AnimatePresence initial={false}>
          {entries.map((entry) => {
            const meta = STATUS_META[entry.status];
            return (
              <motion.div
                key={entry.id}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.25 }}
                className="flex items-start gap-2 py-1 border-b border-zinc-900/60 group"
              >
                {/* Timestamp */}
                <span className="text-zinc-600 shrink-0 tabular-nums w-20">
                  {entry.timestamp.toLocaleTimeString("en-US", {
                    hour12: false,
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })}
                </span>

                {/* Status badge */}
                <span
                  className={`shrink-0 px-1.5 py-0.5 rounded border text-[10px] font-bold w-[70px] text-center ${meta.className}`}
                >
                  {meta.label}
                </span>

                {/* Request ID */}
                <span className="text-zinc-600 shrink-0 w-28 truncate">
                  {entry.requestId}
                </span>

                {/* Excerpt */}
                <span className="text-zinc-400 flex-1 truncate group-hover:text-zinc-200 transition-colors">
                  {entry.excerpt}
                </span>

                {/* Entities */}
                {entry.entityTypes.length > 0 && (
                  <div className="hidden sm:flex items-center gap-1 shrink-0">
                    {entry.entityTypes.slice(0, 2).map((et) => (
                      <span
                        key={et}
                        className="px-1 py-0.5 text-[9px] rounded bg-amber-950/60 border border-amber-800/50 text-amber-400"
                      >
                        {et}
                      </span>
                    ))}
                  </div>
                )}

                {/* Latency */}
                <span className="text-zinc-600 shrink-0 w-12 text-right tabular-nums">
                  {entry.latencyMs}ms
                </span>
              </motion.div>
            );
          })}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
