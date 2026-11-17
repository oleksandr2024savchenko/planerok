"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Bell, Calendar, X } from "lucide-react";
import { useEffect, useId, useState } from "react";

import { formatDay, formatTime } from "@/lib/date";
import { reminderAnchor, remindAtFor } from "@/lib/reminders";
import { haptic } from "@/lib/telegram";
import type { Task, TaskUpdate } from "@/lib/types";

import { ReminderPicker } from "./ReminderPicker";

interface ReminderSheetProps {
  task: Task | null;
  onClose: () => void;
  onSave: (id: number, patch: TaskUpdate) => Promise<unknown>;
}

/** Bottom sheet to set "remind me N before" on an existing task or calendar event. */
export function ReminderSheet({ task, onClose, onSave }: ReminderSheetProps) {
  useEffect(() => {
    if (!task) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [task, onClose]);

  return (
    <AnimatePresence>
      {task && <SheetBody key={task.id} task={task} onClose={onClose} onSave={onSave} />}
    </AnimatePresence>
  );
}

function SheetBody({ task, onClose, onSave }: ReminderSheetProps & { task: Task }) {
  const titleId = useId();
  const [value, setValue] = useState<number | null>(() => initialOffset(task));
  const [saving, setSaving] = useState(false);

  const anchor = reminderAnchor(task);
  const dateOnly =
    !task.start_time && anchor !== null && task.deadline !== null && anchor.getTime() !== new Date(task.deadline).getTime();
  const preview = remindAtFor(task, value);
  const absoluteOnly = task.remind_before_minutes === null && task.remind_at;

  async function save() {
    setSaving(true);
    try {
      await onSave(
        task.id,
        value === null ? { remind_before_minutes: null, remind_at: null } : { remind_before_minutes: value },
      );
      haptic.notify("success");
      onClose();
    } catch {
      haptic.notify("error");
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40" role="dialog" aria-modal="true" aria-labelledby={titleId}>
      <motion.button
        type="button"
        aria-label="Закрити"
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      />
      <motion.div
        className="absolute inset-x-0 bottom-0 max-h-[92dvh] overflow-y-auto rounded-t-3xl border border-white/10 border-b-0 bg-zinc-950/95 pb-safe shadow-[0_-20px_80px_rgba(0,0,0,0.55)] backdrop-blur-xl"
        initial={{ y: "100%" }}
        animate={{ y: 0 }}
        exit={{ y: "100%" }}
        transition={{ type: "spring", stiffness: 320, damping: 32 }}
      >
        <div className="mx-auto mb-3 mt-3 h-1 w-10 rounded-full bg-white/15" />
        <div className="space-y-5 px-5 pb-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 id={titleId} className="flex items-center gap-2 text-lg font-semibold tracking-tight text-zinc-100">
                <Bell className="size-4 text-purple-400" />
                Нагадування
              </h2>
              <p className="mt-0.5 truncate text-sm text-zinc-400">{task.title}</p>
              {anchor && (
                <p className="mt-1 flex items-center gap-1.5 text-xs text-zinc-500">
                  <Calendar className="size-3" />
                  {dateOnly
                    ? `${formatDay(anchor.toISOString())} · без часу`
                    : `${formatDay(anchor.toISOString())} · ${formatTime(anchor.toISOString())}`}
                </p>
              )}
            </div>
            <button
              type="button"
              aria-label="Закрити"
              onClick={onClose}
              className="flex size-9 shrink-0 items-center justify-center rounded-full border border-white/5 bg-zinc-900 text-zinc-400 transition hover:border-purple-500/30 hover:text-zinc-100"
            >
              <X className="size-4" />
            </button>
          </div>

          {anchor ? (
            <>
              {absoluteOnly && task.remind_at && (
                <p className="rounded-xl border border-white/5 bg-zinc-900/60 px-3 py-2 text-xs text-zinc-400">
                  Зараз нагадування стоїть на {formatDay(task.remind_at).toLowerCase()} о {formatTime(task.remind_at)}.
                  Обери інтервал, щоб воно рухалося разом із подією.
                </p>
              )}
              <ReminderPicker
                value={value}
                onChange={setValue}
                preview={preview}
                dateOnly={dateOnly}
              />
              <button
                type="button"
                onClick={() => void save()}
                disabled={saving}
                className="w-full rounded-2xl bg-gradient-to-r from-violet-600 to-fuchsia-500 py-3.5 text-sm font-semibold text-white shadow-[0_0_24px_rgb(var(--glow)/0.35)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {saving ? "Зберігаю…" : "Зберегти"}
              </button>
            </>
          ) : (
            <p className="text-sm text-zinc-400">
              У задачі немає дати — нагадування «за … до події» можна поставити після того, як з’явиться дата.
            </p>
          )}
        </div>
      </motion.div>
    </div>
  );
}

/** Existing relative offset, or the gap between an absolute reminder and the event. */
function initialOffset(task: Task): number | null {
  if (task.remind_before_minutes !== null) return task.remind_before_minutes;
  const anchor = reminderAnchor(task);
  if (!task.remind_at || !anchor) return null;
  const minutes = Math.round((anchor.getTime() - new Date(task.remind_at).getTime()) / 60_000);
  return minutes >= 0 ? minutes : null;
}
