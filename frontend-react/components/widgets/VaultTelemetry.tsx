"use client";

import type { LatencyPoint } from "@/lib/types";
import { animate, useMotionValue } from "framer-motion";
import { KeyRound } from "lucide-react";
import { useEffect, useRef } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip } from "recharts";

interface VaultTelemetryProps {
  tokensToday: number;
  latency: LatencyPoint[];
}

function LatencyTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ value?: number }>;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-xs font-mono text-emerald-400">
      {payload[0].value}ms
    </div>
  );
}

function AnimatedCounter({ value }: { value: number }) {
  const motionValue = useMotionValue(0);
  const displayRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const controls = animate(motionValue, value, {
      duration: 1.2,
      ease: "easeOut",
      onUpdate(latest) {
        if (displayRef.current) {
          displayRef.current.textContent = Math.round(latest).toLocaleString();
        }
      },
    });
    return controls.stop;
  }, [value, motionValue]);

  return (
    <span
      ref={displayRef}
      className="tabular-nums"
      style={{ fontFamily: "var(--font-serif)" }}
    />
  );
}

export function VaultTelemetry({ tokensToday = 0, latency = [] }: VaultTelemetryProps) {
  const avgLatency =
    latency.length > 0
      ? Math.round(
          latency.reduce((s, p) => s + p.latencyMs, 0) / latency.length
        )
      : 0;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Widget header */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-zinc-800 shrink-0">
        <KeyRound className="w-3.5 h-3.5 text-yellow-400" />
        <span className="text-xs font-medium tracking-widest uppercase text-zinc-400">
          Vault Telemetry
        </span>
      </div>

      <div className="flex-1 flex flex-col justify-between p-4 gap-3">
        {/* Large token counter */}
        <div>
          <div className="text-6xl font-bold text-yellow-300 leading-none">
            <AnimatedCounter value={tokensToday} />
          </div>
          <p className="mt-1.5 text-[10px] tracking-widest uppercase text-zinc-500">
            Tokens Secured Today
          </p>
        </div>

        {/* Divider */}
        <div className="border-t border-zinc-800" />

        {/* Latency stats */}
        <div className="flex items-end justify-between">
          <div>
            <p className="text-xl font-semibold text-emerald-400 font-mono tabular-nums">
              {avgLatency}ms
            </p>
            <p className="text-[10px] text-zinc-500 tracking-widest uppercase mt-0.5">
              Avg Latency
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs text-zinc-500">Pipeline overhead</p>
            <p className="text-xs text-zinc-600">20-pt rolling avg</p>
          </div>
        </div>

        {/* Recharts area chart */}
        <div className="h-20 w-full mt-1">
          <ResponsiveContainer width="100%" height={80}>
            <AreaChart data={latency} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="latencyFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <Tooltip content={<LatencyTooltip />} />
              <Area
                type="monotone"
                dataKey="latencyMs"
                stroke="#10b981"
                strokeWidth={1.5}
                fill="url(#latencyFill)"
                dot={false}
                activeDot={{ r: 3, fill: "#10b981" }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
