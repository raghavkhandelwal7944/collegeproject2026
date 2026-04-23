"use client";

import { ToggleSwitch } from "@/components/ui/ToggleSwitch";
import type { PolicyState } from "@/lib/types";
import { motion } from "framer-motion";
import { Settings2 } from "lucide-react";

interface PolicyEngineProps {
  policies: PolicyState;
  onToggle: (key: keyof PolicyState) => void;
}

const POLICIES: {
  key: keyof PolicyState;
  title: string;
  description: string;
}[] = [
  {
    key: "aggressivePii",
    title: "Aggressive PII Redaction",
    description:
      "Extends detection to low-confidence entities and partial matches.",
  },
  {
    key: "semanticCache",
    title: "Semantic Caching",
    description:
      "Return cached responses for semantically similar prompts (≥ 0.95 cosine).",
  },
  {
    key: "codeBlock",
    title: "Code Execution Block",
    description:
      "Flag and quarantine prompts requesting shell commands or code execution.",
  },
];

const containerVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08 } },
};

const rowVariants = {
  hidden: { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};

export function PolicyEngine({ policies, onToggle }: PolicyEngineProps) {
  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Widget header */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-zinc-800 shrink-0">
        <Settings2 className="w-3.5 h-3.5 text-zinc-400" />
        <span className="text-xs font-medium tracking-widest uppercase text-zinc-400">
          Policy Engine
        </span>
      </div>

      <motion.div
        className="flex-1 flex flex-col justify-evenly px-4 py-4 gap-3"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        {POLICIES.map(({ key, title, description }) => (
          <motion.div
            key={key}
            variants={rowVariants}
            className="flex items-center justify-between gap-4 p-3 rounded-lg border border-zinc-800 bg-zinc-900/50 hover:border-zinc-700 transition-colors"
          >
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-zinc-200 truncate">
                {title}
              </p>
              <p className="text-xs text-zinc-500 mt-0.5 leading-relaxed">
                {description}
              </p>
            </div>
            <ToggleSwitch
              checked={policies[key]}
              onChange={() => onToggle(key)}
            />
          </motion.div>
        ))}
      </motion.div>
    </div>
  );
}
