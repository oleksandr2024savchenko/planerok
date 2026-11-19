"use client";

import type { CSSProperties } from "react";

import { Flower } from "./Flower";

interface Bloom {
  top: string;
  left: string;
  size: number;
  rotate: number;
  opacity: number;
  duration: number;
  delay: number;
  variant: "sakura" | "daisy";
  petal?: string;
  edge?: string;
}

// Mostly along the edges, so the task list in the middle stays readable.
const BLOOMS: Bloom[] = [
  { top: "3%", left: "78%", size: 64, rotate: 12, opacity: 0.85, duration: 10, delay: 0, variant: "sakura" },
  { top: "11%", left: "90%", size: 26, rotate: -20, opacity: 0.7, duration: 8, delay: 1.2, variant: "daisy", petal: "#fff", edge: "#ffb3da" },
  { top: "1%", left: "58%", size: 22, rotate: 40, opacity: 0.6, duration: 7, delay: 0.6, variant: "sakura" },
  { top: "24%", left: "-4%", size: 48, rotate: -15, opacity: 0.55, duration: 11, delay: 2, variant: "sakura", petal: "#ffd6ec" },
  { top: "38%", left: "92%", size: 34, rotate: 25, opacity: 0.55, duration: 9, delay: 0.3, variant: "daisy", petal: "#fff", edge: "#ff9fd0" },
  { top: "52%", left: "-2%", size: 24, rotate: 8, opacity: 0.5, duration: 8.5, delay: 1.8, variant: "daisy", petal: "#fff", edge: "#ffb3da" },
  { top: "63%", left: "88%", size: 52, rotate: -30, opacity: 0.5, duration: 12, delay: 0.9, variant: "sakura" },
  { top: "76%", left: "3%", size: 40, rotate: 18, opacity: 0.5, duration: 10, delay: 2.6, variant: "sakura", petal: "#ffd6ec" },
  { top: "88%", left: "60%", size: 28, rotate: -8, opacity: 0.45, duration: 9.5, delay: 1.1, variant: "daisy", petal: "#fff", edge: "#ff9fd0" },
  { top: "93%", left: "18%", size: 56, rotate: 30, opacity: 0.45, duration: 13, delay: 0.4, variant: "sakura" },
];

/** Floating flowers behind the pink theme's content. */
export function FlowerDecor() {
  return (
    <div className="pointer-events-none fixed inset-0 overflow-hidden" aria-hidden>
      {BLOOMS.map((bloom, index) => (
        <div
          key={index}
          className="flower-float absolute"
          style={
            {
              top: bloom.top,
              left: bloom.left,
              width: bloom.size,
              height: bloom.size,
              opacity: bloom.opacity,
              "--r": `${bloom.rotate}deg`,
              "--d": `${bloom.duration}s`,
              "--delay": `${bloom.delay}s`,
              filter: "drop-shadow(0 0 10px rgb(255 46 151 / 0.35))",
            } as CSSProperties
          }
        >
          <Flower variant={bloom.variant} petal={bloom.petal} petalEdge={bloom.edge} className="size-full" />
        </div>
      ))}
    </div>
  );
}
