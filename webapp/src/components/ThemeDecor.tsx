const FLOWERS = [
  { glyph: "✿", top: "5%", left: "1%", fontSize: "2.5rem" },
  { glyph: "❀", top: "2%", right: "8%", fontSize: "2.1rem" },
  { glyph: "✾", top: "31%", left: "-0.35rem", fontSize: "3.6rem" },
  { glyph: "❁", top: "44%", right: "-0.45rem", fontSize: "3.2rem" },
  { glyph: "✿", top: "62%", left: "6%", fontSize: "2rem" },
  { glyph: "❀", bottom: "14%", right: "22%", fontSize: "2.7rem" },
  { glyph: "✾", bottom: "7%", left: "18%", fontSize: "2.2rem" },
  { glyph: "❁", top: "78%", right: "2%", fontSize: "1.8rem" },
];

const STARS = [
  { glyph: "✦", top: "4%", right: "28%", fontSize: "0.5rem" },
  { glyph: "✧", top: "7%", left: "16%", fontSize: "0.62rem" },
  { glyph: "✦", top: "12%", left: "46%", fontSize: "0.42rem" },
  { glyph: "✧", top: "14%", right: "5%", fontSize: "1.15rem" },
  { glyph: "✦", top: "20%", left: "5%", fontSize: "0.78rem" },
  { glyph: "✧", top: "27%", right: "24%", fontSize: "0.55rem" },
  { glyph: "✦", top: "33%", right: "9%", fontSize: "0.72rem" },
  { glyph: "✧", top: "39%", left: "28%", fontSize: "0.48rem" },
  { glyph: "✦", top: "46%", right: "20%", fontSize: "1rem" },
  { glyph: "✧", top: "48%", left: "5%", fontSize: "0.55rem" },
  { glyph: "✦", top: "58%", right: "4%", fontSize: "0.68rem" },
  { glyph: "✧", top: "64%", left: "24%", fontSize: "0.5rem" },
  { glyph: "✦", top: "72%", right: "16%", fontSize: "1.05rem" },
  { glyph: "✦", bottom: "22%", left: "4%", fontSize: "1.35rem" },
  { glyph: "✦", bottom: "14%", left: "32%", fontSize: "0.58rem" },
  { glyph: "✧", bottom: "9%", right: "11%", fontSize: "0.9rem" },
  { glyph: "✦", bottom: "4%", right: "30%", fontSize: "0.46rem" },
];

export function ThemeDecor() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      {FLOWERS.map((flower) => (
        <span
          key={`${flower.glyph}-${flower.top ?? flower.bottom}-${flower.left ?? flower.right}`}
          className="theme-flower"
          style={{ top: flower.top, left: flower.left, right: flower.right, bottom: flower.bottom, fontSize: flower.fontSize }}
        >
          {flower.glyph}
        </span>
      ))}
      {STARS.map((star) => (
        <span
          key={`${star.glyph}-${star.top ?? star.bottom}-${star.left ?? star.right}`}
          className="theme-star"
          style={{ top: star.top, left: star.left, right: star.right, bottom: star.bottom, fontSize: star.fontSize }}
        >
          {star.glyph}
        </span>
      ))}
    </div>
  );
}
