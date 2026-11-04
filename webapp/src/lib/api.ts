import { getInitData } from "./telegram";
import type { Task, TaskCreate, TaskScope, TaskUpdate } from "./types";

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
