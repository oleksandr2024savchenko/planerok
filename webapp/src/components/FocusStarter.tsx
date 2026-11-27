"use client";

import { Timer as TimerIcon } from "lucide-react";
import { useState } from "react";

import { ChoiceChip } from "@/components/SegmentedControl";
import { useTimerControls } from "@/hooks/useTimer";
import { formatDuration } from "@/lib/date";
import { haptic } from "@/lib/telegram";
import type { Task } from "@/lib/types";

const PRESETS = [15, 20, 25, 40, 60];

/** «Фокус» block in the task sheet: pick minutes, start, and see how much time already went in. */
export function FocusStarter({ task, onStarted }: { task: Task; onStarted: () => void }) {
  const controls = useTimerControls();
  const [minutes, setMinutes] = useState(25);
  if (!controls) return null;

  const focused = task.focused_seconds ?? 0;
  const planned =
    task.start_time && task.end_time
      ? Math.max((new Date(task.end_time).getTime() - new Date(task.start_time).getTime()) / 1000, 0)
      : 0;
  const runningHere = controls.timer?.task_id === task.id;

  return (
    <section className="space-y-2.5 rounded-2xl border border-white/10 bg-white/[0.04] p-3">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-zinc-500">
          <TimerIcon className="size-3.5" />
          Фокус-таймер
        </h3>
        <p className="text-xs text-zinc-400">
          {focused > 0
            ? `Вже ${formatDuration(focused)}${planned ? ` з ${formatDuration(planned)}` : ""}`
            : planned
              ? `Заплановано ${formatDuration(planned)}`
              : ""}
        </p>
      </div>

      {planned > 0 && (
        <div className="h-1.5 overflow-hidden rounded-full bg-zinc-800/80">
          <div
            className="h-full rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-500 transition-[width] duration-500"
            style={{ width: `${Math.min((focused / planned) * 100, 100)}%` }}
          />
        </div>
      )}

      {runningHere ? (
        <p className="text-sm text-zinc-300">⏱ Таймер на цю задачу вже йде — керуй ним унизу екрана.</p>
      ) : (
        <>
          <div className="flex flex-wrap gap-1.5">
            {PRESETS.map((value) => (
              <ChoiceChip
                key={value}
                layoutId="focus-minutes"
                anchored
                active={minutes === value}
                onClick={() => {
                  haptic.selection();
                  setMinutes(value);
                }}
              >
                {value} хв
              </ChoiceChip>
            ))}
          </div>
          <button
            type="button"
            onClick={() => {
              void controls.start(task.id, task.title, minutes);
              onStarted();
            }}
            className="choice-fill w-full rounded-xl py-2.5 text-sm font-semibold text-white"
          >
            ▶ Почати фокус · {minutes} хв
          </button>
        </>
      )}
    </section>
  );
}
