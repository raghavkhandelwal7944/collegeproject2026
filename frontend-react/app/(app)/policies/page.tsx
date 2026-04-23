"use client";

import { PolicyEngine } from "@/components/widgets/PolicyEngine";
import { getPolicies, setPolicies, type PolicyData } from "@/lib/api";
import { pageStore } from "@/lib/pageStore";
import { useEffect, useState } from "react";

type FrontendPolicies = {
  aggressivePii: boolean;
  semanticCache: boolean;
  codeBlock: boolean;
};

function toBackend(p: FrontendPolicies): PolicyData {
  return {
    aggressive_pii: p.aggressivePii,
    semantic_cache: p.semanticCache,
    code_block: p.codeBlock,
  };
}

function fromBackend(d: PolicyData): FrontendPolicies {
  return {
    aggressivePii: d.aggressive_pii,
    semanticCache: d.semantic_cache,
    codeBlock: d.code_block,
  };
}

const DEFAULT: FrontendPolicies = {
  aggressivePii: false,
  semanticCache: true,
  codeBlock: false,
};

export default function PoliciesPage() {
  const cached = pageStore.isFresh("policies")
    ? pageStore.get<FrontendPolicies>("policies") ?? DEFAULT
    : DEFAULT;
  const [policies, setPoliciesState] = useState<FrontendPolicies>(cached);
  const [loading, setLoading] = useState(!pageStore.isFresh("policies"));
  const [saved, setSaved] = useState(false);

  // Load from MySQL on mount (skip if cache is fresh)
  useEffect(() => {
    if (pageStore.isFresh("policies")) return;
    getPolicies()
      .then((d) => {
        const parsed = fromBackend(d);
        setPoliciesState(parsed);
        pageStore.set("policies", parsed);
      })
      .catch(() => null)
      .finally(() => setLoading(false));
  }, []);

  const handleToggle = async (key: keyof FrontendPolicies) => {
    const next = { ...policies, [key]: !policies[key] };
    setPoliciesState(next);
    try {
      await setPolicies(toBackend(next));
      pageStore.set("policies", next);
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    } catch {
      // revert on error
      setPoliciesState(policies);
    }
  };

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Policies</h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            Configure firewall enforcement rules
          </p>
        </div>
        {saved && (
          <span className="text-xs text-emerald-400 border border-emerald-700/40 rounded px-2 py-1 bg-emerald-500/10">
            ✓ Saved
          </span>
        )}
      </div>

      {loading ? (
        <div className="space-y-3 max-w-2xl">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-16 rounded-xl border border-zinc-800 bg-zinc-900/50 animate-pulse"
            />
          ))}
        </div>
      ) : (
        <div className="max-w-2xl">
          <PolicyEngine policies={policies} onToggle={handleToggle} />
        </div>
      )}
    </div>
  );
}
