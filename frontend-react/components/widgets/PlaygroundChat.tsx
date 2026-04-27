"use client";

import {
    getChatSessions,
    getSessionMessages,
    sendChat,
    type ChatSession,
} from "@/lib/api";
import { chatStore } from "@/lib/chatStore";
import type { ChatMessage } from "@/lib/types";
import { AnimatePresence, motion } from "framer-motion";
import { Bot, ChevronDown, Plus, Send, User, Zap } from "lucide-react";
import {
    useCallback,
    useEffect,
    useRef,
    useState,
    useSyncExternalStore,
} from "react";

// â”€â”€ Security score heuristics â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const RISK_PATTERNS: [RegExp, number][] = [
  // Prompt injection / jailbreak
  [/ignore (all |previous |prior )?instructions?/i, 35],
  [/jailbreak|DAN mode|act as if/i, 35],
  // Code execution / SQL injection
  [/\bexec\b|\bos\.system\b|subprocess|shell=/i, 25],
  [/drop table|delete from|truncate/i, 25],
  // Hacking / exploitation intent
  [/\bhack\b|\bcrack\b|\bexploit\b|\bbypass\b|\bbrute.?force\b/i, 30],
  [/how to (hack|break into|access|get into|steal|phish)/i, 35],
  [/unauthorized access|gain access to (someone|another|their)/i, 30],
  // Credential / secret leakage
  [/\bpassword\b|\btoken\b|\bapi.?key\b/i, 15],
  [/\bleak\b|\bsteal\b|\bdump\b|\bexfiltrat/i, 25],
  [/my (password|credentials?|secret) is\b/i, 25],
  // Social media / account takeover
  [/\binstagram\b|\bfacebook\b|\btwitter\b|\bsnapchat\b|\btiktok\b/i, 10],
  [/(hack|access|take over|get into).{0,30}(account|profile|instagram|facebook)/i, 35],
  // PII patterns
  [/[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}/i, 10],
  [/\b\d{3}[-.]?\d{3}[-.]?\d{4}\b/, 10],
  [/\b\d{3}-\d{2}-\d{4}\b/, 20],
];

function computeScore(text: string): number {
  if (!text.trim()) return 0;
  let score = 0;
  for (const [re, weight] of RISK_PATTERNS) if (re.test(text)) score += weight;
  return Math.min(100, score);
}
function scoreColor(s: number) {
  return s >= 60 ? "#ef4444" : s >= 30 ? "#d97706" : "#10b981";
}
function scoreLabel(s: number) {
  return s >= 60 ? "HIGH RISK" : s >= 30 ? "MODERATE" : "LOW RISK";
}

function EntityChip({ type }: { type: string }) {
  return (
    <span className="inline-block px-1.5 py-0.5 text-[9px] rounded border border-amber-800/50 bg-amber-950/60 text-amber-400 font-mono">
      {type}
    </span>
  );
}

function CacheHitBadge() {
  return (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[9px] rounded border border-yellow-700/50 bg-yellow-950/60 text-yellow-400 font-mono">
      <Zap className="w-2.5 h-2.5" />
      CACHE HIT
    </span>
  );
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className={`flex gap-2 ${isUser ? "justify-end" : "justify-start"}`}
    >
      {!isUser && (
        <div
          className={`w-6 h-6 shrink-0 rounded-full flex items-center justify-center mt-0.5 ${
            msg.blocked
              ? "bg-red-900/50 border border-red-800"
              : "bg-emerald-900/50 border border-emerald-800"
          }`}
        >
          <Bot className="w-3 h-3 text-emerald-400" />
        </div>
      )}
      <div
        className={`max-w-[80%] rounded-xl px-3 py-2 text-sm leading-relaxed ${
          isUser
            ? "bg-zinc-800 border border-zinc-700 text-zinc-100 rounded-br-sm"
            : msg.blocked
            ? "bg-red-950/50 border border-red-800/60 text-red-200 rounded-bl-sm"
            : msg.error
            ? "bg-zinc-900 border border-zinc-700 text-zinc-400 rounded-bl-sm"
            : "bg-zinc-900 border border-zinc-800 text-zinc-200 rounded-bl-sm"
        }`}
      >
        <p className="whitespace-pre-wrap">{msg.content}</p>
        {msg.firewallMeta && !isUser && (
          <div className="mt-2 pt-2 border-t border-zinc-800/60 flex flex-wrap gap-1.5 items-center">
            {msg.firewallMeta.cache_hit && <CacheHitBadge />}
            {msg.firewallMeta.entities_found?.map((e) => (
              <EntityChip key={e.token} type={e.entity_type} />
            ))}
            <span className="text-[9px] text-zinc-600 font-mono ml-auto">
              {msg.firewallMeta.scan_duration_ms.toFixed(1)}ms scan
            </span>
          </div>
        )}
      </div>
      {isUser && (
        <div className="w-6 h-6 shrink-0 rounded-full bg-zinc-700 border border-zinc-600 flex items-center justify-center mt-0.5">
          <User className="w-3 h-3 text-zinc-400" />
        </div>
      )}
    </motion.div>
  );
}

