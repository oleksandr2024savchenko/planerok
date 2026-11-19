import { useId, type CSSProperties } from "react";

interface FlowerProps {
  className?: string;
  style?: CSSProperties;
  /** sakura: five notched petals; daisy: eight round petals. */
  variant?: "sakura" | "daisy";
  petal?: string;
  petalEdge?: string;
  center?: string;
}

const SAKURA_PETAL = "M0 -7 C -15 -18 -17 -38 -7 -46 L 0 -39 L 7 -46 C 17 -38 15 -18 0 -7 Z";

/** Decorative flower drawn in SVG; colours default to the pink theme's candy palette. */
export function Flower({
  className,
  style,
  variant = "sakura",
  petal = "#ffc2e2",
  petalEdge = "#ff4fa8",
  center = "#ffe27a",
}: FlowerProps) {
  const id = useId().replace(/:/g, "");
  const angles = variant === "sakura" ? [0, 72, 144, 216, 288] : [0, 45, 90, 135, 180, 225, 270, 315];

  return (
    <svg viewBox="-50 -50 100 100" className={className} style={style} aria-hidden focusable="false">
      <defs>
        <radialGradient id={`p${id}`} cx="0" cy="0" r="48" gradientUnits="userSpaceOnUse">
          <stop offset="0.15" stopColor="#ffffff" />
          <stop offset="0.55" stopColor={petal} />
          <stop offset="1" stopColor={petalEdge} />
        </radialGradient>
      </defs>
      {angles.map((angle) =>
        variant === "sakura" ? (
          <path key={angle} d={SAKURA_PETAL} fill={`url(#p${id})`} transform={`rotate(${angle})`} />
        ) : (
          <ellipse key={angle} cx="0" cy="-27" rx="10" ry="20" fill={`url(#p${id})`} transform={`rotate(${angle})`} />
        ),
      )}
      <circle r={variant === "sakura" ? 8 : 12} fill={center} />
      {variant === "sakura" &&
        [0, 72, 144, 216, 288].map((angle) => (
          <circle key={angle} cx="0" cy="-13" r="2.2" fill={center} transform={`rotate(${angle + 36})`} />
        ))}
    </svg>
  );
}
