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