// ── Main widget ────────────────────────────────────────────────────
export function PlaygroundChat() {
  // Subscribe to the module-level store so messages survive tab switches
  const messages = useSyncExternalStore(
    chatStore.subscribe.bind(chatStore),
    chatStore.getMessages.bind(chatStore),
    chatStore.getMessages.bind(chatStore)
  );
  // Loading lives in the store so it persists when navigating away and back
  const loading = useSyncExternalStore(
    chatStore.subscribe.bind(chatStore),
    chatStore.getLoading.bind(chatStore),
    chatStore.getLoading.bind(chatStore)
  );

  const [input, setInput] = useState("");
  const [score, setScore] = useState(0);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [sessionDropdownOpen, setSessionDropdownOpen] = useState(false);
  const [activeSessionTitle, setActiveSessionTitle] = useState<string | null>(null);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const scoreTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Do not auto-load all old messages on first open.
  // A brand-new chat should start empty; only explicitly opened sessions
  // should load prior history.
  useEffect(() => {
    if (chatStore.isSeeded()) return;
    chatStore.markSeeded();
  }, []);

  // Load/refresh sessions list
  const refreshSessions = useCallback(() => {
    getChatSessions().then(setSessions).catch(() => null);
  }, []);

  useEffect(() => { refreshSessions(); }, [refreshSessions]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node))
        setSessionDropdownOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Real-time security score
  useEffect(() => {
    if (scoreTimer.current) clearTimeout(scoreTimer.current);
    scoreTimer.current = setTimeout(() => setScore(computeScore(input)), 150);
    return () => { if (scoreTimer.current) clearTimeout(scoreTimer.current); };
  }, [input]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleNewChat = () => {
    chatStore.newSession();
    setActiveSessionTitle(null);
    setCurrentSessionId(null);
  };

  const handleLoadSession = async (session: ChatSession) => {
    setSessionDropdownOpen(false);
    setActiveSessionTitle(session.title);
    setCurrentSessionId(session.session_id);
    try {
      const msgs = await getSessionMessages(session.session_id);
      const hydrated: ChatMessage[] = msgs.map((m) => ({ role: m.role, content: m.content }));
      chatStore.setMessages(hydrated);
      chatStore.markSeeded();
    } catch { /* silently ignore */ }
  };

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = input.trim();
      if (!trimmed || loading) return;

      chatStore.push({ role: "user", content: trimmed });
      setInput("");
      chatStore.setLoading(true);

      const priorTurns = chatStore
        .getMessages()
        .slice(0, -1)
        .map((m) => ({ role: m.role as "user" | "assistant", content: m.content }));

      const sessionId = currentSessionId ?? chatStore.getSessionId();

      try {
        const data = await sendChat(trimmed, priorTurns, sessionId);
        chatStore.push({
          role: "assistant",
          content: data.final_response || data.llm_response || "(empty response)",
          firewallMeta: {
            anonymized_prompt: data.anonymized_prompt,
            entities_found: data.entities_found,
            pii_detected: data.pii_detected,
            scan_duration_ms: data.scan_duration_ms,
            gatekeeper_verdict: data.gatekeeper_verdict,
            cache_hit: data.cache_hit,
          },
        });
        refreshSessions();
      } catch (err: unknown) {
        const s = (err as { status?: number })?.status;
        chatStore.push({
          role: "assistant",
          content:
            s === 403 ? "🚫 SECURITY ALERT: This prompt was flagged by the firewall and blocked."
            : s === 400 ? "⚠ POLICY VIOLATION: The safety gate blocked this request."
            : `⚠ ${(err as Error)?.message ?? "Connection error"}`,
          blocked: s === 403 || s === 400,
          error: !s || (s !== 403 && s !== 400),
        });
      } finally {
        chatStore.setLoading(false);
      }
    },
    [input, loading, currentSessionId, refreshSessions]
  );

  const color = scoreColor(score);
  const showScore = input.length > 0;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-zinc-800 shrink-0">
        <div className="flex items-center gap-2">
          <Bot className="w-3.5 h-3.5 text-zinc-400" />
          <span className="text-xs font-medium tracking-widest uppercase text-zinc-400">
            {activeSessionTitle ?? "Playground"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* Sessions dropdown */}
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setSessionDropdownOpen((v) => !v)}
              className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-200 border border-zinc-800 hover:border-zinc-600 rounded px-2 py-1 transition-colors"
            >
              <ChevronDown className="w-3 h-3" />
              History
            </button>
            {sessionDropdownOpen && (
              <div className="absolute right-0 top-full mt-1 w-64 bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl z-50 overflow-hidden">
                {sessions.length === 0 ? (
                  <p className="px-3 py-3 text-xs text-zinc-600 text-center">No saved chats yet</p>
                ) : (
                  <div className="max-h-64 overflow-y-auto scrollbar-thin">
                    {sessions.map((s) => (
                      <button
                        key={s.session_id}
                        onClick={() => handleLoadSession(s)}
                        className="w-full text-left px-3 py-2.5 hover:bg-zinc-800 transition-colors border-b border-zinc-800/50 last:border-0"
                      >
                        <p className="text-xs font-medium text-zinc-200 truncate">
                          {s.title || "Untitled chat"}
                        </p>
                        <p className="text-[10px] text-zinc-500 mt-0.5 truncate">{s.last_message}</p>
                        <p className="text-[9px] text-zinc-700 mt-0.5 font-mono">{s.message_count} msgs</p>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          <span className="text-zinc-700 text-xs">·</span>

          <button
            onClick={handleNewChat}
            className="flex items-center gap-1 text-xs text-zinc-500 hover:text-emerald-400 border border-zinc-800 hover:border-emerald-700/50 rounded px-2 py-1 transition-colors"
          >
            <Plus className="w-3 h-3" />
            New Chat
          </button>
        </div>
      </div>

      {/* Message list */}
      <div className="flex-1 overflow-y-auto scrollbar-thin px-4 py-3 space-y-3">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center opacity-40">
            <Bot className="w-8 h-8 text-zinc-600 mb-2" />
            <p className="text-xs text-zinc-500">
              Type a prompt to test the firewall pipeline.
              <br />
              PII, injections, and cache hits will be shown inline.
            </p>
          </div>
        )}
        <AnimatePresence initial={false}>
          {messages.map((msg, i) => (
            <MessageBubble key={i} msg={msg} />
          ))}
        </AnimatePresence>

        {loading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex justify-start gap-2"
          >
            <div className="w-6 h-6 shrink-0 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center mt-0.5">
              <Bot className="w-3 h-3 text-zinc-500" />
            </div>
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl rounded-bl-sm px-4 py-3 flex gap-1.5 items-center">
              {[0, 0.2, 0.4].map((delay) => (
                <motion.span
                  key={delay}
                  className="w-1.5 h-1.5 rounded-full bg-zinc-600"
                  animate={{ opacity: [0.3, 1, 0.3], y: [0, -3, 0] }}
                  transition={{ repeat: Infinity, duration: 0.9, delay }}
                />
              ))}
            </div>
          </motion.div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="shrink-0 px-4 pb-4 pt-2 border-t border-zinc-800/60">
        <div
          className="mb-2 overflow-hidden"
          style={{ height: showScore ? "28px" : "0px", transition: "height 0.2s ease" }}
        >
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1 bg-zinc-800 rounded-full overflow-hidden">
              <motion.div
                className="h-full rounded-full"
                animate={{ width: `${score}%`, backgroundColor: color }}
                transition={{ duration: 0.3 }}
              />
            </div>
            <span
              className="text-[9px] font-bold tracking-widest tabular-nums shrink-0 w-20 text-right"
              style={{ color }}
            >
              {scoreLabel(score)} {score > 0 ? `${score}` : ""}
            </span>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type a prompt to test the firewall…"
            disabled={loading}
            className="flex-1 bg-zinc-900 border border-zinc-800 text-sm text-zinc-100 placeholder-zinc-600 rounded-lg px-3 py-2 focus:outline-none focus:border-emerald-600/60 transition-colors disabled:opacity-50"
          />
          <button
            type="submit"
            aria-label="Send message"
            disabled={!input.trim() || loading}
            className="shrink-0 p-2 bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-700/50 text-emerald-400 rounded-lg transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
