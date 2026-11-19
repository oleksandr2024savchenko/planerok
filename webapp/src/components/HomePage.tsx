"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";

import { useAppUpdates } from "@/hooks/useAppUpdates";
import { TimerContext, useTimer } from "@/hooks/useTimer";
import { useTasks } from "@/hooks/useTasks";
import { calendarApi, USE_MOCKS, usersApi } from "@/lib/api";
import { cn } from "@/lib/cn";
import { CoupleContext, type Couple } from "@/lib/couple";
import { EASE, SOFT_MOVE } from "@/lib/motion";
import { setSurfaceColor } from "@/lib/telegram";
import {
  countByFilter,
  matchesAudience,
  matchesFilter,
  sortTasks,
  todayProgress,
  type AudienceId,
  type FilterId,
} from "@/lib/filters";
import type { CalendarStatus } from "@/lib/types";

import { AddTaskSheet, type TaskSlot } from "./AddTaskSheet";
import { ExternalCalendarSheet } from "./ExternalCalendarSheet";
import { CalendarBoard } from "./CalendarBoard";
import { DashboardHeader } from "./DashboardHeader";
import { EmptyState } from "./EmptyState";
import { Fab } from "./Fab";
import { TimerDock } from "./TimerDock";
import { AudiencePills, FilterPills } from "./FilterPills";
import { SettingsBlock } from "./SettingsBlock";
import { TaskList } from "./TaskList";
import { useTelegram } from "./TelegramProvider";
import { ViewModeSwitch, type ViewMode } from "./ViewModeSwitch";

// Demo mode plays the first account, with tasks from and for the partner.
const MOCK_COUPLE: Couple = { meId: 969740172, partnerName: "Таня" };
const MOCK_STATUS: CalendarStatus = { connected: true, live: true, last_sync_at: null };
const OFFLINE_STATUS: CalendarStatus = { connected: false, live: false, last_sync_at: null };

export function HomePage() {
  const { firstName, isReady } = useTelegram();
  const { tasks, isLoading, error, reload, createTask, updateTask, toggleTask, deleteTask } = useTasks({
    enabled: isReady || USE_MOCKS,
  });
  const [filter, setFilter] = useState<FilterId>("today");
  const [audience, setAudience] = useState<AudienceId>("all");
  const [view, setView] = useState<ViewMode>("list");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [feedsOpen, setFeedsOpen] = useState(false);
  const [slot, setSlot] = useState<TaskSlot | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const sync = useCalendarStatus(isReady || USE_MOCKS);
  const timerControls = useTimer({ enabled: isReady || USE_MOCKS, onSettled: () => void reload({ silent: true }) });
  const [couple, setCouple] = useState<Couple>(USE_MOCKS ? MOCK_COUPLE : { meId: null, partnerName: "Партнер" });
  useAppUpdates(sheetOpen || feedsOpen);

  const scoped = useMemo(
    () => tasks.filter((task) => matchesAudience(task, audience, couple.meId)),
    [tasks, audience, couple.meId],
  );
  const counts = useMemo(() => countByFilter(scoped), [scoped]);
  const visible = useMemo(
    () => sortTasks(scoped.filter((task) => matchesFilter(task, filter))),
    [scoped, filter],
  );
  const progress = useMemo(() => todayProgress(tasks, couple.meId), [tasks, couple.meId]);
  const ready = (isReady || USE_MOCKS) && !isLoading;

  useEffect(() => {
    if (!isReady || USE_MOCKS) return;
    let cancelled = false;
    usersApi
      .me()
      .then((me) => {
        if (cancelled) return;
        setCouple({ meId: me.telegram_id, partnerName: me.partner_first_name?.trim() || "Партнер" });
        const pink = me.theme === "pink";
        document.documentElement.dataset.theme = pink ? "pink" : "violet";
        try {
          localStorage.setItem("planer:theme", pink ? "pink" : "violet");
        } catch {
          // Private mode: the theme just loads a moment later next time.
        }
        document.querySelector('meta[name="theme-color"]')?.setAttribute("content", pink ? "#fff0f7" : "#12061f");
        // The pink theme is light, so Telegram's header follows it instead of staying black.
        if (pink) setSurfaceColor("#FFF0F7");
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [isReady]);

  const editing = tasks.find((task) => task.id === editingId) ?? null;

  function openSheet(nextSlot: TaskSlot | null = null) {
    setEditingId(null);
    setSlot(nextSlot);
    setSheetOpen(true);
  }

  function openTask(taskId: number) {
    setSlot(null);
    setEditingId(taskId);
    setSheetOpen(true);
  }

  return (
    <CoupleContext.Provider value={couple}>
    <TimerContext.Provider value={timerControls}>
    <main
      className={cn(
        "relative mx-auto min-h-dvh px-5 pt-6 transition-[padding] duration-300",
        timerControls.timer || timerControls.finished ? "pb-40" : "pb-28",
        view === "calendar" ? "max-w-3xl" : "max-w-lg",
      )}
    >
      <DashboardHeader
        firstName={firstName}
        done={progress.done}
        total={progress.total}
        settings={<SettingsBlock status={sync} onConnect={() => setFeedsOpen(true)} />}
      />

      <div className="mt-5 flex justify-end">
        <ViewModeSwitch value={view} onChange={setView} />
      </div>

      {view === "list" && (
        <div className="mt-4">
          <AudiencePills value={audience} onChange={setAudience} />
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

      {/* Switching view, filter or audience fades the old list out before the new one rises in. */}
      <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={ready ? `${view}:${view === "list" ? `${filter}:${audience}` : audience}` : "loading"}
        className="mt-5"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -6, transition: { duration: 0.16, ease: EASE } }}
        transition={SOFT_MOVE}
      >
        {!ready ? (
          <TaskSkeleton />
        ) : view === "calendar" ? (
          <CalendarBoard
            tasks={scoped}
            onSlot={(date, time) => openSheet({ date, time })}
            onOpenTask={openTask}
          />
        ) : visible.length === 0 ? (
          <EmptyState filter={filter} onAdd={() => openSheet(null)} />
        ) : (
          <TaskList tasks={visible} filter={filter} onToggle={toggleTask} onOpen={openTask} />
        )}
      </motion.div>
      </AnimatePresence>

      {USE_MOCKS && (
        <p className="mt-8 text-center text-[11px] tracking-wide text-zinc-600">Демо-дані · API ще не підключено</p>
      )}

      <Fab hidden={sheetOpen} onClick={() => openSheet(null)} />
      <TimerDock controls={timerControls} />
      <AddTaskSheet
        open={sheetOpen}
        slot={slot}
        task={editing}
        onClose={() => setSheetOpen(false)}
        onCreate={createTask}
        onUpdate={updateTask}
        onToggle={toggleTask}
        onDelete={deleteTask}
      />
      <ExternalCalendarSheet
        open={feedsOpen}
        onClose={() => setFeedsOpen(false)}
        onChanged={() => void reload({ silent: true })}
      />
    </main>
    </TimerContext.Provider>
    </CoupleContext.Provider>
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
