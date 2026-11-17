export const EASE = [0.22, 1, 0.36, 1] as [number, number, number, number];

export const SOFT_MOVE = {
  type: "tween" as const,
  duration: 0.32,
  ease: EASE,
};
