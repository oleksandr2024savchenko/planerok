"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { SegmentedControl } from "@/components/SegmentedControl";
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

const START_HOUR = 0;
const END_HOUR = 24;
const HOUR_PX = 76;
const GUTTER_PX = 62;
const HOURS = Array.from({ length: END_HOUR - START_HOUR }, (_, index) => START_HOUR + index);
const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"];

type Zoom = "day" | "week";

interface CalendarBoardProps {
  tasks: Task[];
  onSlot: (date: string, time: string) => void;
  onOpenTask: (taskId: number) => void;
}

interface Block {
  key: string;
  taskId: number;
  title: string;
  startIso: string;
  endIso: string;
  completed: boolean;
  external: boolean;
  startMin: number;
  endMin: number;
}

export function CalendarBoard({ tasks, onSlot, onOpenTask }: CalendarBoardProps) {
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
  const allDay = useMemo(() => {
    const byDay = new Map<string, Task[]>();
    for (const day of days) {
      byDay.set(
        day,
        tasks.filter((task) => task.all_day && task.start_time && dateKey(task.start_time) === day),
      );
    }
    return byDay;
  }, [days, tasks]);
  const hasAllDay = days.some((day) => (allDay.get(day) ?? []).length > 0);

  return (
    <section className="space-y-3">
      <div className="flex flex-col gap-2.5 min-[480px]:flex-row min-[480px]:items-center min-[480px]:justify-between">
        <SegmentedControl
          size="sm"
          layoutId="calendar-zoom"
          value={zoom}
          options={[
            { id: "day", label: "День" },
            { id: "week", label: "Тиждень" },
          ]}
          onChange={(next) => {
            haptic.selection();
            setZoom(next);
          }}
          className="self-start"
        />
        <div className="flex min-w-0 items-center gap-1">
          <IconButton label="Назад" onClick={() => shift(-1)}>
            <ChevronLeft className="size-4" />
          </IconButton>
          <button
            type="button"
            onClick={() => setAnchor(todayKey())}
            className="min-w-0 flex-1 truncate rounded-full px-2 py-1 text-center text-sm font-medium text-zinc-100 hover:bg-white/5 min-[480px]:flex-none min-[480px]:max-w-56"
          >
            {label}
          </button>
          <IconButton label="Далі" onClick={() => shift(1)}>
            <ChevronRight className="size-4" />
          </IconButton>
        </div>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-white/10 bg-zinc-950/50">
        <div className={zoom === "week" ? "min-w-[980px]" : "min-w-full"}>
          <div className="grid" style={{ gridTemplateColumns: `${GUTTER_PX}px repeat(${days.length}, minmax(0, 1fr))` }}>
            <div />
            {days.map((day) => (
              <div
                key={day}
                className={cn(
                  "border-b border-white/5 px-1 py-2 text-center",
                  day === today && "text-purple-200",
                )}
              >
                <div className="text-[11px] uppercase tracking-wider text-zinc-500">{WEEKDAYS[weekdayIndex(day)]}</div>
                <div className={cn("text-base font-semibold", day === today ? "text-purple-100" : "text-zinc-200")}>
                  {Number(day.slice(-2))}
                </div>
              </div>
            ))}

            {hasAllDay && (
              <>
                <div className="border-b border-white/5 px-1 py-2 text-[10px] uppercase tracking-wider text-zinc-500">
                  Весь день
                </div>
                {days.map((day) => (
                  <div key={`all-${day}`} className="space-y-1 border-b border-l border-white/5 px-1 py-1">
                    {(allDay.get(day) ?? []).map((task) => (
                      <button
                        key={task.id}
                        type="button"
                        onClick={() => {
                          haptic.selection();
                          onOpenTask(task.id);
                        }}
                        className={cn(
                          "block w-full truncate rounded-md bg-white/10 px-1.5 py-0.5 text-left text-[11px] font-medium text-zinc-100",
                          task.is_completed && "text-zinc-500 line-through opacity-60",
                        )}
                      >
                        {task.title}
                      </button>
                    ))}
                  </div>
                ))}
              </>
            )}

            <div className="relative border-white/10" style={{ height: HOURS.length * HOUR_PX }}>
              {HOURS.map((hour) => (
                <div
                  key={hour}
                  className="absolute right-2 font-mono text-xs leading-none text-zinc-400"
                  style={{ top: hour === START_HOUR ? 2 : (hour - START_HOUR) * HOUR_PX - 6 }}
                >
                  {String(hour).padStart(2, "0")}:00
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
                onOpenTask={onOpenTask}
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
  onOpenTask,
}: {
  day: string;
  blocks: ReturnType<typeof layoutBlocks>;
  showNow: boolean;
  nowTop: number;
  onSlot: (time: string) => void;
  onOpenTask: (taskId: number) => void;
}) {
  return (
    <div className="relative border-l border-white/5" style={{ height: HOURS.length * HOUR_PX }}>
      {HOURS.map((hour) => (
        <button
          key={hour}
          type="button"
          aria-label={`Створити подію ${formatDayKey(day)} о ${String(hour).padStart(2, "0")}:00`}
          onClick={(event) => {
            const rect = event.currentTarget.getBoundingClientRect();
            const fraction = rect.height ? (event.clientY - rect.top) / rect.height : 0;
            const minute = Math.min(55, Math.max(0, Math.round((fraction * 60) / 5) * 5));
            haptic.selection();
            onSlot(`${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`);
          }}
          className="absolute inset-x-0 border-t border-white/10 transition hover:bg-purple-500/[0.06]"
          style={{ top: (hour - START_HOUR) * HOUR_PX, height: HOUR_PX }}
        />
      ))}

      {blocks.map((block) => {
        const width = 100 / block.cols;
        return (
          <button
            key={block.key}
            type="button"
            aria-label={`Редагувати ${block.title}`}
            className={cn(
              "event-block absolute z-10 overflow-hidden rounded-lg border-l-4 px-2 py-1 text-left",
              block.completed && "opacity-45",
              block.external && "border-dashed",
            )}
            style={{
              top: (block.startMin / 60) * HOUR_PX + 1,
              height: blockHeight(block),
              left: `calc(${block.col * width}% + 1px)`,
              width: `calc(${width}% - 3px)`,
            }}
            onClick={(event) => {
              event.stopPropagation();
              haptic.selection();
              onOpenTask(block.taskId);
            }}
          >
            <p
              className={cn(
                "truncate text-sm font-medium leading-5",
                block.completed ? "text-zinc-400 line-through" : "text-zinc-50",
              )}
            >
              {block.title}
            </p>
            {blockHeight(block) >= 40 && (
              <p className="truncate text-xs leading-4">{blockLabel(block)}</p>
            )}
          </button>
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
      className="flex size-8 shrink-0 items-center justify-center rounded-full text-zinc-400 hover:bg-white/10 hover:text-zinc-100"
    >
      {children}
    </button>
  );
}

function blockHeight(block: { startMin: number; endMin: number }): number {
  return Math.max(30, ((block.endMin - block.startMin) / 60) * HOUR_PX - 4);
}

function blockLabel(block: Block): string {
  const start = formatTime(block.startIso);
  const end = formatTime(block.endIso);
  return end && end !== start ? `${start}–${end}` : start;
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
    blocks.push({
      key: `task-${task.id}`,
      taskId: task.id,
      title: task.title,
      startIso: range.start,
      endIso: range.end,
      completed: task.is_completed,
      external: Boolean(task.read_only),
      startMin,
      endMin,
    });
  }
  return layoutBlocks(blocks);
}

function blockRange(task: Task): { start: string; end: string } | null {
  if (task.all_day) return null;
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
  const columnOf = new Map<string, number>();
  for (const block of sorted) {
    let column = columnEnds.findIndex((end) => end <= block.startMin);
    if (column < 0) {
      column = columnEnds.length;
      columnEnds.push(block.endMin);
    } else {
      columnEnds[column] = block.endMin;
    }
    columnOf.set(block.key, column);
  }
  return sorted.map((block) => {
    const overlapping = sorted.filter(
      (other) => other.startMin < block.endMin && other.endMin > block.startMin,
    );
    const cols = Math.max(...overlapping.map((other) => (columnOf.get(other.key) ?? 0) + 1));
    return { ...block, col: columnOf.get(block.key) ?? 0, cols };
  });
}
