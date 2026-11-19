import { createContext, useContext } from "react";

import type { Task } from "./types";

/** Who does a task, seen from the person looking at it. */
export type Assignee = "me" | "partner" | "shared";

export interface Couple {
  meId: number | null;
  partnerName: string;
}

export const CoupleContext = createContext<Couple>({ meId: null, partnerName: "Партнер" });

export function useCouple(): Couple {
  return useContext(CoupleContext);
}

export function assigneeOf(task: Pick<Task, "is_shared" | "owner_id">, meId: number | null): Assignee {
  if (task.is_shared) return "shared";
  if (meId === null || task.owner_id == null || task.owner_id === meId) return "me";
  return "partner";
}

/** A task the partner wrote for me (shown as «Від: …» on the card). */
export function isFromPartner(task: Pick<Task, "is_shared" | "owner_id" | "created_by_id">, meId: number | null): boolean {
  return (
    !task.is_shared &&
    meId !== null &&
    task.created_by_id != null &&
    task.created_by_id !== meId &&
    assigneeOf(task, meId) === "me"
  );
}
