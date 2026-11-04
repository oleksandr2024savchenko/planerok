"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Bell, Calendar, Flag, X } from "lucide-react";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";

import { cn } from "@/lib/cn";
import { todayKey, viennaToDate } from "@/lib/date";
import { haptic } from "@/lib/telegram";
import { CATEGORIES, type Category, type Priority, type TaskCreate } from "@/lib/types";

const PRIORITIES: { id: Priority; label: string }[] = [
  { id: "low", label: "Низький" },
  { id: "medium", label: "Середній" },
  { id: "high", label: "Високий" },
];

interface AddTaskSheetProps {
  open: boolean;
  onClose: () => void;
  onCreate: (data: TaskCreate) => Promise<unknown>;
}

export function AddTaskSheet({ open, onClose, onCreate }: AddTaskSheetProps) {
  const titleId = useId();
  const titleRef = useRef<HTMLInputElement>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<Category | null>(null);
  const [priority, setPriority] = useState<Priority>("medium");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setTitle("");
    setDescription("");
    setCategory(null);
    setPriority("medium");
    setDate(todayKey());
    setTime("");
    setError(null);
    const frame = requestAnimationFrame(() => titleRef.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = title.trim();
    if (!trimmed) {
      setError("Додай назву задачі");
      titleRef.current?.focus();
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const start = date && time ? viennaToDate(date, time) : null;
      const end = start ? new Date(start.getTime() + 60 * 60 * 1000) : null;
      await onCreate({
        title: trimmed,
        description: description.trim() || null,
        category,
        priority,
        deadline: start ? start.toISOString() : date ? viennaToDate(date, "23:59").toISOString() : null,
        remind_at: start ? start.toISOString() : null,
        start_time: start ? start.toISOString() : null,
        end_time: end ? end.toISOString() : null,
      });
      haptic.notify("success");
      onClose();
    } catch (err) {
      haptic.notify("error");
      setError(err instanceof Error ? err.message : "Не вдалося зберегти задачу");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AnimatePresence>
      {open && (
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

            <form onSubmit={handleSubmit} className="space-y-5 px-5 pb-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 id={titleId} className="text-lg font-semibold tracking-tight text-zinc-100">
                    Нова задача
                  </h2>
                  <p className="mt-0.5 text-sm text-zinc-500">Дата, нагадування та пріоритет — за бажанням</p>
                </div>
                <button
                  type="button"
                  aria-label="Закрити"
                  onClick={onClose}
                  className="flex size-9 items-center justify-center rounded-full border border-white/5 bg-zinc-900 text-zinc-400 transition hover:border-purple-500/30 hover:text-zinc-100"
                >
                  <X className="size-4" />
                </button>
              </div>

              <label className="block space-y-1.5">
                <span className="text-xs font-medium uppercase tracking-wider text-zinc-500">Назва</span>
                <input
                  ref={titleRef}
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="Що потрібно зробити?"
                  maxLength={255}
                  className={fieldClass}
                />
              </label>

              <label className="block space-y-1.5">
                <span className="text-xs font-medium uppercase tracking-wider text-zinc-500">Опис</span>
                <textarea
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  placeholder="Деталі, посилання, контекст…"
                  rows={2}
                  className={`${fieldClass} resize-none`}
                />
              </label>

              <fieldset className="space-y-2">
                <legend className="text-xs font-medium uppercase tracking-wider text-zinc-500">Тег</legend>
                <div className="flex flex-wrap gap-2">
                  {CATEGORIES.map((tag) => {
                    const active = category === tag;
                    return (
                      <button
                        key={tag}
                        type="button"
                        onClick={() => {
                          haptic.selection();
                          setCategory(active ? null : tag);
                        }}
                        className={cn(
                          "rounded-full border px-3 py-1.5 text-sm transition",
                          active
                            ? "border-purple-500/50 bg-purple-500/15 text-purple-100 shadow-[0_0_16px_rgba(168,85,247,0.2)]"
                            : "border-white/5 bg-zinc-900/70 text-zinc-400 hover:border-purple-500/30 hover:text-zinc-200",
                        )}
                      >
                        #{tag}
                      </button>
                    );
                  })}
                </div>
              </fieldset>

              <fieldset className="space-y-2">
                <legend className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-zinc-500">
                  <Flag className="size-3" />
                  Пріоритет
                </legend>
                <div className="grid grid-cols-3 gap-2">
                  {PRIORITIES.map((item) => {
                    const active = priority === item.id;
                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => {
                          haptic.selection();
                          setPriority(item.id);
                        }}
                        className={cn(
                          "rounded-xl border px-2 py-2 text-sm font-medium transition",
                          active
                            ? "border-purple-500/50 bg-purple-500/15 text-purple-100 shadow-[0_0_16px_rgba(168,85,247,0.2)]"
                            : "border-white/5 bg-zinc-900/70 text-zinc-400 hover:border-purple-500/30 hover:text-zinc-200",
                        )}
                      >
                        {item.label}
                      </button>
                    );
                  })}
                </div>
              </fieldset>

              <div className="grid grid-cols-2 gap-3">
                <label className="space-y-1.5">
                  <span className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-zinc-500">
                    <Calendar className="size-3" />
                    Дата
                  </span>
                  <input type="date" value={date} onChange={(event) => setDate(event.target.value)} className={fieldClass} />
                </label>
                <label className="space-y-1.5">
                  <span className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-zinc-500">
                    <Bell className="size-3" />
                    Нагадування
                  </span>
                  <input
                    type="time"
                    value={time}
                    onChange={(event) => setTime(event.target.value)}
                    disabled={!date}
                    className={fieldClass}
                  />
                </label>
              </div>

              {error && <p className="text-sm text-rose-400">{error}</p>}

              <button
                type="submit"
                disabled={submitting || !title.trim()}
                className="w-full rounded-2xl bg-gradient-to-r from-violet-600 to-fuchsia-500 py-3.5 text-sm font-semibold text-white shadow-[0_0_24px_rgba(168,85,247,0.35)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {submitting ? "Зберігаю…" : "Додати задачу"}
              </button>
            </form>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

const fieldClass =
  "w-full rounded-xl border border-white/5 bg-zinc-900/80 px-3 py-2.5 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-600 focus:border-purple-500/50 focus:shadow-[0_0_20px_rgba(168,85,247,0.15)] disabled:opacity-40";
