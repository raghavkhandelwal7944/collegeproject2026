"use client";

import { VaultTelemetry } from "@/components/widgets/VaultTelemetry";
import { useMockTelemetry } from "@/hooks/useMockTelemetry";
import { getStats } from "@/lib/api";
import { pageStore } from "@/lib/pageStore";
import type { BackendStats } from "@/lib/types";
import { Activity, BarChart3, ShieldCheck, Zap } from "lucide-react";
import { useEffect, useState } from "react";

function StatCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-5 flex items-center gap-4">
      <div className={`p-2.5 rounded-lg ${color}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-xs text-zinc-500 uppercase tracking-widest">{label}</p>
        <p className="text-2xl font-bold tabular-nums mt-0.5">{value}</p>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [mounted, setMounted] = useState(false);
  const [stats, setStats] = useState<BackendStats | null>(
    pageStore.isFresh("dashboard") ? pageStore.get<BackendStats>("dashboard") ?? null : null
  );
  const { tokensSecuredToday, latencyHistory } = useMockTelemetry();

  useEffect(() => {
    const load = () =>
      getStats()
        .then((s) => {
          setStats(s);
          pageStore.set("dashboard", s);
        })
        .catch(() => null);
    // Skip fetch on first load if cache is still fresh
    if (!pageStore.isFresh("dashboard")) load();
    const id = setInterval(load, 10_000);
    return () => clearInterval(id);
  }, []);

  // Prevent hydration mismatch — mock data uses Math.random() which differs SSR vs CSR
  useEffect(() => { setMounted(true); }, []);

  const blockRate = stats
    ? stats.percentage_blocked.toFixed(1) + "%"
    : "—";

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Overview</h1>
        <p className="text-sm text-zinc-500 mt-0.5">System health and live statistics</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={Activity}
          label="Total Requests"
          value={stats?.total_requests ?? "—"}
          color="bg-blue-500/15 text-blue-400"
        />
        <StatCard
          icon={ShieldCheck}
          label="Block Rate"
          value={blockRate}
          color="bg-emerald-500/15 text-emerald-400"
        />
        <StatCard
          icon={Zap}
          label="Blocked"
          value={stats?.total_blocked ?? "—"}
          color="bg-violet-500/15 text-violet-400"
        />
        <StatCard
          icon={BarChart3}
          label="Avg Latency"
          value={mounted && latencyHistory.length > 0 ? `${Math.round(latencyHistory.reduce((s, p) => s + p.latencyMs, 0) / latencyHistory.length)}ms` : "—"}
          color="bg-amber-500/15 text-amber-400"
        />
      </div>

      {/* Vault Telemetry chart */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
        <p className="text-xs text-zinc-500 uppercase tracking-widest mb-4">Token Vault Telemetry</p>
        <VaultTelemetry tokensToday={mounted ? tokensSecuredToday : 0} latency={mounted ? latencyHistory : []} />
      </div>
    </div>
  );
}
