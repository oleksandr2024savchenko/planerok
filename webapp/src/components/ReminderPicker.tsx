"use client";

import { Bell, BellOff } from "lucide-react";
import { useState, type ReactNode } from "react";

import { cn } from "@/lib/cn";
import { formatDay, formatTime } from "@/lib/date";
import {
  MAX_OFFSET_MINUTES,
  OFFSET_UNITS,
  REMINDER_PRESETS,
  shortOffset,
  splitOffset,
  type OffsetUnit,
} from "@/lib/reminders";
import { haptic } from "@/lib/telegram";

/** Remount with a `key` to reset its custom-interval fields. */
interface ReminderPickerProps {
  /** Minutes before the event, or null for no reminder. */
  value: number | null;
  onChange: (value: number | null) => void;
  /** When the reminder will fire for the current value, for the preview line. */
  preview: string | null;
  /** Explains how date-only tasks are counted. */
  dateOnly?: boolean;
}

const isPreset = (value: number | null) =>
  value !== null && (REMINDER_PRESETS as readonly number[]).includes(value);

export function ReminderPicker({ value, onChange, preview, dateOnly = false }: ReminderPickerProps) {
  const [custom, setCustom] = useState(() => value !== null && !isPreset(value));
  const initial = splitOffset(value !== null && !isPreset(value) ? value : 30);
  const [amount, setAmount] = useState(String(initial.amount));
  const [unit, setUnit] = useState<OffsetUnit>(initial.unit);

  function applyCustom(nextAmount: string, nextUnit: OffsetUnit) {
    setAmount(nextAmount);
    setUnit(nextUnit);
    const parsed = Number.parseInt(nextAmount, 10);
    const per = OFFSET_UNITS.find((item) => item.id === nextUnit)?.minutes ?? 1;
    if (Number.isFinite(parsed) && parsed >= 0) onChange(Math.min(parsed * per, MAX_OFFSET_MINUTES));
  }

  function pick(next: number | null) {
    haptic.selection();
    setCustom(false);
    onChange(next);
  }

  return (
    <div className="space-y-2.5">
      <div className="flex flex-wrap gap-2">
        {REMINDER_PRESETS.map((minutes) => (
          <Chip key={minutes} active={!custom && value === minutes} onClick={() => pick(minutes)}>
            {shortOffset(minutes)}
          </Chip>
        ))}
        <Chip
          active={custom}
          onClick={() => {
            haptic.selection();
            setCustom(true);
            applyCustom(amount, unit);
          }}
        >
          Свій…
        </Chip>
        <Chip active={!custom && value === null} onClick={() => pick(null)}>
          <BellOff className="size-3.5" />
          Вимк.
        </Chip>
      </div>

      {custom && (
        <div className="flex items-center gap-2">
          <span className="text-sm text-zinc-400">за</span>
          <input
            type="number"
            inputMode="numeric"
            min={0}
            value={amount}
            onChange={(event) => applyCustom(event.target.value, unit)}
            aria-label="Скільки"
            className="w-20 rounded-xl border border-white/5 bg-zinc-900/80 px-3 py-2 text-sm text-zinc-100 outline-none transition focus:border-purple-500/50"
          />
          <div className="flex flex-1 rounded-xl border border-white/5 bg-zinc-900/70 p-1">
            {OFFSET_UNITS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  haptic.selection();
                  applyCustom(amount, item.id);
                }}
                className={cn(
                  "flex-1 rounded-lg py-1.5 text-xs font-medium transition",
                  unit === item.id ? "bg-purple-500/20 text-purple-100" : "text-zinc-400 hover:text-zinc-200",
                )}
              >
                {item.label}
              </button>
            ))}
          </div>
          <span className="text-sm text-zinc-400">до</span>
        </div>
      )}

      <p className="flex items-center gap-1.5 text-xs text-zinc-500">
        <Bell className="size-3" />
        {value === null
          ? "Без нагадування"
          : preview
            ? `Нагадаю ${formatDay(preview).toLowerCase()} о ${formatTime(preview)}`
            : "Обери дату, щоб нагадування спрацювало"}
        {value !== null && preview && new Date(preview).getTime() <= Date.now() && (
          <span className="text-amber-400/90"> · вже минуло</span>
        )}
      </p>
      {dateOnly && value !== null && (
        <p className="text-[11px] text-zinc-600">Для задачі без часу відлік іде від 07:00 дня дедлайну.</p>
      )}
    </div>
  );
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-3 py-1.5 text-sm transition",
        active
          ? "border-purple-500/50 bg-purple-500/15 text-purple-100 shadow-[0_0_16px_rgba(168,85,247,0.2)]"
          : "border-white/5 bg-zinc-900/70 text-zinc-400 hover:border-purple-500/30 hover:text-zinc-200",
      )}
    >
      {children}
    </button>
  );
}
