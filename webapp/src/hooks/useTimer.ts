"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

import { timerApi, USE_MOCKS } from "@/lib/api";
import { haptic } from "@/lib/telegram";
import type { Timer, TimerKind } from "@/lib/types";

export interface FinishedTimer {
  kind: TimerKind;
  minutes: number;
  taskId: number;
  taskTitle: string;
}

export interface TimerControls {
  timer: Timer | null;
  finished: FinishedTimer | null;
  /** Milliseconds left right now; read it every frame, it does not re-render. */
  remainingMs: () => number;
  start: (taskId: number, taskTitle: string, minutes: number, kind?: TimerKind) => Promise<void>;
  pause: () => Promise<void>;
  resume: () => Promise<void>;
  stop: () => Promise<void>;
  dismiss: () => void;
}

const POLL_MS = 20_000;

/**
 * The one live focus/break timer. The server owns it (it keeps running with the app closed and
 * the bot writes when it ends); this hook mirrors it and counts down locally between syncs.
 */
export function useTimer({ enabled, onSettled }: { enabled: boolean; onSettled?: () => void }): TimerControls {
  const [timer, setTimer] = useState<Timer | null>(null);
  const [finished, setFinished] = useState<FinishedTimer | null>(null);
  const endsAt = useRef<number | null>(null);
  const timerRef = useRef<Timer | null>(null);
  const settled = useRef(onSettled);
  settled.current = onSettled;

  const adopt = useCallback((next: Timer | null) => {
    timerRef.current = next;
    endsAt.current = next && next.status === "running" ? Date.now() + next.remaining_seconds * 1000 : null;
    setTimer(next);
  }, []);

  const remainingMs = useCallback(() => {
    const current = timerRef.current;
    if (!current) return 0;
    if (endsAt.current !== null) return Math.max(endsAt.current - Date.now(), 0);
    return current.remaining_seconds * 1000;
  }, []);

  const sync = useCallback(async () => {
    if (USE_MOCKS) return;
    try {
      const server = await timerApi.current();
      const local = timerRef.current;
      // A local countdown that just hit zero waits for its own "finished" panel, not the server.
      if (!server && local && endsAt.current !== null && endsAt.current - Date.now() < 1500) return;
      if (server) setFinished(null);
      adopt(server);
    } catch {
      // Offline: keep counting locally, the next sync fixes it.
    }
  }, [adopt]);

  useEffect(() => {
    if (!enabled) return;
    void sync();
    const timerId = setInterval(() => void sync(), POLL_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") void sync();
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onVisible);
    return () => {
      clearInterval(timerId);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onVisible);
    };
  }, [enabled, sync]);

  // Notice the end locally so the panel switches the moment the ring closes.
  useEffect(() => {
    if (!timer || timer.status !== "running") return;
    const check = setInterval(() => {
      if (endsAt.current === null || endsAt.current > Date.now()) return;
      const done = timerRef.current;
      if (!done) return;
      haptic.notify("success");
      try {
        navigator.vibrate?.([120, 80, 120]);
      } catch {
        // Not every webview vibrates.
      }
      setFinished({
        kind: done.kind,
        minutes: Math.max(Math.round(done.duration_seconds / 60), 1),
        taskId: done.task_id,
        taskTitle: done.task_title,
      });
      adopt(null);
      // The server credits the focus time a moment later; refresh the cards then.
      setTimeout(() => settled.current?.(), 2500);
    }, 250);
    return () => clearInterval(check);
  }, [timer, adopt]);

  const start = useCallback(
    async (taskId: number, taskTitle: string, minutes: number, kind: TimerKind = "focus") => {
      setFinished(null);
      const optimistic: Timer = {
        id: -Date.now(),
        task_id: taskId,
        task_title: taskTitle,
        kind,
        status: "running",
        duration_seconds: minutes * 60,
        remaining_seconds: minutes * 60,
        task_focused_seconds: timerRef.current?.task_focused_seconds ?? 0,
        server_now: new Date().toISOString(),
      };
      adopt(optimistic);
      haptic.impact("medium");
      if (USE_MOCKS) return;
      try {
        adopt(await timerApi.start(taskId, minutes, kind));
      } catch {
        adopt(null);
        haptic.notify("error");
      }
      settled.current?.();
    },
    [adopt],
  );

  const pause = useCallback(async () => {
    const current = timerRef.current;
    if (!current || current.status !== "running") return;
    haptic.selection();
    adopt({ ...current, status: "paused", remaining_seconds: Math.round(remainingMs() / 1000) });
    if (!USE_MOCKS) await timerApi.pause().then(adopt).catch(() => void sync());
  }, [adopt, remainingMs, sync]);

  const resume = useCallback(async () => {
    const current = timerRef.current;
    if (!current || current.status !== "paused") return;
    haptic.selection();
    adopt({ ...current, status: "running" });
    if (!USE_MOCKS) await timerApi.resume().then(adopt).catch(() => void sync());
  }, [adopt, sync]);

  const stop = useCallback(async () => {
    if (!timerRef.current) return;
    haptic.impact("light");
    adopt(null);
    setFinished(null);
    if (!USE_MOCKS) await timerApi.stop().catch(() => undefined);
    settled.current?.();
  }, [adopt]);

  const dismiss = useCallback(() => setFinished(null), []);

  const controls = { timer, finished, remainingMs, start, pause, resume, stop, dismiss };
  // Demo builds only: lets browser tests drive a few-second timer instead of waiting minutes.
  if (USE_MOCKS && typeof window !== "undefined") (window as unknown as { __planerTimer?: TimerControls }).__planerTimer = controls;
  return controls;
}

export const TimerContext = createContext<TimerControls | null>(null);

export function useTimerControls(): TimerControls | null {
  return useContext(TimerContext);
}
