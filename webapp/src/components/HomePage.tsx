"use client";

import { useEffect, useMemo, useState } from "react";

import { useTasks } from "@/hooks/useTasks";
import { calendarApi, USE_MOCKS } from "@/lib/api";
import { cn } from "@/lib/cn";
import { countByFilter, matchesFilter, sortTasks, todayProgress, type FilterId } from "@/lib/filters";
import type { CalendarStatus } from "@/lib/types";

import { AddTaskSheet, type TaskSlot } from "./AddTaskSheet";
import { CalendarBoard } from "./CalendarBoard";
import { DashboardHeader } from "./DashboardHeader";
import { EmptyState } from "./EmptyState";
import { Fab } from "./Fab";
import { FilterPills } from "./FilterPills";
import { SyncBadge } from "./SyncBadge";
import { TaskList } from "./TaskList";
import { useTelegram } from "./TelegramProvider";
import { ViewModeSwitch, type ViewMode } from "./ViewModeSwitch";

const MOCK_STATUS: CalendarStatus = { connected: true, live: true, last_sync_at: null };
const OFFLINE_STATUS: CalendarStatus = { connected: false, live: false, last_sync_at: null };

export function HomePage() {
  const { firstName, isReady } = useTelegram();
  const { tasks, isLoading, error, reload, createTask, toggleTask } = useTasks({
    enabled: isReady || USE_MOCKS,
  });
  const [filter, setFilter] = useState<FilterId>("today");
  const [view, setView] = useState<ViewMode>("list");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [slot, setSlot] = useState<TaskSlot | null>(null);
  const sync = useCalendarStatus(isReady || USE_MOCKS);

  const counts = useMemo(() => countByFilter(tasks), [tasks]);
  const visible = useMemo(
    () => sortTasks(tasks.filter((task) => matchesFilter(task, filter))),
    [tasks, filter],
  );
  const progress = useMemo(() => todayProgress(tasks), [tasks]);
  const ready = (isReady || USE_MOCKS) && !isLoading;

  useEffect(() => {
    if (view !== "calendar" || USE_MOCKS) return;
    const timer = setInterval(() => void reload({ silent: true }), 15_000);
    return () => clearInterval(timer);
  }, [view, reload]);

  function openSheet(nextSlot: TaskSlot | null = null) {
    setSlot(nextSlot);
    setSheetOpen(true);
  }

  return (
    <main className={cn("relative mx-auto min-h-dvh px-5 pb-28 pt-6", view === "calendar" ? "max-w-3xl" : "max-w-lg")}>
      <DashboardHeader firstName={firstName} done={progress.done} total={progress.total} />

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
        <SyncBadge status={sync} />
        <ViewModeSwitch value={view} onChange={setView} />
      </div>

      {view === "list" && (
        <div className="mt-4">
          <FilterPills value={filter} counts={counts} onChange={setFilter} />
        </div>
      )}

      {error && (
        <button
          type="button"
          onClick={() => void reload()}
          className="mt-4 w-full rounded-xl border border-rose-500/20 bg-rose-500/10 px-3 py-2.5 text-left text-sm text-rose-300 transition hover:border-rose-500/40"
        >
          {error}
          <span className="mt-0.5 block text-xs text-rose-400/80">Натисни, щоб спробувати ще раз</span>
        </button>
      )}

      <div className="mt-5">
        {!ready ? (
          <TaskSkeleton />
        ) : view === "calendar" ? (
          <CalendarBoard tasks={tasks} onSlot={(date, time) => openSheet({ date, time })} />
        ) : visible.length === 0 ? (
          <EmptyState filter={filter} onAdd={() => openSheet(null)} />
        ) : (
          <TaskList tasks={visible} filter={filter} onToggle={toggleTask} />
        )}
      </div>

      {USE_MOCKS && (
        <p className="mt-8 text-center text-[11px] tracking-wide text-zinc-600">Демо-дані · API ще не підключено</p>
      )}

      <Fab hidden={sheetOpen} onClick={() => openSheet(null)} />
      <AddTaskSheet
        open={sheetOpen}
        slot={slot}
        onClose={() => setSheetOpen(false)}
        onCreate={createTask}
      />
    </main>
  );
}

function useCalendarStatus(enabled: boolean): CalendarStatus {
  const [status, setStatus] = useState<CalendarStatus>(USE_MOCKS ? MOCK_STATUS : OFFLINE_STATUS);

  useEffect(() => {
    if (!enabled || USE_MOCKS) return;
    let cancelled = false;
    const load = async () => {
      try {
        const next = await calendarApi.status();
        if (!cancelled) setStatus(next);
      } catch {
        if (!cancelled) setStatus(OFFLINE_STATUS);
      }
    };
    void load();
    const timer = setInterval(() => void load(), 20_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [enabled]);

  return status;
}

function TaskSkeleton() {
  return (
    <div className="space-y-2.5" aria-hidden>
      {[0.9, 0.7, 0.55, 0.4].map((opacity, index) => (
        <div
          key={index}
          className="h-[76px] animate-pulse rounded-2xl border border-white/5 bg-zinc-900/50"
          style={{ opacity }}
        />
      ))}
    </div>
  );
}
