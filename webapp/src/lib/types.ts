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
  start_time: string | null;
  end_time: string | null;
  google_event_id: string | null;
  sync_token: string | null;
  is_completed: boolean;
  is_shared?: boolean;
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
  start_time?: string | null;
  end_time?: string | null;
  is_shared?: boolean;
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
