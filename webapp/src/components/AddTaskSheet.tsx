"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Bell, Flag, Users, X } from "lucide-react";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";

import { ChoiceChip, SegmentedControl } from "@/components/SegmentedControl";
import { cn } from "@/lib/cn";
import { clockInput, dateKey, shiftTime, todayKey, viennaToDate } from "@/lib/date";
import { assigneeOf, useCouple, type Assignee } from "@/lib/couple";
import { reminderAnchor, remindAtFor } from "@/lib/reminders";
import { haptic } from "@/lib/telegram";

import { SheetBackdrop, SheetPanel } from "./Sheet";
import { CATEGORIES, type Category, type Priority, type Task, type TaskCreate, type TaskUpdate } from "@/lib/types";

import { FocusStarter } from "./FocusStarter";
import { ReminderPicker } from "./ReminderPicker";
import { WhenPicker } from "./WhenPicker";
import { Reveal } from "./Reveal";

const PRIORITIES: { id: Priority; label: string }[] = [
  { id: "low", label: "Низький" },
  { id: "medium", label: "Середній" },
  { id: "high", label: "Високий" },
];

export interface TaskSlot {
  date: string;
  time: string;
}

interface AddTaskSheetProps {
  open: boolean;
  slot?: TaskSlot | null;
  task?: Task | null;
  onClose: () => void;
  onCreate: (data: TaskCreate) => Promise<unknown>;
  onUpdate: (id: number, data: TaskUpdate) => Promise<unknown>;
  onToggle: (id: number) => void;
  onDelete?: (id: number) => Promise<unknown>;
}

