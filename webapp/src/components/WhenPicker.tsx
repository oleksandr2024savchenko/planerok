"use client";

import { CalendarDays, ChevronLeft, ChevronRight, Clock } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { ChoiceChip } from "@/components/SegmentedControl";
import { cn } from "@/lib/cn";
import { addDays, formatDayKey, shiftTime, todayKey, weekdayIndex } from "@/lib/date";
import { haptic } from "@/lib/telegram";

import { Reveal } from "./Reveal";

const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"];
const QUICK_TIMES = ["09:00", "12:00", "15:00", "18:00", "20:00"];
const DURATIONS = [15, 30, 60, 90, 120, 180];
const MONTH = new Intl.DateTimeFormat("uk-UA", { month: "long", year: "numeric", timeZone: "UTC" });

interface WhenPickerProps {
  date: string;
  start: string;
  end: string;
  onChange: (date: string, start: string, end: string) => void;
}

function minutesOf(time: string): number {
  const [h, m] = time.split(":").map(Number);
  return h * 60 + m;
}

function durationLabel(minutes: number): string {
  if (minutes < 60) return `${minutes} хв`;
  const hours = minutes / 60;
  return Number.isInteger(hours) ? `${hours} год` : `${hours.toString().replace(".", ",")} год`;
}

function dayChipLabel(key: string, today: string): string {
  if (key === today) return "Сьогодні";
  if (key === addDays(today, 1)) return "Завтра";
  return `${WEEKDAYS[weekdayIndex(key)]} ${Number(key.slice(8))}`;
}

/**
 * «Коли» in one place: a day in one tap, a time from chips or a 24-hour wheel, and a duration
 * instead of a separate end time. Replaces three native date/time inputs.
 */
