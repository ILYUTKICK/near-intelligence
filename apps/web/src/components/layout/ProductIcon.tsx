const paths = {
  home: "m2 7 6-5 6 5v7H2zm4 7V9h4v5",
  book: "M8 4C6 2 3 2 1.5 3v10C3 12 6 12 8 14c2-2 5-2 6.5-1V3C13 2 10 2 8 4v10",
  chart: "M2 2v12h12M5 11V7m3 4V4m3 7V6",
  globe: "M14 8a6 6 0 1 0-12 0 6 6 0 0 0 12 0ZM2 8h12M8 2a10 10 0 0 1 0 12A10 10 0 0 1 8 2Z",
  layers: "m1.5 5 6.5-3 6.5 3L8 8zm0 3L8 11l6.5-3m-13 3L8 14l6.5-3",
  leaf: "M2 13C2 5 6 2 14 2c0 8-4 12-12 11Zm0 1 7-7",
  grid: "M2 2h4v4H2zm8 0h4v4h-4zm0 8h4v4h-4zm-8 0h4v4H2z",
  filter: "M2 3h12M4.5 7.5h7m-5 4.5h3",
  user: "M11 5a3 3 0 1 0-6 0 3 3 0 0 0 6 0ZM2.5 14c0-3 2.5-4.5 5.5-4.5s5.5 1.5 5.5 4.5",
  settings: "m6 2 4 0 .6 2 2 .5 1.5 3-1.4 1.8.2 2-3 1.8-1.9-.8-1.9.8-3-1.8.2-2L1.9 7.5l1.5-3 2-.5Zm4.4 6a2.4 2.4 0 1 0-4.8 0 2.4 2.4 0 0 0 4.8 0Z",
  search: "M10.8 6.8a4 4 0 1 0-8 0 4 4 0 0 0 8 0Zm-.9 3.1 3.5 3.5",
  arrow: "M2.75 8h10.5m-4-4 4 4-4 4",
  shield: "M8 1.75 14 4v4.1c0 3.4-3.8 5.5-6 6.15-2.2-.65-6-2.75-6-6.15V4Zm-2.5 6.5 1.75 1.7 3.25-3.5",
  document: "M3.25 1.75h6.5l3 3v9.5h-9.5zm6.5 0V5h3M5.5 8h5m-5 2.75h5",
} as const;

export type ProductIconName = keyof typeof paths;

export function ProductIcon({ name, className = "size-4" }: { name: ProductIconName; className?: string }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 16 16" className={className}>
      <path d={paths[name]} fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
