"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Bell, Calendar, Check } from "lucide-react";

import { cn } from "@/lib/cn";
import { assigneeOf, isFromPartner, useCouple } from "@/lib/couple";
import { useTimerControls } from "@/hooks/useTimer";
import { formatDay, formatDuration, formatTime } from "@/lib/date";
import { isOverdue } from "@/lib/filters";
import { shortOffset } from "@/lib/reminders";
import { haptic } from "@/lib/telegram";
import type { Task } from "@/lib/types";

import { Flower } from "./Flower";

interface TaskCardProps {
  task: Task;
  onToggle: (id: number) => void;
  onOpen?: (id: number) => void;
}

export function TaskCard({ task, onToggle, onOpen }: TaskCardProps) {
  const { meId, partnerName } = useCouple();
  const timerControls = useTimerControls();
  const timerHere = timerControls?.timer?.task_id === task.id ? timerControls.timer : null;
  const overdue = isOverdue(task);
  const highlight = task.priority === "high" && !task.is_completed;
  const when = task.start_time ?? task.deadline;

  return (
    <article
      onClick={
        onOpen
          ? () => {
              haptic.selection();
              onOpen(task.id);
            }
          : undefined
      }
      className={cn(
        onOpen && "cursor-pointer",
        "group relative rounded-2xl border bg-zinc-900/60 p-3.5 backdrop-blur-md transition-[border-color,box-shadow,opacity] duration-300",
        "border-white/5 hover:border-purple-500/40 hover:shadow-[0_0_15px_rgba(168,85,247,0.15)]",
        highlight && "border-purple-500/40 shadow-[0_0_15px_rgba(168,85,247,0.15)]",
        task.is_completed && "opacity-55",
      )}
    >
      <div className="flex gap-3">
        <Checkbox
          checked={task.is_completed}
          onToggle={() => {
            haptic.impact("medium");
            onToggle(task.id);
          }}
        />

        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-2">
            <h3
              className={cn(
                "text-[15px] font-medium leading-5 tracking-tight text-zinc-100",
                task.is_completed && "text-zinc-500 line-through decoration-zinc-600",
              )}
            >
              {task.title}
            </h3>
            {highlight && (
              <span
                aria-label="Високий пріоритет"
                className="mt-1.5 size-1.5 shrink-0 rounded-full bg-fuchsia-400 shadow-[0_0_8px_rgba(232,121,249,0.85)]"
              />
            )}
          </div>

          {task.description && (
            <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-zinc-500">{task.description}</p>
          )}

          <div className="mt-2 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[11px] text-zinc-500">
            {task.is_shared && (
              <span className="rounded-full bg-fuchsia-500/15 px-2 py-0.5 font-medium text-fuchsia-200 shadow-[0_0_10px_rgba(255,45,214,0.35)]">
                Спільне
              </span>
            )}
            {timerHere ? (
              <span className="rounded-full bg-purple-500/15 px-2 py-0.5 font-medium text-purple-200">
                ⏱ {timerHere.kind === "break" ? "перерва" : timerHere.status === "paused" ? "на паузі" : "фокус іде"}
              </span>
            ) : (task.focused_seconds ?? 0) >= 60 ? (
              <span className="rounded-full bg-white/10 px-2 py-0.5 font-medium text-zinc-300">
                ⏱ {formatDuration(task.focused_seconds ?? 0)}
              </span>
            ) : null}
            {assigneeOf(task, meId) === "partner" && (
              <span className="rounded-full bg-fuchsia-500/15 px-2 py-0.5 font-medium text-fuchsia-200">
                Робить: {partnerName}
              </span>
            )}
            {isFromPartner(task, meId) && (
              <span className="rounded-full bg-fuchsia-500/15 px-2 py-0.5 font-medium text-fuchsia-200">
                Від: {partnerName}
              </span>
            )}
            {task.read_only && (
              <span className="rounded-full bg-white/10 px-2 py-0.5 font-medium text-zinc-300">
                {task.source_name ?? "Календар"}
              </span>
            )}
            {task.category && (
              <span className="rounded-full bg-purple-500/10 px-2 py-0.5 font-medium text-purple-300/90">
                #{task.category}
              </span>
            )}
            {when && (
              <span className={cn("inline-flex items-center gap-1", overdue && "text-rose-400")}>
                <Calendar className="size-3" />
                {task.all_day ? `${formatDay(when)} · весь день` : `${formatDay(when)} · ${formatTime(when)}${task.start_time && task.end_time ? `–${formatTime(task.end_time)}` : ""}`}
              </span>
            )}
            {task.remind_at && !task.is_completed && (
              <span className="inline-flex items-center gap-1">
                <Bell className="size-3" />
                {task.remind_before_minutes != null
                  ? task.remind_before_minutes === 0
                    ? "у момент"
                    : `за ${shortOffset(task.remind_before_minutes).toLowerCase()}`
                  : formatTime(task.remind_at)}
              </span>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}

function Checkbox({ checked, onToggle }: { checked: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={checked}
      aria-label={checked ? "Позначити як невиконану" : "Виконати задачу"}
      onClick={(event) => {
        event.stopPropagation();
        onToggle();
      }}
      className="relative mt-0.5 flex size-6 shrink-0 items-center justify-center"
    >
      <motion.span
        className={cn(
          "pointer-events-none flex size-6 items-center justify-center rounded-full border-2 transition-[background-color,border-color,box-shadow] duration-300",
          checked
            ? "border-[var(--accent)] bg-[var(--accent-strong)] shadow-[0_0_12px_var(--accent-glow)]"
            : "border-zinc-600 bg-transparent",
        )}
        whileTap={{ scale: 0.9 }}
        transition={{ type: "spring", stiffness: 420, damping: 32, mass: 0.7 }}
      >
        <AnimatePresence>
          {checked && (
            <motion.span
              key="check"
              initial={{ scale: 0.4, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.4, opacity: 0 }}
              transition={{ type: "spring", stiffness: 420, damping: 28, mass: 0.7 }}
            >
              <Check className="not-pink size-3.5 text-white" strokeWidth={3} />
              <Flower className="pink-only size-5" petal="#ffffff" petalEdge="#ffd1e8" center="#ff2e97" />
            </motion.span>
          )}
        </AnimatePresence>
      </motion.span>
    </button>
  );
}
