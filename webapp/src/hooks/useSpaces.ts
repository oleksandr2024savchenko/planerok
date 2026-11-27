"use client";

import { useCallback, useEffect, useState } from "react";

import { spacesApi, USE_MOCKS } from "@/lib/api";
import { MOCK_SPACES } from "@/lib/mock-data";
import type { Space, SpaceInput } from "@/lib/types";

let mockSpaceId = 100;

/** Spaces the user belongs to; the personal one always comes first. */
export function useSpaces({ enabled }: { enabled: boolean }) {
  const [spaces, setSpaces] = useState<Space[]>([]);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setSpaces(USE_MOCKS ? MOCK_SPACES : await spacesApi.list());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не вдалося завантажити простори");
    }
  }, []);

  useEffect(() => {
    if (enabled) void reload();
  }, [enabled, reload]);

  const createSpace = useCallback(async (data: SpaceInput & { name: string }) => {
    const created: Space = USE_MOCKS
      ? { id: ++mockSpaceId, name: data.name, color: data.color ?? null, icon: null, kind: "shared", role: "owner" }
      : await spacesApi.create(data);
    setSpaces((current) => [...current, created]);
    return created;
  }, []);

  const updateSpace = useCallback(async (id: number, data: SpaceInput) => {
    const saved = USE_MOCKS ? null : await spacesApi.update(id, data);
    setSpaces((current) => current.map((space) => (space.id === id ? (saved ?? { ...space, ...data }) : space)));
  }, []);

  const removeSpace = useCallback(async (id: number) => {
    if (!USE_MOCKS) await spacesApi.remove(id);
    setSpaces((current) => current.filter((space) => space.id !== id));
  }, []);

  return { spaces, error, reload, createSpace, updateSpace, removeSpace };
}
