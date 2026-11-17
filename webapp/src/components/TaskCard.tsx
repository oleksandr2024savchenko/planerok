"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Bell, Calendar, Check } from "lucide-react";

import { cn } from "@/lib/cn";
import { formatDay, formatTime } from "@/lib/date";
import { isOverdue } from "@/lib/filters";
import { shortOffset } from "@/lib/reminders";
import { haptic } from "@/lib/telegram";
import type { Task } from "@/lib/types";

interface TaskCardProps {
  task: Task;
  onToggle: (id: number) => void;
  onReminder?: (task: Task) => void;
}

export function TaskCard({ task, onToggle, onReminder }: TaskCardProps) {
  const overdue = isOverdue(task);
  const highlight = task.priority === "high" && !task.is_completed;
  const when = task.start_time ?? task.deadline;

  return (
    <article
      className={cn(
        "group relative rounded-2xl border bg-zinc-900/60 p-3.5 backdrop-blur-md transition-all duration-300",
        "border-white/5 hover:border-purple-500/40 hover:shadow-[0_0_15px_rgb(var(--glow)/0.15)]",
        highlight && "border-purple-500/40 shadow-[0_0_15px_rgb(var(--glow)/0.15)]",
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
                className="mt-1.5 size-1.5 shrink-0 rounded-full bg-fuchsia-400 shadow-[0_0_8px_rgb(var(--glow-hot)/0.85)]"
              />
            )}
          </div>

          {task.description && (
            <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-zinc-500">{task.description}</p>
          )}

          <div className="mt-2 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[11px] text-zinc-500">
            {task.category && (
              <span className="rounded-full bg-purple-500/10 px-2 py-0.5 font-medium text-purple-300/90">
                #{task.category}
              </span>
            )}
            {when && (
              <span className={cn("inline-flex items-center gap-1", overdue && "text-rose-400")}>
                <Calendar className="size-3" />
                {formatDay(when)} · {formatTime(when)}
                {task.start_time && task.end_time ? `–${formatTime(task.end_time)}` : ""}
              </span>
            )}
            {!task.is_completed && when && onReminder ? (
              <button
                type="button"
                onClick={() => {
                  haptic.selection();
                  onReminder(task);
                }}
                aria-label="Налаштувати нагадування"
                className={cn(
                  "inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 transition",
                  task.remind_at
                    ? "border-purple-500/20 text-purple-300/90 hover:border-purple-500/50"
                    : "border-dashed border-white/10 text-zinc-500 hover:border-purple-500/40 hover:text-zinc-300",
                )}
              >
                <Bell className="size-3" />
                {reminderLabel(task)}
              </button>
            ) : (
              task.remind_at &&
              !task.is_completed && (
                <span className="inline-flex items-center gap-1">
                  <Bell className="size-3" />
                  {formatTime(task.remind_at)}
                </span>
              )
            )}
          </div>
        </div>
      </div>
    </article>
  );
}

function reminderLabel(task: Task): string {
  if (!task.remind_at) return "Нагадати";
  if (task.remind_before_minutes !== null) {
    return task.remind_before_minutes === 0 ? "у момент" : `за ${shortOffset(task.remind_before_minutes).toLowerCase()}`;
  }
  return formatTime(task.remind_at);
}

function Checkbox({ checked, onToggle }: { checked: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={checked}
      aria-label={checked ? "Позначити як невиконану" : "Виконати задачу"}
      onClick={onToggle}
      className="relative mt-0.5 flex size-6 shrink-0 items-center justify-center"
    >
      <motion.span
        // Colours come from CSS so they follow the active theme; motion only handles the tap scale.
        className={cn(
          "pointer-events-none flex size-6 items-center justify-center rounded-full border-2 transition-[background-color,border-color,box-shadow] duration-200",
          checked
            ? "border-purple-500 bg-purple-600 shadow-[0_0_12px_rgb(var(--glow)/0.55)]"
            : "border-zinc-600 bg-transparent",
        )}
        whileTap={{ scale: 0.86 }}
        transition={{ type: "spring", stiffness: 500, damping: 28 }}
      >
        <AnimatePresence>
          {checked && (
            <motion.span
              key="check"
              initial={{ scale: 0.4, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.4, opacity: 0 }}
              transition={{ type: "spring", stiffness: 520, damping: 24 }}
            >
              <Check className="size-3.5 text-white" strokeWidth={3} />
            </motion.span>
          )}
        </AnimatePresence>
      </motion.span>
    </button>
  );
}
