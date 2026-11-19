"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Coffee, Pause, Play, Square, X } from "lucide-react";
import { useEffect, useRef } from "react";

import type { TimerControls } from "@/hooks/useTimer";
import { useMotionProfile } from "@/hooks/useMotionProfile";
import { SHEET_MOTION } from "@/lib/motion";

const RING = 2 * Math.PI * 21;

function clock(ms: number): string {
  const total = Math.ceil(ms / 1000);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  const mm = String(minutes).padStart(hours ? 2 : 1, "0");
  return `${hours ? `${hours}:` : ""}${mm}:${String(seconds).padStart(2, "0")}`;
}

/** Floating timer above the list: countdown ring, pause/resume, stop, then break or another round. */
export function TimerDock({ controls }: { controls: TimerControls }) {
  const { timer, finished } = controls;
  const profile = useMotionProfile();
  const reduce = useReducedMotion();
  const timing = SHEET_MOTION[profile];
  const show = Boolean(timer || finished);

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          key="dock"
          className="timer-dock fixed left-4 right-24 z-30 rounded-2xl border border-white/10 bg-zinc-900 p-2.5 shadow-[0_12px_40px_rgba(0,0,0,0.45)]"
          style={{ bottom: "max(1.25rem, calc(env(safe-area-inset-bottom) + 0.75rem))", willChange: "transform" }}
          initial={{ transform: "translateY(140%)", opacity: 0 }}
          animate={{ transform: "translateY(0%)", opacity: 1, transition: reduce ? { duration: 0 } : timing.open }}
          exit={{ transform: "translateY(140%)", opacity: 0, transition: reduce ? { duration: 0 } : timing.close }}
          role="status"
          aria-live="polite"
        >
          <AnimatePresence mode="wait" initial={false}>
            {timer ? (
              <motion.div
                key={`live-${timer.id > 0 ? timer.id : "new"}`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
              >
                <LiveTimer controls={controls} />
              </motion.div>
            ) : finished ? (
              <motion.div key="done" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
                <FinishedTimer controls={controls} />
              </motion.div>
            ) : null}
          </AnimatePresence>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function LiveTimer({ controls }: { controls: TimerControls }) {
  const { timer, remainingMs, pause, resume, stop } = controls;
  const textRef = useRef<HTMLSpanElement>(null);
  const ringRef = useRef<SVGCircleElement>(null);
  const running = timer?.status === "running";
  const total = (timer?.duration_seconds ?? 1) * 1000;

  // Paint the countdown straight into the DOM each frame: smooth ring, no React re-render per tick.
  useEffect(() => {
    let frame = 0;
    const paint = () => {
      const left = remainingMs();
      if (textRef.current) textRef.current.textContent = clock(left);
      if (ringRef.current) ringRef.current.style.strokeDashoffset = String(RING * (left / total));
      if (running) frame = requestAnimationFrame(paint);
    };
    paint();
    return () => cancelAnimationFrame(frame);
  }, [remainingMs, running, total, timer?.id, timer?.status]);

  if (!timer) return null;
  const isBreak = timer.kind === "break";

  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={() => void (running ? pause() : resume())}
        aria-label={running ? "Пауза" : "Продовжити"}
        className="relative flex size-12 shrink-0 items-center justify-center rounded-full text-zinc-100"
      >
        <svg viewBox="0 0 48 48" className="absolute inset-0 size-12 -rotate-90" aria-hidden>
          <circle cx="24" cy="24" r="21" fill="none" stroke="currentColor" strokeOpacity="0.14" strokeWidth="3.5" />
          <circle
            ref={ringRef}
            cx="24"
            cy="24"
            r="21"
            fill="none"
            stroke="var(--accent-strong)"
            strokeWidth="3.5"
            strokeLinecap="round"
            strokeDasharray={RING}
            style={{ filter: "drop-shadow(0 0 4px var(--accent-glow))" }}
          />
        </svg>
        {running ? <Pause className="size-4" fill="currentColor" /> : <Play className="ml-0.5 size-4" fill="currentColor" />}
      </button>

      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-zinc-500">
          {isBreak ? <Coffee className="size-3" /> : null}
          {isBreak ? "Перерва" : running ? "Фокус" : "Пауза"}
        </p>
        <p className="font-mono text-2xl font-semibold leading-7 tabular-nums text-zinc-100">
          <span ref={textRef} />
        </p>
        <p className="truncate text-xs text-zinc-400">{timer.task_title}</p>
      </div>

      <button
        type="button"
        onClick={() => void stop()}
        aria-label="Зупинити таймер"
        className="flex size-9 shrink-0 items-center justify-center rounded-full border border-white/10 text-zinc-400 hover:text-zinc-100"
      >
        <Square className="size-3.5" fill="currentColor" />
      </button>
    </div>
  );
}

function FinishedTimer({ controls }: { controls: TimerControls }) {
  const { finished, start, dismiss } = controls;
  if (!finished) return null;
  const { kind, minutes, taskId, taskTitle } = finished;
  const options =
    kind === "focus"
      ? [
          { label: "☕ 5 хв", minutes: 5, kind: "break" as const },
          { label: "☕ 10 хв", minutes: 10, kind: "break" as const },
          { label: `▶ Ще ${minutes}`, minutes, kind: "focus" as const },
        ]
      : [
          { label: "▶ 20 хв", minutes: 20, kind: "focus" as const },
          { label: "▶ 25 хв", minutes: 25, kind: "focus" as const },
          { label: "▶ 40 хв", minutes: 40, kind: "focus" as const },
        ];

  return (
    <div className="space-y-2">
      <div className="flex items-start gap-2">
        <p className="min-w-0 flex-1 text-sm leading-snug text-zinc-100">
          {kind === "focus" ? `✅ ${minutes} хв фокусу позаду. Перерва?` : "☕ Перерва скінчилась. Повертаємось?"}
          <span className="block truncate text-xs text-zinc-500">{taskTitle}</span>
        </p>
        <button
          type="button"
          onClick={dismiss}
          aria-label="Закрити"
          className="flex size-7 shrink-0 items-center justify-center rounded-full text-zinc-500 hover:text-zinc-100"
        >
          <X className="size-4" />
        </button>
      </div>
      <div className="grid grid-cols-3 gap-1.5">
        {options.map((option) => (
          <button
            key={option.label}
            type="button"
            onClick={() => void start(taskId, taskTitle, option.minutes, option.kind)}
            className="rounded-xl border border-white/10 bg-white/[0.04] px-1 py-2 text-xs font-medium text-zinc-100 hover:border-purple-500/40"
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}
