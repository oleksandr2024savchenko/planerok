"use client";

import { motion } from "framer-motion";
import { Plus } from "lucide-react";

import { SOFT_MOVE } from "@/lib/motion";
import { haptic } from "@/lib/telegram";

interface FabProps {
  onClick: () => void;
  hidden?: boolean;
}

export function Fab({ onClick, hidden }: FabProps) {
  return (
    <motion.button
      type="button"
      aria-label="Додати задачу"
      aria-hidden={hidden}
      tabIndex={hidden ? -1 : 0}
      onClick={() => {
        haptic.impact("medium");
        onClick();
      }}
      initial={false}
      animate={hidden ? { opacity: 0, scale: 0.86, y: 10 } : { opacity: 1, scale: 1, y: 0 }}
      whileTap={hidden ? undefined : { scale: 0.94 }}
      transition={SOFT_MOVE}
      className="fixed right-5 z-30 flex size-14 items-center justify-center rounded-full bg-purple-600 text-white shadow-[0_0_25px_rgba(168,85,247,0.6)] hover:bg-purple-500 hover:shadow-[0_0_32px_rgba(168,85,247,0.8)] disabled:pointer-events-none"
      style={{ bottom: "max(1.25rem, calc(env(safe-area-inset-bottom) + 0.75rem))" }}
      disabled={hidden}
    >
      <Plus className="size-7" strokeWidth={2.25} />
    </motion.button>
  );
}
