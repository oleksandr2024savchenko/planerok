export type Priority = "low" | "medium" | "high";

/** Mirrors `TaskRead` from the backend. Datetimes are ISO strings with offset. */
export interface Task {
  id: number;
  title: string;
  description: string | null;
  category: string | null;
  priority: Priority;
  deadline: string | null;
  remind_at: string | null;
  /** Relative reminder in minutes before the event; the server derives `remind_at` from it. */
  remind_before_minutes?: number | null;
  start_time: string | null;
  end_time: string | null;
  google_event_id: string | null;
  sync_token: string | null;
  is_completed: boolean;
  is_shared?: boolean;
  owner_id?: number | null;
  assigned_to_id?: number | null;
  created_by_id?: number | null;
  /** Seconds spent in finished focus sessions. */
  focused_seconds?: number;
  created_at: string;
  read_only?: boolean;
  all_day?: boolean;
  source_name?: string | null;
}

export interface CalendarFeed {
  id: number;
  name: string;
  host: string;
  last_sync_at: string | null;
  last_error: string | null;
  event_count: number;
}

export interface TaskCreate {
  title: string;
  description?: string | null;
  category?: string | null;
  priority?: Priority;
  deadline?: string | null;
  remind_at?: string | null;
  remind_before_minutes?: number | null;
  start_time?: string | null;
  end_time?: string | null;
  is_shared?: boolean;
  /** Who does it, seen from the sender: me, the partner, or both. */
  assignee?: "me" | "partner" | "shared";
}

export interface CalendarStatus {
  connected: boolean;
  live: boolean;
  last_sync_at: string | null;
}

export type TaskUpdate = Partial<TaskCreate> & { is_completed?: boolean };

export type TaskScope = "today" | "upcoming" | "all";

export const CATEGORIES = ["робота", "навчання", "тренування", "особисте"] as const;
export type Category = (typeof CATEGORIES)[number];

export type TimerKind = "focus" | "break";

/** Mirrors `TimerRead`: the one live timer of the current person. */
export interface Timer {
  id: number;
  task_id: number;
  task_title: string;
  kind: TimerKind;
  status: "running" | "paused";
  duration_seconds: number;
  remaining_seconds: number;
  task_focused_seconds: number;
  server_now: string;
}
