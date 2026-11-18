export const EASE = [0.22, 1, 0.36, 1] as [number, number, number, number];

/** Calm ease-out for fades and small moves. */
export const SOFT_MOVE = {
  type: "tween" as const,
  duration: 0.38,
  ease: EASE,
};

/** Selection pills and layout shifts: a soft spring with no bounce. */
export const GLIDE = {
  type: "spring" as const,
  stiffness: 320,
  damping: 36,
  mass: 0.9,
};

/** Bottom sheets: slides in a touch slower and settles without a wobble. */
export const SHEET = {
  type: "spring" as const,
  stiffness: 240,
  damping: 32,
  mass: 1,
};

/** Fade for things appearing in place (fills, hints). */
export const FADE = { duration: 0.3, ease: EASE };

/**
 * Per-person motion tuning. The violet account runs on a 120 Hz phone: longer, silkier curves
 * with blur. The pink account runs on 60 Hz: shorter moves and no live blur, so every one of
 * the fewer frames lands on time. Picked from the active theme.
 */
export type MotionProfile = "fluid" | "lite";

/** iOS-like sheet curve: quick start, long gentle settle. */
const SHEET_CURVE = [0.32, 0.72, 0, 1] as [number, number, number, number];

export const SHEET_MOTION: Record<
  MotionProfile,
  { open: { duration: number; ease: typeof SHEET_CURVE }; close: { duration: number; ease: typeof EASE }; backdrop: number }
> = {
  fluid: { open: { duration: 0.52, ease: SHEET_CURVE }, close: { duration: 0.34, ease: EASE }, backdrop: 0.42 },
  lite: { open: { duration: 0.34, ease: SHEET_CURVE }, close: { duration: 0.24, ease: EASE }, backdrop: 0.26 },
};
