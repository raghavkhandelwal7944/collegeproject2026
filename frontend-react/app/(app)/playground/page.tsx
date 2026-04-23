"use client";

import { PlaygroundChat } from "@/components/widgets/PlaygroundChat";

export default function PlaygroundPage() {
  return (
    <div className="p-6 h-full flex flex-col">
      <div className="mb-5 shrink-0">
        <h1 className="text-xl font-semibold">Playground</h1>
        <p className="text-sm text-zinc-500 mt-0.5">
          Send prompts through the firewall and see real-time responses
        </p>
      </div>
      <div className="flex-1 min-h-0 rounded-xl border border-zinc-800 bg-zinc-900 overflow-hidden">
        <PlaygroundChat />
      </div>
    </div>
  );
}
