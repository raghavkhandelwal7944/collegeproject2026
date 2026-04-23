/**
 * Module-level chat store — survives React component unmounts.
 *
 * Because this lives at module scope (outside any component), messages
 * persist even when the user navigates away from the Playground page.
 * A new chat is only started explicitly via newSession() (New Chat button
 * or logout).
 */
import type { ChatMessage } from "./types";

type Listener = () => void;

let _messages: ChatMessage[] = [];
let _seeded = false;   // true once history has been loaded from the backend
let _loading = false;  // true while waiting for LLM response (survives navigation)
let _sessionId: string = crypto.randomUUID().replace(/-/g, "");

const _listeners = new Set<Listener>();

function notify() {
  _listeners.forEach((l) => l());
}

export const chatStore = {
  /** Returns a stable reference to the current messages array. */
  getMessages(): ChatMessage[] {
    return _messages;
  },

  /** Whether history has been loaded from the backend this session. */
  isSeeded(): boolean {
    return _seeded;
  },

  markSeeded(): void {
    _seeded = true;
  },

  /** The current chat session ID (sent to backend, stored in MongoDB). */
  getSessionId(): string {
    return _sessionId;
  },

  /** Whether the LLM is currently generating a response. */
  getLoading(): boolean {
    return _loading;
  },

  /** Update loading state and notify subscribers so UI stays in sync. */
  setLoading(v: boolean): void {
    _loading = v;
    notify();
  },

  /** Replace entire messages array (used when loading a past session). */
  setMessages(msgs: ChatMessage[]): void {
    _messages = [...msgs];
    notify();
  },

  /** Append one or more messages. */
  push(...msgs: ChatMessage[]): void {
    _messages = [..._messages, ...msgs];
    notify();
  },

  /** Start a brand-new session — fresh UUID, clear messages. */
  newSession(): void {
    _messages = [];
    _seeded = true; // don't auto-reload history after explicit new session
    _loading = false;
    _sessionId = crypto.randomUUID().replace(/-/g, "");
    notify();
  },

  /** Reset everything — called on logout. */
  clearChat(): void {
    _messages = [];
    _seeded = false;
    _loading = false;
    _sessionId = crypto.randomUUID().replace(/-/g, "");
    notify();
  },

  /** Subscribe to changes. Returns an unsubscribe function. */
  subscribe(listener: Listener): () => void {
    _listeners.add(listener);
    return () => _listeners.delete(listener);
  },
};
