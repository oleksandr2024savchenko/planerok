"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Bell, Calendar, CalendarClock, Check, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { cn } from "@/lib/cn";
import { formatSchedule, formatTime, sameMinute } from "@/lib/date";
import { isOverdue } from "@/lib/filters";
import { haptic } from "@/lib/telegram";
import type { Task } from "@/lib/types";

interface TaskCardProps {
  task: Task;
  onToggle: (id: number) => void;
  onDelete: (id: number) => void;
}

export function TaskCard({ task, onToggle, onDelete }: TaskCardProps) {
  const overdue = isOverdue(task);
  const highlight = task.priority === "high" && !task.is_completed;
  const schedule = formatSchedule(task);
  const anchor = task.start_time ?? task.deadline;
  const showReminder = Boolean(task.remind_at && !task.is_completed && !sameMinute(task.remind_at, anchor));
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  useEffect(() => {
    if (!confirmingDelete) return;
    const timer = window.setTimeout(() => setConfirmingDelete(false), 4000);
    return () => window.clearTimeout(timer);
  }, [confirmingDelete]);

  return (
    <article
      className={cn(
        "group relative rounded-2xl border bg-zinc-900/60 p-3.5 backdrop-blur-md transition-all duration-300",
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
                "min-w-0 flex-1 text-[15px] font-medium leading-5 tracking-tight text-zinc-100",
                task.is_completed && "text-zinc-500 line-through decoration-zinc-600",
              )}
            >
              {task.title}
              {highlight && (
                <span
                  aria-label="Високий пріоритет"
                  className="ml-2 inline-block size-1.5 translate-y-[-1px] rounded-full bg-fuchsia-400 shadow-[0_0_8px_rgba(232,121,249,0.85)]"
                />
              )}
            </h3>
            {confirmingDelete ? (
              <button
                type="button"
                onClick={() => {
                  haptic.impact("medium");
                  onDelete(task.id);
                }}
                className="shrink-0 rounded-full bg-rose-500/15 px-2.5 py-1 text-[11px] font-medium text-rose-300"
              >
                Видалити
              </button>
            ) : (
              <button
                type="button"
                aria-label="Видалити задачу"
                onClick={() => {
                  haptic.selection();
                  setConfirmingDelete(true);
                }}
                className="flex size-7 shrink-0 items-center justify-center rounded-full text-zinc-600 transition hover:bg-rose-500/10 hover:text-rose-300"
              >
                <Trash2 className="size-3.5" />
              </button>
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
            {schedule && (
              <span className={cn("inline-flex items-center gap-1", overdue && "text-rose-400")}>
                <Calendar className="size-3" />
                {schedule}
              </span>
            )}
            {showReminder && task.remind_at && (
              <span className="inline-flex items-center gap-1">
                <Bell className="size-3" />
                {formatTime(task.remind_at)}
              </span>
            )}
            {task.google_event_id && (
              <span className="inline-flex items-center gap-1 text-zinc-400">
                <CalendarClock className="size-3" />
                Google
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
      onClick={onToggle}
      className="relative mt-0.5 flex size-6 shrink-0 items-center justify-center"
    >
      <motion.span
        className="pointer-events-none flex size-6 items-center justify-center rounded-full border-2"
        animate={{
          backgroundColor: checked ? "rgb(147 51 234)" : "rgba(0,0,0,0)",
          borderColor: checked ? "rgb(168 85 247)" : "rgb(82 82 91)",
          boxShadow: checked ? "0 0 12px rgba(168,85,247,0.55)" : "0 0 0 rgba(0,0,0,0)",
        }}
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