export function WhenPicker({ date, start, end, onChange }: WhenPickerProps) {
  const today = todayKey();
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [wheelOpen, setWheelOpen] = useState(() => Boolean(start) && !QUICK_TIMES.includes(start));
  const duration = start && end ? Math.max(minutesOf(end) - minutesOf(start), 0) : 60;

  const days = useMemo(() => Array.from({ length: 8 }, (_, index) => addDays(today, index)), [today]);
  const farDate = date && !days.includes(date) ? date : null;

  function pickDay(next: string) {
    haptic.selection();
    onChange(next, next ? start : "", next ? end : "");
  }

  function pickTime(next: string) {
    haptic.selection();
    onChange(date || today, next, next ? shiftTime(next, duration || 60) : "");
  }

  function pickDuration(minutes: number) {
    haptic.selection();
    if (start) onChange(date, start, shiftTime(start, minutes));
  }

  const summary = date
    ? `${formatDayKey(date)}${date !== today && date !== addDays(today, 1) ? `, ${WEEKDAYS[weekdayIndex(date)].toLowerCase()}` : ""} · ${
        start ? `${start}–${end || shiftTime(start, 60)}` : "весь день"
      }`
    : "Без дати";

  return (
    <section className="min-w-0 space-y-3">
      <div className="flex items-baseline justify-between gap-2">
        <span className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-zinc-500">
          <CalendarDays className="size-3 shrink-0" />
          Коли
        </span>
        <span className="truncate text-sm font-semibold text-zinc-100">{summary}</span>
      </div>

      <div className="no-scrollbar -mx-4 flex gap-1.5 overflow-x-auto px-4 sm:-mx-5 sm:px-5">
        <ChoiceChip layoutId="when-day" anchored active={!date} onClick={() => pickDay("")}>
          Без дати
        </ChoiceChip>
        {days.map((key) => (
          <ChoiceChip key={key} layoutId="when-day" anchored active={date === key} onClick={() => pickDay(key)}>
            {dayChipLabel(key, today)}
          </ChoiceChip>
        ))}
        {farDate && (
          <ChoiceChip layoutId="when-day" anchored active onClick={() => setCalendarOpen((open) => !open)}>
            {formatDayKey(farDate)}
          </ChoiceChip>
        )}
        <ChoiceChip
          layoutId="when-day-more"
          anchored
          active={calendarOpen}
          aria-label="Обрати дату в календарі"
          onClick={() => {
            haptic.selection();
            setCalendarOpen((open) => !open);
          }}
        >
          <CalendarDays className="size-3.5" />
          Інша
        </ChoiceChip>
      </div>

      <Reveal show={calendarOpen}>
        <MonthGrid
          value={date}
          today={today}
          onPick={(key) => {
            pickDay(key);
            setCalendarOpen(false);
          }}
        />
      </Reveal>

      <Reveal show={Boolean(date)}>
        <div className="space-y-2.5">
          <div className="flex flex-wrap gap-1.5">
            <ChoiceChip
              layoutId="when-time"
              anchored
              active={!start}
              onClick={() => {
                setWheelOpen(false);
                pickTime("");
              }}
            >
              Весь день
            </ChoiceChip>
            {QUICK_TIMES.map((time) => (
              <ChoiceChip
                key={time}
                layoutId="when-time"
                anchored
                active={!wheelOpen && start === time}
                onClick={() => {
                  setWheelOpen(false);
                  pickTime(time);
                }}
              >
                {time}
              </ChoiceChip>
            ))}
            <ChoiceChip
              layoutId="when-time"
              anchored
              active={wheelOpen}
              onClick={() => {
                haptic.selection();
                setWheelOpen(true);
                if (!start) pickTime(nextRoundTime());
              }}
            >
              <Clock className="size-3.5" />
              {wheelOpen && start ? start : "Свій час"}
            </ChoiceChip>
          </div>

          <Reveal show={wheelOpen && Boolean(start)}>
            <TimeWheel value={start || "09:00"} onChange={(time) => onChange(date || today, time, shiftTime(time, duration || 60))} />
          </Reveal>

          <Reveal show={Boolean(start)}>
            <div className="space-y-1.5">
              <p className="text-xs text-zinc-500">
                Триватиме · до <span className="font-medium text-zinc-300">{end || shiftTime(start || "00:00", 60)}</span>
              </p>
              <div className="flex flex-wrap gap-1.5">
                {DURATIONS.map((minutes) => (
                  <ChoiceChip
                    key={minutes}
                    layoutId="when-duration"
                    anchored
                    active={duration === minutes}
                    onClick={() => pickDuration(minutes)}
                  >
                    {durationLabel(minutes)}
                  </ChoiceChip>
                ))}
                {start && !DURATIONS.includes(duration) && duration > 0 && (
                  <ChoiceChip layoutId="when-duration" anchored active onClick={() => undefined}>
                    {durationLabel(duration)}
                  </ChoiceChip>
                )}
              </div>
            </div>
          </Reveal>
        </div>
      </Reveal>
    </section>
  );
}

/** Next quarter hour from now, e.g. 14:07 → 14:15. */
function nextRoundTime(): string {
  const now = new Date();
  const total = Math.min(Math.ceil((now.getHours() * 60 + now.getMinutes() + 1) / 15) * 15, 23 * 60 + 45);
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

function MonthGrid({ value, today, onPick }: { value: string; today: string; onPick: (key: string) => void }) {
  const [month, setMonth] = useState(() => (value || today).slice(0, 7));
  const [year, monthIndex] = month.split("-").map(Number);
  const first = `${month}-01`;
  const lead = weekdayIndex(first);
  const length = new Date(Date.UTC(year, monthIndex, 0)).getUTCDate();
  const cells = [...Array(lead).fill(null), ...Array.from({ length }, (_, i) => `${month}-${String(i + 1).padStart(2, "0")}`)];

  function shift(direction: -1 | 1) {
    haptic.selection();
    const next = new Date(Date.UTC(year, monthIndex - 1 + direction, 1));
    setMonth(next.toISOString().slice(0, 7));
  }

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-2.5">
      <div className="mb-2 flex items-center justify-between">
        <button type="button" aria-label="Попередній місяць" onClick={() => shift(-1)} className="flex size-8 items-center justify-center rounded-full text-zinc-400 hover:text-zinc-100">
          <ChevronLeft className="size-4" />
        </button>
        <span className="text-sm font-medium capitalize text-zinc-100">{MONTH.format(new Date(Date.UTC(year, monthIndex - 1, 15)))}</span>
        <button type="button" aria-label="Наступний місяць" onClick={() => shift(1)} className="flex size-8 items-center justify-center rounded-full text-zinc-400 hover:text-zinc-100">
          <ChevronRight className="size-4" />
        </button>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center">
        {WEEKDAYS.map((day) => (
          <span key={day} className="pb-1 text-[10px] font-medium uppercase tracking-wider text-zinc-500">
            {day}
          </span>
        ))}
        {cells.map((key, index) =>
          key ? (
            <button
              key={key}
              type="button"
              onClick={() => onPick(key)}
              className={cn(
                "aspect-square rounded-full text-sm tabular-nums",
                key === value
                  ? "choice-fill font-semibold text-white"
                  : key === today
                    ? "border border-purple-500/50 text-zinc-100"
                    : key < today
                      ? "text-zinc-600"
                      : "text-zinc-200 hover:bg-white/5",
              )}
            >
              {Number(key.slice(8))}
            </button>
          ) : (
            <span key={`pad-${index}`} />
          ),
        )}
      </div>
    </div>
  );
}