export function AddTaskSheet({
  open,
  slot = null,
  task = null,
  onClose,
  onCreate,
  onUpdate,
  onToggle,
  onDelete,
}: AddTaskSheetProps) {
  const titleId = useId();
  const titleRef = useRef<HTMLInputElement>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<Category | null>(null);
  const [priority, setPriority] = useState<Priority>("medium");
  const [date, setDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { meId, partnerName } = useCouple();
  const [assignee, setAssignee] = useState<Assignee>("me");
  const [initialAssignee, setInitialAssignee] = useState<Assignee>("me");
  /** Minutes before the event; `undefined` until picked, so new tasks follow the start-time default. */
  const [reminder, setReminder] = useState<number | null | undefined>(undefined);
  const [reminderKey, setReminderKey] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);

  useEffect(() => {
    if (!open) return;
    const initialStart = task
      ? task.start_time
        ? clockInput(task.start_time)
        : task.deadline && clockInput(task.deadline) !== "23:59"
          ? clockInput(task.deadline)
          : ""
      : (slot?.time ?? "");
    const when = task?.start_time ?? task?.deadline;
    setDate(task && when ? dateKey(when) : (slot?.date ?? todayKey()));
    setStartTime(initialStart);
    setEndTime(task?.end_time ? clockInput(task.end_time) : initialStart ? shiftTime(initialStart, 60) : "");
    const startAssignee = task ? assigneeOf(task, meId) : "me";
    setAssignee(startAssignee);
    setInitialAssignee(startAssignee);
    setReminder(task ? initialOffset(task) : undefined);
    setReminderKey((current) => current + 1);
    setTitle(task?.title ?? "");
    setDescription(task?.description ?? "");
    setCategory(asCategory(task?.category ?? null));
    setPriority(task?.priority ?? "medium");
    setError(null);
    setConfirmCancel(false);
    const frame = requestAnimationFrame(() => titleRef.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [open, slot?.date, slot?.time, task?.id]);

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

  const schedule = scheduleFor(date, startTime, endTime);
  // New timed events remind at the start, date-only ones not at all (the behaviour before offsets).
  const effectiveReminder = reminder === undefined ? (startTime ? 0 : null) : reminder;
  const reminderPreview = remindAtFor({ start_time: schedule.start, deadline: schedule.deadline }, effectiveReminder);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (task?.read_only) return;
    const trimmed = title.trim();
    if (!trimmed) {
      setError("Додай назву задачі");
      titleRef.current?.focus();
      return;
    }

    if (date && startTime && endTime && endTime <= startTime) {
      setError("Кінець має бути пізніше за початок");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const offset = date ? effectiveReminder : null;
      const payload: TaskCreate = {
        title: trimmed,
        description: description.trim() || null,
        category,
        priority,
        deadline: schedule.deadline,
        start_time: schedule.start,
        end_time: schedule.end,
        is_shared: assignee === "shared",
        // Only a real hand-over is sent on edit, so a save never moves a task by accident.
        ...(!task || assignee !== initialAssignee ? { assignee } : {}),
        remind_before_minutes: offset,
        // With an offset the server derives remind_at and keeps it moving with the event.
        ...(offset === null ? { remind_at: null } : {}),
      };
      if (task) await onUpdate(task.id, payload);
      else await onCreate(payload);
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
          <SheetBackdrop onClose={onClose} />

          <SheetPanel className="overflow-x-clip">
            <div className="mx-auto mb-2 mt-3 h-1 w-10 rounded-full bg-white/15" />

            <form onSubmit={handleSubmit} className="space-y-5 px-4 pb-4 sm:px-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 id={titleId} className="text-lg font-semibold tracking-tight text-zinc-100">
                    {task?.read_only ? "Подія з календаря" : task ? "Подія" : slot ? "Нова подія" : "Нова задача"}
                  </h2>
                  <p className="mt-0.5 text-sm leading-snug text-zinc-500">
                    {task?.read_only
                      ? `${task.is_completed ? "Виконано" : "Можна позначити виконаною"} · ${task.source_name ?? "сторонній календар"}`
                      : task
                        ? "Зміни назву, час і нагадування"
                        : slot
                          ? `Старт ${slot.time} · час можна змінити`
                          : "Коли, нагадування й пріоритет — за бажанням"}
                  </p>
                </div>
                <button
                  type="button"
                  aria-label="Закрити"
                  onClick={onClose}
                  className="flex size-9 shrink-0 items-center justify-center rounded-full border border-white/10 bg-zinc-900 text-zinc-400 hover:border-purple-500/30 hover:text-zinc-100"
                >
                  <X className="size-4" />
                </button>
              </div>

              {task?.read_only ? (
                <div className="space-y-3">
                  <p
                    className={cn(
                      "text-base font-medium text-zinc-100",
                      task.is_completed && "text-zinc-500 line-through decoration-zinc-600",
                    )}
                  >
                    {task.title}
                  </p>
                  {task.description && <p className="text-sm leading-relaxed text-zinc-400">{task.description}</p>}
                  <p className="text-sm text-zinc-500">
                    {task.all_day
                      ? "Весь день"
                      : task.start_time
                        ? `${date || ""} ${startTime}${endTime ? `–${endTime}` : ""}`
                        : "Без часу"}
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      haptic.impact("medium");
                      onToggle(task.id);
                    }}
                    className={cn(
                      "w-full rounded-2xl py-3.5 text-sm font-semibold",
                      task.is_completed
                        ? "border border-white/10 text-zinc-100"
                        : "bg-gradient-to-r from-violet-600 to-fuchsia-500 text-white shadow-[0_0_24px_rgba(168,85,247,0.35)]",
                    )}
                  >
                    {task.is_completed ? "Позначити як невиконану" : "Позначити виконаною"}
                  </button>
                  <button
                    type="button"
                    onClick={onClose}
                    className="w-full rounded-2xl border border-white/10 py-3.5 text-sm font-semibold text-zinc-100"
                  >
                    Закрити
                  </button>
                </div>
              ) : (
              <>
              {task && <FocusStarter task={task} onStarted={onClose} />}
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

              <fieldset className="min-w-0 space-y-2">
                <legend className="text-xs font-medium uppercase tracking-wider text-zinc-500">Тег</legend>
                <div className="grid grid-cols-2 gap-2">
                  {CATEGORIES.map((tag) => {
                    const active = category === tag;
                    return (
                      <ChoiceChip
                        key={tag}
                        layoutId="task-category"
                        anchored
                        active={active}
                        className="w-full"
                        onClick={() => {
                          haptic.selection();
                          setCategory(active ? null : tag);
                        }}
                      >
                        #{tag}
                      </ChoiceChip>
                    );
                  })}
                </div>
              </fieldset>

              <fieldset className="min-w-0 space-y-2">
                <legend className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-zinc-500">
                  <Flag className="size-3 shrink-0" />
                  Пріоритет
                </legend>
                <SegmentedControl
                  fullWidth
                  anchored
                  layoutId="task-priority"
                  value={priority}
                  options={PRIORITIES}
                  onChange={(next) => {
                    haptic.selection();
                    setPriority(next);
                  }}
                />
                {/* Mirrors the backend defaults: NAG_INTERVAL_MINUTES=5, quiet 23:00–08:00. */}
                <Reveal show={priority === "high"}>
                  <p className="pt-1 text-xs leading-snug text-zinc-400">
                    🔥 Додовбувач: після нагадування писатиму кожні 5 хв, доки не виконаєш. Вночі (23:00–08:00) мовчу.
                  </p>
                </Reveal>
              </fieldset>

              <WhenPicker
                date={date}
                start={startTime}
                end={endTime}
                onChange={(nextDate, nextStart, nextEnd) => {
                  setDate(nextDate);
                  setStartTime(nextStart);
                  setEndTime(nextEnd);
                }}
              />

              <Reveal show={Boolean(date)}>
                <fieldset className="min-w-0 space-y-2">
                  <legend className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-zinc-500">
                    <Bell className="size-3 shrink-0" />
                    Нагадати до події
                  </legend>
                  <ReminderPicker
                    key={reminderKey}
                    value={effectiveReminder}
                    onChange={setReminder}
                    preview={reminderPreview}
                    dateOnly={!startTime}
                  />
                </fieldset>
              </Reveal>

              <fieldset className="min-w-0 space-y-2">
                <legend className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-zinc-500">
                  <Users className="size-3 shrink-0" />
                  Хто робить
                </legend>
                <SegmentedControl
                  fullWidth
                  anchored
                  layoutId="task-assignee"
                  value={assignee}
                  options={[
                    { id: "me", label: "Я" },
                    { id: "partner", label: partnerName },
                    { id: "shared", label: "Разом ⚡️" },
                  ]}
                  onChange={(next) => {
                    haptic.selection();
                    setAssignee(next);
                  }}
                />
                <p className="text-xs leading-snug text-zinc-500">
                  {assignee === "partner"
                    ? `${partnerName} отримає задачу й нагадування, а ти дізнаєшся, коли буде виконано.`
                    : assignee === "shared"
                      ? "Побачите обоє, і в обох календарях."
                      : "Лише для тебе."}
                </p>
              </fieldset>

              {error && <p className="text-sm text-rose-400">{error}</p>}

              <button
                type="submit"
                disabled={submitting || !title.trim()}
                className="w-full rounded-2xl bg-gradient-to-r from-violet-600 to-fuchsia-500 py-3.5 text-sm font-semibold text-white shadow-[0_0_24px_rgba(168,85,247,0.35)] hover:brightness-110 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-40"
              >
                {submitting ? "Зберігаю…" : task ? "Зберегти" : "Додати задачу"}
              </button>

              {task && onDelete && (
                <div className="space-y-2">
                  <Reveal show={confirmCancel}>
                    <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-3">
                      <p className="text-sm text-zinc-100">
                        Скасувати «{task.title}»?
                        <span className="mt-0.5 block text-xs text-zinc-400">
                          Подія зникне з планера й Google Calendar, нагадування вимкнуться.
                          {task.is_shared ? " Партнер отримає сповіщення." : ""}
                        </span>
                      </p>
                      <div className="mt-3 grid grid-cols-2 gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            haptic.selection();
                            setConfirmCancel(false);
                          }}
                          className="rounded-xl border border-white/10 py-2.5 text-sm font-medium text-zinc-100"
                        >
                          Ні, лишити
                        </button>
                        <button
                          type="button"
                          disabled={submitting}
                          onClick={async () => {
                            setSubmitting(true);
                            try {
                              await onDelete(task.id);
                              haptic.notify("warning");
                              onClose();
                            } catch (err) {
                              haptic.notify("error");
                              setError(err instanceof Error ? err.message : "Не вдалося скасувати");
                            } finally {
                              setSubmitting(false);
                            }
                          }}
                          className="rounded-xl bg-rose-500 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
                        >
                          Так, скасувати
                        </button>
                      </div>
                    </div>
                  </Reveal>
                  <Reveal show={!confirmCancel}>
                    <button
                      type="button"
                      onClick={() => {
                        haptic.impact("light");
                        setConfirmCancel(true);
                      }}
                      className="w-full rounded-2xl py-2.5 text-sm font-medium text-rose-400 hover:text-rose-300"
                    >
                      Скасувати подію
                    </button>
                  </Reveal>
                </div>
              )}
              </>
              )}
            </form>
          </SheetPanel>
        </div>
      )}
    </AnimatePresence>
  );
}

function scheduleFor(date: string, startTime: string, endTime: string) {
  const start = date && startTime ? viennaToDate(date, startTime).toISOString() : null;
  const end = date && endTime ? viennaToDate(date, endTime).toISOString() : null;
  const deadline = end ?? (date ? viennaToDate(date, "23:59").toISOString() : null);
  return { start, end, deadline };
}

/** Saved offset, or the gap between an older absolute reminder and the event. */
function initialOffset(task: Task): number | null {
  if (task.remind_before_minutes != null) return task.remind_before_minutes;
  const anchor = reminderAnchor(task);
  if (!task.remind_at || !anchor) return null;
  const minutes = Math.round((anchor.getTime() - new Date(task.remind_at).getTime()) / 60_000);
  return minutes >= 0 ? minutes : null;
}

function asCategory(value: string | null): Category | null {
  return CATEGORIES.includes(value as Category) ? (value as Category) : null;
}

const fieldClass =
  "field-focus block w-full min-w-0 max-w-full rounded-xl border border-white/10 bg-zinc-900/80 px-3 py-2.5 text-sm text-zinc-100 outline-none placeholder:text-zinc-600 disabled:opacity-40";
