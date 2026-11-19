import { dateKey, viennaClock, viennaToDate } from "./date";
import type { Task } from "./types";

/** Mirrors `app/services/reminders.py` on the backend. */
export const MAX_OFFSET_MINUTES = 4 * 7 * 24 * 60;

export const REMINDER_PRESETS = [0, 15, 60, 3 * 60, 24 * 60, 2 * 24 * 60, 7 * 24 * 60] as const;

export const OFFSET_UNITS = [
  { id: "min", label: "хв", minutes: 1 },
  { id: "hour", label: "год", minutes: 60 },
  { id: "day", label: "дн", minutes: 24 * 60 },
  { id: "week", label: "тиж", minutes: 7 * 24 * 60 },
] as const;

export type OffsetUnit = (typeof OFFSET_UNITS)[number]["id"];

function plural(value: number, one: string, few: string, many: string): string {
  const mod10 = value % 10;
  const mod100 = value % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

/** 0 → «у момент події», 1440 → «за 1 день». */
export function formatOffset(minutes: number): string {
  if (minutes <= 0) return "у момент події";
  const week = 7 * 24 * 60;
  const day = 24 * 60;
  if (minutes % week === 0) {
    const n = minutes / week;
    return `за ${n} ${plural(n, "тиждень", "тижні", "тижнів")}`;
  }
  if (minutes % day === 0) {
    const n = minutes / day;
    return `за ${n} ${plural(n, "день", "дні", "днів")}`;
  }
  if (minutes % 60 === 0) {
    const n = minutes / 60;
    return `за ${n} ${plural(n, "годину", "години", "годин")}`;
  }
  return `за ${minutes} хв`;
}

/** Short chip label: 1440 → «1 день», 0 → «У момент». */
export function shortOffset(minutes: number): string {
  if (minutes <= 0) return "У момент";
  const label = formatOffset(minutes).replace(/^за /, "");
  return label.charAt(0).toUpperCase() + label.slice(1);
}

/** Largest whole unit for editing a custom offset: 2880 → { amount: 2, unit: "day" }. */
export function splitOffset(minutes: number): { amount: number; unit: OffsetUnit } {
  for (const unit of [...OFFSET_UNITS].reverse()) {
    if (minutes > 0 && minutes % unit.minutes === 0) return { amount: minutes / unit.minutes, unit: unit.id };
  }
  return { amount: minutes, unit: "min" };
}

/** Event start, timed deadline, or 07:00 on the due day for date-only tasks. */
export function reminderAnchor(task: Pick<Task, "start_time" | "deadline">): Date | null {
  if (task.start_time) return new Date(task.start_time);
  if (!task.deadline) return null;
  const clock = viennaClock(new Date(task.deadline));
  if (clock.hour === 23 && clock.minute === 59) return viennaToDate(dateKey(task.deadline), "07:00");
  return new Date(task.deadline);
}

export function remindAtFor(
  task: Pick<Task, "start_time" | "deadline">,
  minutes: number | null | undefined,
): string | null {
  if (minutes === null || minutes === undefined) return null;
  const anchor = reminderAnchor(task);
  return anchor ? new Date(anchor.getTime() - minutes * 60_000).toISOString() : null;
}
