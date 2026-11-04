"use client";

import { useMemo, useState } from "react";

import { useCalendarStatus } from "@/hooks/useCalendarStatus";
import { useTasks } from "@/hooks/useTasks";
import { USE_MOCKS } from "@/lib/api";
import { haptic } from "@/lib/telegram";
import { countByFilter, matchesFilter, sortTasks, todayProgress, type FilterId } from "@/lib/filters";

import { AddTaskSheet } from "./AddTaskSheet";
import { DashboardHeader } from "./DashboardHeader";
import { EmptyState } from "./EmptyState";
import { Fab } from "./Fab";
import { FilterPills } from "./FilterPills";
import { TaskList } from "./TaskList";
import { useTelegram } from "./TelegramProvider";

export function HomePage() {
  const { firstName, isReady } = useTelegram();
  const { tasks, isLoading, error, reload, createTask, toggleTask, deleteTask } = useTasks({
    enabled: isReady || USE_MOCKS,
  });
  const calendar = useCalendarStatus(isReady);
  const [filter, setFilter] = useState<FilterId>("today");
  const [sheetOpen, setSheetOpen] = useState(false);

  const counts = useMemo(() => countByFilter(tasks), [tasks]);
  const visible = useMemo(
    () => sortTasks(tasks.filter((task) => matchesFilter(task, filter))),
    [tasks, filter],
  );
  const progress = useMemo(() => todayProgress(tasks), [tasks]);
  const showList = isReady && !isLoading;

  async function handleDelete(id: number) {
    try {
      await deleteTask(id);
      haptic.notify("success");
    } catch {
      haptic.notify("error");
    }
  }

  return (
    <main className="relative mx-auto min-h-dvh max-w-lg px-5 pb-28 pt-6">
      <DashboardHeader firstName={firstName} done={progress.done} total={progress.total} calendar={calendar} />

      <div className="mt-5">
        <FilterPills value={filter} counts={counts} onChange={setFilter} />
      </div>

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
        {!showList ? (
          <TaskSkeleton />
        ) : visible.length === 0 ? (
          <EmptyState filter={filter} onAdd={() => setSheetOpen(true)} />
        ) : (
          <TaskList tasks={visible} filter={filter} onToggle={toggleTask} onDelete={(id) => void handleDelete(id)} />
        )}
      </div>

      {USE_MOCKS && (
        <p className="mt-8 text-center text-[11px] tracking-wide text-zinc-600">Демо-дані · API ще не підключено</p>
      )}

      <Fab hidden={sheetOpen} onClick={() => setSheetOpen(true)} />
      <AddTaskSheet open={sheetOpen} onClose={() => setSheetOpen(false)} onCreate={createTask} />
    </main>
  );
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
