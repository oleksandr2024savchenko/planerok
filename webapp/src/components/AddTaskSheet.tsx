"use client";

import { Bell, Calendar, Flag, FolderOpen, Repeat } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { cn } from "@/lib/cn";
import { todayKey, viennaToDate, weekdayIndex } from "@/lib/date";
import { haptic } from "@/lib/telegram";
import { CATEGORIES, canWrite, type Category, type Priority, type Space, type TaskCreate } from "@/lib/types";

import { BottomSheet, chipClass, fieldClass } from "./BottomSheet";
import { SpaceDot } from "./SpacePills";

const PRIORITIES: { id: Priority; label: string }[] = [
  { id: "low", label: "Низький" },
  { id: "medium", label: "Середній" },
  { id: "high", label: "Високий" },
];

type RepeatId = "none" | "daily" | "weekdays" | "weekly" | "monthly";

const REPEATS: { id: RepeatId }[] = [
  { id: "none" },
  { id: "daily" },
  { id: "weekdays" },
  { id: "weekly" },
  { id: "monthly" },
];

const WEEKDAY_CODES = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"];
const WEEKDAY_SHORT = ["пн", "вт", "ср", "чт", "пт", "сб", "нд"];

function repeatLabel(id: RepeatId, date: string): string {
  const day = date || todayKey();
  switch (id) {
    case "none":
      return "Без повтору";
    case "daily":
      return "Щодня";
    case "weekdays":
      return "По буднях";
    case "weekly":
      return `Щотижня (${WEEKDAY_SHORT[weekdayIndex(day)]})`;
    case "monthly":
      return `Щомісяця, ${Number(day.slice(8, 10))}-го`;
  }
}

/** Builds the RRULE subset the backend understands, anchored to the chosen date. */
function repeatRule(id: RepeatId, date: string): string | null {
  const day = date || todayKey();
  switch (id) {
    case "none":
      return null;
    case "daily":
      return "FREQ=DAILY";
    case "weekdays":
      return "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR";
    case "weekly":
      return `FREQ=WEEKLY;BYDAY=${WEEKDAY_CODES[weekdayIndex(day)]}`;
    case "monthly":
      return `FREQ=MONTHLY;BYMONTHDAY=${Number(day.slice(8, 10))}`;
  }
}

export interface TaskSlot {
  date: string;
  time: string;
}

interface AddTaskSheetProps {
  open: boolean;
  slot?: TaskSlot | null;
  spaces: Space[];
  /** Preselected space (the active filter); falls back to the personal space. */
  defaultSpaceId?: number | null;
  onClose: () => void;
  onCreate: (data: TaskCreate) => Promise<unknown>;
}

export function AddTaskSheet({ open, slot = null, spaces, defaultSpaceId = null, onClose, onCreate }: AddTaskSheetProps) {
  const writable = spaces.filter(canWrite);
  const titleRef = useRef<HTMLInputElement>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<Category | null>(null);
  const [priority, setPriority] = useState<Priority>("medium");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [spaceId, setSpaceId] = useState<number | null>(null);
  const [repeat, setRepeat] = useState<RepeatId>("none");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setTitle("");
    setDescription("");
    setCategory(null);
    setPriority("medium");
    setDate(slot?.date ?? todayKey());
    setTime(slot?.time ?? "");
    setRepeat("none");
    setError(null);
    const frame = requestAnimationFrame(() => titleRef.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [open, slot?.date, slot?.time]);

  useEffect(() => {
    if (!open) return;
    const preferred = spaces.find((space) => space.id === defaultSpaceId && canWrite(space));
    const personal = spaces.find((space) => space.kind === "personal");
    setSpaceId(preferred?.id ?? personal?.id ?? null);
  }, [open, spaces, defaultSpaceId]);

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
      const start = date && time ? viennaToDate(date, time).toISOString() : null;
      const end = start ? new Date(new Date(start).getTime() + 3_600_000).toISOString() : null;
      await onCreate({
        title: trimmed,
        description: description.trim() || null,
        category,
        priority,
        deadline: end ?? (date ? viennaToDate(date, "23:59").toISOString() : null),
        space_id: spaceId,
        recurrence: repeatRule(repeat, date),
        remind_at: start,
        start_time: start,
        end_time: end,
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
    <BottomSheet
      open={open}
      title={slot ? "Нова подія" : "Нова задача"}
      subtitle={slot ? `Слот ${slot.time} · блок на 1 годину` : "Дата, нагадування та пріоритет — за бажанням"}
      onClose={onClose}
    >
      <form onSubmit={handleSubmit} className="space-y-5">
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

        {writable.length > 1 && (
          <fieldset className="space-y-2">
            <legend className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-zinc-500">
              <FolderOpen className="size-3" />
              Простір
            </legend>
            <div className="flex flex-wrap gap-2">
              {writable.map((space) => (
                <button
                  key={space.id}
                  type="button"
                  onClick={() => {
                    haptic.selection();
                    setSpaceId(space.id);
                  }}
                  className={cn("flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition", chipClass(spaceId === space.id))}
                >
                  <SpaceDot color={space.color} />
                  {space.name}
                </button>
              ))}
            </div>
          </fieldset>
        )}

        <fieldset className="space-y-2">
          <legend className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-zinc-500">
            <Repeat className="size-3" />
            Повтор
          </legend>
          <div className="flex flex-wrap gap-2">
            {REPEATS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  haptic.selection();
                  setRepeat(item.id);
                }}
                className={cn("rounded-full border px-3 py-1.5 text-sm transition", chipClass(repeat === item.id))}
              >
                {repeatLabel(item.id, date)}
              </button>
            ))}
          </div>
        </fieldset>

        {error && <p className="text-sm text-rose-400">{error}</p>}

        <button
          type="submit"
          disabled={submitting || !title.trim()}
          className="w-full rounded-2xl bg-gradient-to-r from-violet-600 to-fuchsia-500 py-3.5 text-sm font-semibold text-white shadow-[0_0_24px_rgba(168,85,247,0.35)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {submitting ? "Зберігаю…" : "Додати задачу"}
        </button>
      </form>
    </BottomSheet>
  );
}
