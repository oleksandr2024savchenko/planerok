"use client";

import { useCallback, useEffect, useState } from "react";

import { tasksApi, USE_MOCKS } from "@/lib/api";
import { buildMockTask, createMockTasks } from "@/lib/mock-data";
import type { Task, TaskCreate, TaskUpdate } from "@/lib/types";

/** `enabled` should flip once the Telegram SDK is initialised, so requests carry initData. */
export function useTasks({ enabled }: { enabled: boolean }) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setTasks(USE_MOCKS ? createMockTasks() : await tasksApi.list());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не вдалося завантажити задачі");
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Loaded after mount: mock data depends on the current time and must not be prerendered.
  useEffect(() => {
    if (enabled) void reload();
  }, [enabled, reload]);

  const updateTask = useCallback(
    async (id: number, patch: TaskUpdate) => {
      const previous = tasks.find((task) => task.id === id);
      if (!previous) return;
      setTasks((current) => current.map((task) => (task.id === id ? { ...task, ...patch } : task)));
      if (USE_MOCKS) return;
      try {
        const saved = await tasksApi.update(id, patch);
        setTasks((current) => current.map((task) => (task.id === id ? saved : task)));
      } catch (err) {
        setTasks((current) => current.map((task) => (task.id === id ? previous : task)));
        setError(err instanceof Error ? err.message : "Не вдалося оновити задачу");
      }
    },
    [tasks],
  );

  const toggleTask = useCallback(
    (id: number) => {
      const task = tasks.find((item) => item.id === id);
      if (task) void updateTask(id, { is_completed: !task.is_completed });
    },
    [tasks, updateTask],
  );

  const createTask = useCallback(async (data: TaskCreate) => {
    const created = USE_MOCKS ? buildMockTask(data) : await tasksApi.create(data);
    setTasks((current) => [created, ...current]);
    return created;
  }, []);

  const deleteTask = useCallback(
    async (id: number) => {
      const snapshot = tasks;
      setTasks((current) => current.filter((task) => task.id !== id));
      if (USE_MOCKS) return;
      try {
        await tasksApi.remove(id);
      } catch (err) {
        setTasks(snapshot);
        const message = err instanceof Error ? err.message : "Не вдалося видалити задачу";
        setError(message);
        throw err instanceof Error ? err : new Error(message);
      }
    },
    [tasks],
  );

  return { tasks, isLoading, error, reload, createTask, updateTask, toggleTask, deleteTask };
}
