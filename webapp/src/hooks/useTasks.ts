"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { tasksApi, USE_MOCKS } from "@/lib/api";
import { buildMockTask, createMockTasks } from "@/lib/mock-data";
import { remindAtFor } from "@/lib/reminders";
import type { Task, TaskCreate, TaskUpdate } from "@/lib/types";

/** `enabled` should flip once the Telegram SDK is initialised, so requests carry initData. */
export function useTasks({ enabled }: { enabled: boolean }) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const busy = useRef(0);
  const generation = useRef(0);

  const reload = useCallback(async (options?: { silent?: boolean }) => {
    if (options?.silent && (busy.current > 0 || document.visibilityState === "hidden")) return;
    const token = ++generation.current;
    if (!options?.silent) setIsLoading(true);
    if (!options?.silent) setError(null);
    try {
      const next = USE_MOCKS ? createMockTasks() : await tasksApi.list();
      if (token !== generation.current) return;
      if (options?.silent && busy.current > 0) return;
      setTasks(next);
      if (options?.silent) setError(null);
    } catch (err) {
      if (token !== generation.current || options?.silent) return;
      setError(err instanceof Error ? err.message : "Не вдалося завантажити задачі");
    } finally {
      if (!options?.silent && token === generation.current) setIsLoading(false);
    }
  }, []);

  // Loaded after mount: mock data depends on the current time and must not be prerendered.
  useEffect(() => {
    if (enabled) void reload();
  }, [enabled, reload]);

  useEffect(() => {
    if (!enabled || USE_MOCKS) return;
    const pull = () => void reload({ silent: true });
    const timer = window.setInterval(pull, 8_000);
    document.addEventListener("visibilitychange", pull);
    window.addEventListener("focus", pull);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", pull);
      window.removeEventListener("focus", pull);
    };
  }, [enabled, reload]);

  const updateTask = useCallback(
    async (id: number, patch: TaskUpdate) => {
      const previous = tasks.find((task) => task.id === id);
      const completionOnly =
        patch.is_completed !== undefined && Object.keys(patch).every((key) => key === "is_completed");
      if (!previous || (previous.read_only && !completionOnly)) return;
      busy.current += 1;
      generation.current += 1;
      setTasks((current) => current.map((task) => (task.id === id ? withLocalReminder({ ...task, ...patch }, patch) : task)));
      if (USE_MOCKS) {
        busy.current -= 1;
        return;
      }
      try {
        const saved = await tasksApi.update(id, patch);
        setTasks((current) => current.map((task) => (task.id === id ? saved : task)));
      } catch (err) {
        setTasks((current) => current.map((task) => (task.id === id ? previous : task)));
        const message = err instanceof Error ? err.message : "Не вдалося оновити задачу";
        setError(message);
        throw new Error(message);
      } finally {
        busy.current -= 1;
      }
    },
    [tasks],
  );

  const toggleTask = useCallback(
    (id: number) => {
      const task = tasks.find((item) => item.id === id);
      if (task) void updateTask(id, { is_completed: !task.is_completed }).catch(() => undefined);
    },
    [tasks, updateTask],
  );

  const createTask = useCallback(async (data: TaskCreate) => {
    busy.current += 1;
    generation.current += 1;
    try {
      const created = USE_MOCKS ? buildMockTask(data) : await tasksApi.create(data);
      setTasks((current) => [created, ...current]);
      return created;
    } finally {
      busy.current -= 1;
    }
  }, []);

  const deleteTask = useCallback(
    async (id: number) => {
      const snapshot = tasks;
      busy.current += 1;
      generation.current += 1;
      setTasks((current) => current.filter((task) => task.id !== id));
      if (USE_MOCKS) {
        busy.current -= 1;
        return;
      }
      try {
        await tasksApi.remove(id);
      } catch (err) {
        setTasks(snapshot);
        setError(err instanceof Error ? err.message : "Не вдалося видалити задачу");
      } finally {
        busy.current -= 1;
      }
    },
    [tasks],
  );

  return { tasks, isLoading, error, reload, createTask, updateTask, toggleTask, deleteTask };
}

/** The server derives `remind_at` from the offset; mirror that so the card (and demo mode) updates at once. */
function withLocalReminder(task: Task, patch: TaskUpdate): Task {
  if (patch.remind_at !== undefined || patch.remind_before_minutes == null) return task;
  return { ...task, remind_at: remindAtFor(task, patch.remind_before_minutes) };
}
