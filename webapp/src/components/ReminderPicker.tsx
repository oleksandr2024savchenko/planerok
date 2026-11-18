"use client";

import { Bell, BellOff } from "lucide-react";
import { useState } from "react";

import { ChoiceChip, SegmentedControl } from "@/components/SegmentedControl";
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

import { Reveal } from "./Reveal";

interface ReminderPickerProps {
  /** Minutes before the event, or null for no reminder. Remount with a `key` to reset. */
  value: number | null;
  onChange: (value: number | null) => void;
  /** When the reminder fires for the current value, for the hint line. */
  preview: string | null;
  /** Explains how date-only tasks are counted. */
  dateOnly?: boolean;
}

const isPreset = (value: number | null) =>
  value !== null && (REMINDER_PRESETS as readonly number[]).includes(value);

const UNIT_OPTIONS = OFFSET_UNITS.map((unit) => ({ id: unit.id, label: unit.label }));

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

  const passed = value !== null && preview !== null && new Date(preview).getTime() <= Date.now();

  return (
    <div className="min-w-0 space-y-2.5">
      <div className="flex flex-wrap gap-2">
        {REMINDER_PRESETS.map((minutes) => (
          <ChoiceChip
            key={minutes}
            layoutId="task-reminder"
            anchored
            active={!custom && value === minutes}
            onClick={() => pick(minutes)}
          >
            {shortOffset(minutes)}
          </ChoiceChip>
        ))}
        <ChoiceChip
          layoutId="task-reminder"
          anchored
          active={custom}
          onClick={() => {
            haptic.selection();
            setCustom(true);
            applyCustom(amount, unit);
          }}
        >
          Свій…
        </ChoiceChip>
        <ChoiceChip layoutId="task-reminder" anchored active={!custom && value === null} onClick={() => pick(null)}>
          <BellOff className="size-3.5 shrink-0" />
          Вимк.
        </ChoiceChip>
      </div>

      <Reveal show={custom}>
        <div className="flex min-w-0 items-center gap-2">
          <span className="shrink-0 text-sm text-zinc-400">за</span>
          <input
            type="number"
            inputMode="numeric"
            min={0}
            value={amount}
            onChange={(event) => applyCustom(event.target.value, unit)}
            aria-label="Скільки"
            className="field-focus w-16 shrink-0 rounded-xl border border-white/10 bg-zinc-900/80 px-3 py-2 text-sm text-zinc-100 outline-none"
          />
          <SegmentedControl
            className="min-w-0 flex-1"
            fullWidth
            anchored
            size="sm"
            layoutId="task-reminder-unit"
            value={unit}
            options={UNIT_OPTIONS}
            onChange={(next) => {
              haptic.selection();
              applyCustom(amount, next);
            }}
          />
          <span className="shrink-0 text-sm text-zinc-400">до</span>
        </div>
      </Reveal>

      <p className="flex items-center gap-1.5 text-xs text-zinc-500">
        <Bell className="size-3 shrink-0" />
        <span>
          {value === null
            ? "Без нагадування"
            : preview
              ? `Нагадаю ${formatDay(preview).toLowerCase()} о ${formatTime(preview)}`
              : "Обери дату, щоб нагадування спрацювало"}
          {passed && <span className="text-amber-400/90"> · вже минуло</span>}
        </span>
      </p>
      <Reveal show={dateOnly && value !== null}>
        <p className="text-[11px] text-zinc-600">Для задачі без часу відлік іде від 07:00 дня дедлайну.</p>
      </Reveal>
    </div>
  );
}
