import { getInitData } from "./telegram";
import type { CalendarFeed, CalendarStatus, ScheduleEvent, SchedulePreview, Task, TaskCreate, TaskScope, TaskUpdate, Timer, TimerKind } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
export const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS !== "false" || !API_URL;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": getInitData(),
      ...init.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, body?.detail ?? response.statusText);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const tasksApi = {
  list(params: { scope?: TaskScope; category?: string } = {}) {
    const query = new URLSearchParams(
      Object.entries(params).filter((entry): entry is [string, string] => Boolean(entry[1])),
    );
    const suffix = query.size ? `?${query}` : "";
    return request<Task[]>(`/tasks${suffix}`);
  },
  create(data: TaskCreate) {
    return request<Task>("/tasks", { method: "POST", body: JSON.stringify(data) });
  },
  update(id: number, data: TaskUpdate) {
    return request<Task>(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(data) });
  },
  remove(id: number) {
    return request<void>(`/tasks/${id}`, { method: "DELETE" });
  },
};

export const timerApi = {
  current: () => request<Timer | null>("/tasks/timer"),
  start: (taskId: number, minutes: number, kind: TimerKind = "focus") =>
    request<Timer>("/tasks/timer", { method: "POST", body: JSON.stringify({ task_id: taskId, minutes, kind }) }),
  pause: () => request<Timer>("/tasks/timer/pause", { method: "POST" }),
  resume: () => request<Timer>("/tasks/timer/resume", { method: "POST" }),
  stop: () => request<void>("/tasks/timer/stop", { method: "POST" }),
};

export const importApi = {
  preview: (fileBase64: string, filename?: string) =>
    request<SchedulePreview>("/tasks/import/pdf", {
      method: "POST",
      body: JSON.stringify({ file_base64: fileBase64, filename }),
    }),
  commit: (payload: {
    events: ScheduleEvent[];
    assignee: "me" | "partner" | "shared";
    category: string | null;
    remind_before_minutes: number | null;
    title: string | null;
  }) => request<{ created: number; skipped: number }>("/tasks/import", { method: "POST", body: JSON.stringify(payload) }),
};

export const calendarApi = {
  status: () => request<CalendarStatus>("/calendar/status"),
  feeds: () => request<CalendarFeed[]>("/calendar/feeds"),
  connect: (url: string, name?: string) =>
    request<CalendarFeed>("/calendar/feeds", {
      method: "POST",
      body: JSON.stringify({ url, name: name || null }),
    }),
  disconnect: (id: number) => request<void>(`/calendar/feeds/${id}`, { method: "DELETE" }),
};

export interface Me {
  telegram_id: number;
  theme: string;
  partner_telegram_id: number | null;
  first_name?: string | null;
  partner_first_name?: string | null;
}

export const usersApi = {
  me: () => request<Me>("/me"),
};
