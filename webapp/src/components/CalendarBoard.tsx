"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { cn } from "@/lib/cn";
import {
  addDays,
  dateKey,
  formatDayKey,
  formatTime,
  startOfWeek,
  todayKey,
  viennaClock,
  weekdayIndex,
} from "@/lib/date";
import { haptic } from "@/lib/telegram";
import type { Task } from "@/lib/types";

const START_HOUR = 7;
const END_HOUR = 23;
const HOUR_PX = 64;
const HOURS = Array.from({ length: END_HOUR - START_HOUR }, (_, index) => START_HOUR + index);
const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"];

type Zoom = "day" | "week";

interface CalendarBoardProps {
  tasks: Task[];
  onSlot: (date: string, time: string) => void;
}

interface Block {
  task: Task;
  startMin: number;
  endMin: number;
}

export function CalendarBoard({ tasks, onSlot }: CalendarBoardProps) {
  const [zoom, setZoom] = useState<Zoom>("day");
  const [anchor, setAnchor] = useState(() => todayKey());
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      document.querySelector("[data-now-line]")?.scrollIntoView({ block: "center" });
    });
    return () => cancelAnimationFrame(frame);
  }, [zoom, anchor]);

  const days = useMemo(() => {
    const start = zoom === "week" ? startOfWeek(anchor) : anchor;
    return Array.from({ length: zoom === "week" ? 7 : 1 }, (_, index) => addDays(start, index));
  }, [anchor, zoom]);

  const clock = viennaClock(now);
  const nowMinutes = (clock.hour - START_HOUR) * 60 + clock.minute;
  const showNow = nowMinutes >= 0 && nowMinutes <= (END_HOUR - START_HOUR) * 60;
  const today = dateKey(now);

  function shift(direction: -1 | 1) {
    haptic.selection();
    setAnchor((current) => addDays(current, direction * (zoom === "week" ? 7 : 1)));
  }

  const firstDay = days[0] ?? anchor;
  const lastDay = days[days.length - 1] ?? anchor;
  const label = zoom === "day" ? formatDayKey(anchor) : `${formatDayKey(firstDay)} — ${formatDayKey(lastDay)}`;

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex rounded-full border border-white/5 bg-zinc-900/60 p-1">
          {(["day", "week"] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => {
                if (zoom === value) return;
                haptic.selection();
                setZoom(value);
              }}
              className={cn(
                "rounded-full px-3 py-1 text-xs font-medium transition",
                zoom === value ? "bg-purple-500/20 text-purple-100" : "text-zinc-400",
              )}
            >
              {value === "day" ? "День" : "Тиждень"}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1">
          <IconButton label="Назад" onClick={() => shift(-1)}>
            <ChevronLeft className="size-4" />
          </IconButton>
          <button
            type="button"
            onClick={() => setAnchor(todayKey())}
            className="min-w-28 px-2 text-center text-sm font-medium text-zinc-100"
          >
            {label}
          </button>
          <IconButton label="Далі" onClick={() => shift(1)}>
            <ChevronRight className="size-4" />
          </IconButton>
        </div>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-white/5 bg-zinc-950/40">
        <div className={cn("min-w-full", zoom === "week" && "min-w-[640px]")}>
          <div className="grid" style={{ gridTemplateColumns: `44px repeat(${days.length}, minmax(0, 1fr))` }}>
            <div />
            {days.map((day) => (
              <div
                key={day}
                className={cn(
                  "border-b border-white/5 px-1 py-2 text-center",
                  day === today && "text-purple-200",
                )}
              >
                <div className="text-[10px] uppercase tracking-wider text-zinc-500">{WEEKDAYS[weekdayIndex(day)]}</div>
                <div className={cn("text-sm font-semibold", day === today ? "text-purple-100" : "text-zinc-200")}>
                  {Number(day.slice(-2))}
                </div>
              </div>
            ))}

            <div className="relative" style={{ height: HOURS.length * HOUR_PX }}>
              {HOURS.map((hour) => (
                <div
                  key={hour}
                  className="absolute right-2 -translate-y-1/2 font-mono text-[10px] text-zinc-600"
                  style={{ top: (hour - START_HOUR) * HOUR_PX }}
                >
                  {String(hour).padStart(2, "0")}
                </div>
              ))}
            </div>

            {days.map((day) => (
              <DayColumn
                key={day}
                day={day}
                blocks={blocksForDay(tasks, day)}
                showNow={showNow && day === today}
                nowTop={(nowMinutes / 60) * HOUR_PX}
                onSlot={(time) => onSlot(day, time)}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function DayColumn({
  day,
  blocks,
  showNow,
  nowTop,
  onSlot,
}: {
  day: string;
  blocks: ReturnType<typeof layoutBlocks>;
  showNow: boolean;
  nowTop: number;
  onSlot: (time: string) => void;
}) {
  return (
    <div className="relative border-l border-white/5" style={{ height: HOURS.length * HOUR_PX }}>
      {HOURS.map((hour) => (
        <button
          key={hour}
          type="button"
          aria-label={`Створити подію ${formatDayKey(day)} о ${String(hour).padStart(2, "0")}:00`}
          onClick={() => {
            haptic.selection();
            onSlot(`${String(hour).padStart(2, "0")}:00`);
          }}
          className="absolute inset-x-0 border-t border-white/[0.06] transition hover:bg-purple-500/[0.06]"
          style={{ top: (hour - START_HOUR) * HOUR_PX, height: HOUR_PX }}
        />
      ))}

      {blocks.map((block) => {
        const width = 100 / block.cols;
        return (
          <div
            key={block.task.id}
            className={cn(
              "absolute z-10 overflow-hidden rounded-md border-l-4 border-purple-500 bg-purple-950/40 px-1.5 py-1 text-left backdrop-blur-md",
              block.task.is_completed && "opacity-45",
            )}
            style={{
              top: (block.startMin / 60) * HOUR_PX + 1,
              height: Math.max(22, (block.endMin - block.startMin) / 60 * HOUR_PX - 2),
              left: `calc(${block.col * width}% + 2px)`,
              width: `calc(${width}% - 4px)`,
            }}
            onClick={(event) => event.stopPropagation()}
          >
            <p className="truncate text-[11px] font-medium leading-tight text-zinc-100">{block.task.title}</p>
            <p className="truncate text-[10px] text-purple-200/80">
              {formatTime(block.task.start_time ?? block.task.deadline ?? "")}
              {block.task.google_event_id ? " · G" : ""}
            </p>
          </div>
        );
      })}

      {showNow && (
        <div
          data-now-line
          className="pointer-events-none absolute inset-x-0 z-20"
          style={{ top: nowTop }}
        >
          <span className="absolute -left-1 top-1/2 size-2.5 -translate-y-1/2 animate-pulse rounded-full bg-purple-500 shadow-[0_0_10px_#A855F7]" />
          <span className="block h-px bg-purple-500 shadow-[0_0_10px_#A855F7]" />
        </div>
      )}
    </div>
  );
}

function IconButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      className="flex size-8 items-center justify-center rounded-full text-zinc-400 transition hover:bg-white/5 hover:text-zinc-100"
    >
      {children}
    </button>
  );
}

function blocksForDay(tasks: Task[], day: string) {
  const gridStart = START_HOUR * 60;
  const gridEnd = END_HOUR * 60;
  const blocks: Block[] = [];
  for (const task of tasks) {
    const range = blockRange(task);
    if (!range || dateKey(range.start) !== day) continue;
    const startMin = Math.max(gridStart, minutesOfDay(range.start)) - gridStart;
    const endMin = Math.min(gridEnd, minutesOfDay(range.end)) - gridStart;
    if (endMin <= startMin) continue;
    blocks.push({ task, startMin, endMin });
  }
  return layoutBlocks(blocks);
}

function blockRange(task: Task): { start: string; end: string } | null {
  if (task.start_time) {
    const end = task.end_time ?? new Date(new Date(task.start_time).getTime() + 3_600_000).toISOString();
    return { start: task.start_time, end };
  }
  if (!task.deadline) return null;
  const clock = viennaClock(new Date(task.deadline));
  if (clock.hour === 23 && clock.minute === 59) return null;
  return {
    start: task.deadline,
    end: new Date(new Date(task.deadline).getTime() + 3_600_000).toISOString(),
  };
}

function minutesOfDay(iso: string): number {
  const clock = viennaClock(new Date(iso));
  return clock.hour * 60 + clock.minute;
}

function layoutBlocks(blocks: Block[]) {
  const sorted = [...blocks].sort((a, b) => a.startMin - b.startMin || a.endMin - b.endMin);
  const columnEnds: number[] = [];
  const columnOf = new Map<number, number>();
  for (const block of sorted) {
    let column = columnEnds.findIndex((end) => end <= block.startMin);
    if (column < 0) {
      column = columnEnds.length;
      columnEnds.push(block.endMin);
    } else {
      columnEnds[column] = block.endMin;
    }
    columnOf.set(block.task.id, column);
  }
  return sorted.map((block) => {
    const overlapping = sorted.filter(
      (other) => other.startMin < block.endMin && other.endMin > block.startMin,
    );
    const cols = Math.max(...overlapping.map((other) => (columnOf.get(other.task.id) ?? 0) + 1));
    return { ...block, col: columnOf.get(block.task.id) ?? 0, cols };
  });
}