const ROW = 40;

/** iOS-style 24-hour wheel: hours and minutes in 5-minute steps, snapping under a centre band. */
function TimeWheel({ value, onChange }: { value: string; onChange: (time: string) => void }) {
  const [hour, minute] = value.split(":").map(Number);
  const minutes = useMemo(() => {
    const list = Array.from({ length: 12 }, (_, i) => i * 5);
    return list.includes(minute) ? list : [...list, minute].sort((a, b) => a - b);
  }, [minute]);

  return (
    <div className="relative mx-auto flex w-56 items-stretch justify-center gap-2 rounded-2xl border border-white/10 bg-white/[0.04] px-3">
      <div aria-hidden className="pointer-events-none absolute inset-x-2 top-1/2 h-10 -translate-y-1/2 rounded-xl bg-purple-500/15" />
      <WheelColumn
        label="Години"
        items={Array.from({ length: 24 }, (_, i) => i)}
        value={hour}
        onChange={(h) => onChange(`${String(h).padStart(2, "0")}:${String(minute).padStart(2, "0")}`)}
      />
      <span className="self-center text-xl font-semibold text-zinc-400">:</span>
      <WheelColumn
        label="Хвилини"
        items={minutes}
        value={minute}
        onChange={(m) => onChange(`${String(hour).padStart(2, "0")}:${String(m).padStart(2, "0")}`)}
      />
    </div>
  );
}

function WheelColumn({
  label,
  items,
  value,
  onChange,
}: {
  label: string;
  items: number[];
  value: number;
  onChange: (value: number) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const settle = useRef<number | null>(null);
  const lastIndex = useRef(items.indexOf(value));

  // Follow outside changes (a chip was tapped) without fighting the finger.
  useEffect(() => {
    const index = items.indexOf(value);
    const el = ref.current;
    if (!el || index < 0) return;
    if (Math.round(el.scrollTop / ROW) !== index) el.scrollTo({ top: index * ROW, behavior: lastIndex.current < 0 ? "auto" : "smooth" });
    lastIndex.current = index;
  }, [items, value]);

  return (
    <div
      ref={ref}
      role="listbox"
      aria-label={label}
      className="no-scrollbar relative z-10 h-[120px] w-16 snap-y snap-mandatory overflow-y-auto overscroll-contain py-10 text-center"
      onScroll={(event) => {
        const el = event.currentTarget;
        if (settle.current) window.clearTimeout(settle.current);
        settle.current = window.setTimeout(() => {
          const index = Math.max(0, Math.min(items.length - 1, Math.round(el.scrollTop / ROW)));
          if (index !== lastIndex.current) {
            lastIndex.current = index;
            haptic.selection();
            onChange(items[index]);
          }
        }, 90);
      }}
    >
      {items.map((item) => (
        <button
          key={item}
          type="button"
          role="option"
          aria-selected={item === value}
          onClick={() => onChange(item)}
          className={cn(
            "flex h-10 w-full snap-center items-center justify-center font-mono text-xl tabular-nums transition-colors",
            item === value ? "font-semibold text-zinc-100" : "text-zinc-500",
          )}
        >
          {String(item).padStart(2, "0")}
        </button>
      ))}
    </div>
  );
}
