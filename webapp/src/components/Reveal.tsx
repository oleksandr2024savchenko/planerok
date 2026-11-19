"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";

import { EASE } from "@/lib/motion";

/** Opens and closes its content by height, so the form around it glides instead of jumping. */
export function Reveal({ show, children, className }: { show: boolean; children: ReactNode; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <AnimatePresence initial={false}>
      {show && (
        <motion.div
          className={className}
          style={{ overflow: "hidden" }}
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={reduce ? { duration: 0 } : { height: { duration: 0.36, ease: EASE }, opacity: { duration: 0.26 } }}
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
