import type { Metadata } from "next";
import type { ReactNode } from "react";
import localFont from "next/font/local";
import "@/styles/globals.css";

// NI-099: approved Comic Lab families, served same-origin. See font licenses.
const rubik = localFont({
  src: [
    { path: "../styles/fonts/Rubik-Regular.woff2", weight: "400", style: "normal" },
    { path: "../styles/fonts/Rubik-Bold.woff2", weight: "700", style: "normal" },
  ], display: "swap", variable: "--font-rubik", fallback: ["system-ui", "sans-serif"],
});
const golos = localFont({
  src: [
    { path: "../styles/fonts/GolosText-Regular.woff2", weight: "400", style: "normal" },
    { path: "../styles/fonts/GolosText-Bold.woff2", weight: "700", style: "normal" },
  ], display: "swap", variable: "--font-golos", fallback: ["system-ui", "sans-serif"],
});
const plexMono = localFont({
  src: [{ path: "../styles/fonts/IBMPlexMono-Medium.woff2", weight: "500", style: "normal" }],
  display: "swap", variable: "--font-plex-mono", fallback: ["monospace"],
});

export const metadata: Metadata = {
  title: "NEAR Intelligence",
  description: "Evidence-first NEAR investment research.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="en" className={`${rubik.variable} ${golos.variable} ${plexMono.variable}`}>
    <body>{children}</body>
  </html>;
}
