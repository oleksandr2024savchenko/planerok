"use client";

import { Check, Pencil, Plus, Trash2 } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { cn } from "@/lib/cn";
import { haptic } from "@/lib/telegram";
import type { Space, SpaceInput } from "@/lib/types";

import { BottomSheet, DEFAULT_SPACE_COLOR, SPACE_COLORS, fieldClass } from "./BottomSheet";
import { SpaceDot } from "./SpacePills";

const ROLE_LABELS: Record<Space["role"], string> = { owner: "власник", editor: "редактор", viewer: "перегляд" };

interface SpacesSheetProps {
  open: boolean;
  spaces: Space[];
  onClose: () => void;
  onCreate: (data: SpaceInput & { name: string }) => Promise<unknown>;
  onUpdate: (id: number, data: SpaceInput) => Promise<unknown>;
  onRemove: (id: number) => Promise<unknown>;
}

export function SpacesSheet({ open, spaces, onClose, onCreate, onUpdate, onRemove }: SpacesSheetProps) {
  const [name, setName] = useState("");
  const [color, setColor] = useState<string>(DEFAULT_SPACE_COLOR);
  const [editing, setEditing] = useState<number | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setName("");
    setColor(DEFAULT_SPACE_COLOR);
    setEditing(null);
    setConfirmDelete(null);
    setError(null);
  }, [open]);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      haptic.notify("success");
      return true;
    } catch (err) {
      haptic.notify("error");
      const message = err instanceof Error ? err.message : "";
      setError(message.includes("already exists") ? "Простір з такою назвою вже є" : "Не вдалося зберегти зміни");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    if (await run(() => onCreate({ name: trimmed, color }))) setName("");
  }

  return (
    <BottomSheet
      open={open}
      title="Простори"
      subtitle="Окремі списки для різних сфер. Задачу можна додати й голосом: «звіт для бізнесу»."
      onClose={onClose}
    >
      <ul className="space-y-2">
        {spaces.map((space) => (
          <li key={space.id}>
            {editing === space.id ? (
              <SpaceEditor
                space={space}
                busy={busy}
                onCancel={() => setEditing(null)}
                onSave={async (data) => {
                  if (await run(() => onUpdate(space.id, data))) setEditing(null);
                }}
              />
            ) : (
              <div className="flex items-center gap-3 rounded-2xl border border-white/5 bg-zinc-900/60 px-3.5 py-3">
                <SpaceDot color={space.color} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[15px] font-medium text-zinc-100">{space.name}</p>
                  <p className="text-[11px] text-zinc-500">
                    {space.kind === "personal" ? "за замовчуванням · " : ""}
                    {ROLE_LABELS[space.role]}
                  </p>
                </div>
                {space.role === "owner" && (
                  <button
                    type="button"
                    aria-label={`Редагувати ${space.name}`}
                    onClick={() => setEditing(space.id)}
                    className="flex size-8 items-center justify-center rounded-full text-zinc-500 transition hover:text-zinc-100"
                  >
                    <Pencil className="size-3.5" />
                  </button>
                )}
                {space.role === "owner" && space.kind !== "personal" && (
                  <button
                    type="button"
                    aria-label={confirmDelete === space.id ? `Підтвердити видалення ${space.name}` : `Видалити ${space.name}`}
                    disabled={busy}
                    onClick={async () => {
                      if (confirmDelete !== space.id) {
                        haptic.impact("light");
                        setConfirmDelete(space.id);
                        return;
                      }
                      await run(() => onRemove(space.id));
                      setConfirmDelete(null);
                    }}
                    className={cn(
                      "flex h-8 items-center justify-center rounded-full px-2 text-xs transition",
                      confirmDelete === space.id
                        ? "border border-rose-500/40 bg-rose-500/10 text-rose-300"
                        : "text-zinc-500 hover:text-rose-300",
                    )}
                  >
                    {confirmDelete === space.id ? "Видалити разом із задачами?" : <Trash2 className="size-3.5" />}
                  </button>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>

      <form onSubmit={handleCreate} className="space-y-3 rounded-2xl border border-dashed border-white/10 p-3.5">
        <p className="text-xs font-medium uppercase tracking-wider text-zinc-500">Новий простір</p>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Напр. Бізнес, Дім, Спільне"
          maxLength={64}
          className={fieldClass}
        />
        <ColorPicker value={color} onChange={setColor} />
        <button
          type="submit"
          disabled={busy || !name.trim()}
          className="flex w-full items-center justify-center gap-1.5 rounded-2xl bg-gradient-to-r from-violet-600 to-fuchsia-500 py-3 text-sm font-semibold text-white shadow-[0_0_24px_rgba(168,85,247,0.35)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Plus className="size-4" />
          Створити простір
        </button>
      </form>

      {error && <p className="text-sm text-rose-400">{error}</p>}
    </BottomSheet>
  );
}

function SpaceEditor({
  space,
  busy,
  onSave,
  onCancel,
}: {
  space: Space;
  busy: boolean;
  onSave: (data: SpaceInput) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(space.name);
  const [color, setColor] = useState(space.color ?? DEFAULT_SPACE_COLOR);

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (name.trim()) onSave({ name: name.trim(), color });
      }}
      className="space-y-3 rounded-2xl border border-purple-500/30 bg-zinc-900/60 p-3.5"
    >
      <input value={name} onChange={(event) => setName(event.target.value)} maxLength={64} className={fieldClass} autoFocus />
      <ColorPicker value={color} onChange={setColor} />
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="flex-1 rounded-xl border border-white/5 bg-zinc-900 py-2 text-sm text-zinc-400 transition hover:text-zinc-100"
        >
          Скасувати
        </button>
        <button
          type="submit"
          disabled={busy || !name.trim()}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-purple-500/50 bg-purple-500/15 py-2 text-sm font-medium text-purple-100 transition disabled:opacity-40"
        >
          <Check className="size-4" />
          Зберегти
        </button>
      </div>
    </form>
  );
}

function ColorPicker({ value, onChange }: { value: string; onChange: (color: string) => void }) {
  return (
    <div className="flex gap-2.5" role="radiogroup" aria-label="Колір">
      {SPACE_COLORS.map((color) => (
        <button
          key={color}
          type="button"
          role="radio"
          aria-checked={value === color}
          aria-label={color}
          onClick={() => {
            haptic.selection();
            onChange(color);
          }}
          className={cn(
            "size-7 rounded-full border-2 transition",
            value === color ? "scale-110 border-white/80" : "border-transparent opacity-70 hover:opacity-100",
          )}
          style={{ backgroundColor: color, boxShadow: value === color ? `0 0 14px ${color}aa` : undefined }}
        />
      ))}
    </div>
  );
}
