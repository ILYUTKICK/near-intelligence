"use client";

import { useState } from "react";

interface WindowValue {
  label: string;
  near: string;
  usd: string;
}

export function AcquisitionComparison({ windows, nearDecline, usdDecline, closingDecline }: {
  windows: readonly WindowValue[];
  nearDecline: string;
  usdDecline: string;
  closingDecline: string;
}) {
  const [measure, setMeasure] = useState<"near" | "usd">("near");
  const isUsd = measure === "usd";
  const unit = isUsd ? "Estimated USD" : "NEAR acquired";
  const maximum = isUsd ? 600_000 : 300_000;
  const prefix = isUsd ? "$" : "";
  const ticks = [maximum, maximum * 2 / 3, maximum / 3, 0];
  const summary = windows.map((window) => `${window.label}: ${prefix}${window[measure]}`).join("; ");

  return (
    <figure id="thesis-usd-windows" aria-labelledby="acquisitions-title" className="mt-4 scroll-mt-8 bg-surface-muted p-4 sm:p-6">
      <figcaption className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 id="acquisitions-title" className="text-heading">Acquisitions by 30-day window</h3>
          <p className="mt-1 text-metadata text-text-secondary">
            {unit} · {isUsd ? "Daily start-of-day prices · " : ""}2026 UTC
          </p>
        </div>
        <div role="group" aria-label="Acquisition measure" className="inline-flex rounded-control">
          {(["near", "usd"] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setMeasure(value)}
              aria-pressed={measure === value}
              className="min-h-11 border border-control-border px-3 text-ui first:rounded-l-control last:rounded-r-control last:border-l-0 aria-pressed:border-accent aria-pressed:bg-accent aria-pressed:text-on-accent"
            >
              {value === "near" ? "NEAR" : "USD estimate"}
            </button>
          ))}
        </div>
      </figcaption>
      <div role="img" aria-label={`${unit}. ${summary}.`} className="mt-7 grid grid-cols-[auto_minmax(0,1fr)] grid-rows-[10rem_auto] tabular-nums">
        <div aria-hidden="true" className="col-start-1 row-start-1 flex flex-col justify-between pr-2 text-right text-metadata leading-none text-text-secondary">
          {ticks.map((tick) => <span key={tick} className="-translate-y-1/2">{prefix}{tick ? `${tick / 1000}k` : 0}</span>)}
        </div>
        <div aria-hidden="true" className="col-start-2 row-start-1 flex flex-col justify-between">
          {ticks.map((tick) => <div key={tick} className={tick ? "border-t border-border" : "border-t border-control-border"} />)}
        </div>
        <div aria-hidden="true" className="col-start-2 row-start-1 grid grid-cols-3 items-end">
          {windows.map((window) => (
            <div
              key={window.label}
              className="relative mx-auto w-[62%] max-w-32 rounded-t-sm bg-accent/35 even:bg-accent/60 last:bg-accent"
              style={{ height: `${Number(window[measure].replaceAll(",", "")) / maximum * 100}%` }}
            >
              <span className="absolute bottom-full left-1/2 -translate-x-1/2 whitespace-nowrap pb-1 text-metadata font-semibold sm:text-ui">
                {prefix}{window[measure]}
              </span>
            </div>
          ))}
        </div>
        <div aria-hidden="true" className="col-start-2 row-start-2 grid grid-cols-3 gap-1 pt-2 text-center text-metadata text-text-secondary">
          {windows.map((window) => <span key={window.label}>{window.label}</span>)}
        </div>
      </div>
      <p aria-live="polite" className="mt-4 text-ui">
        {isUsd
          ? `Estimated dollar value fell ${usdDecline}% from the second window to the third.`
          : `The cohort acquired ${nearDecline}% less NEAR in the third window than in the second.`}
      </p>
      <details className="mt-3 border-t border-border pt-2 text-ui">
        <summary className="w-fit cursor-pointer py-1 font-medium text-accent">Values and valuation method</summary>
        <table className="mt-2 w-full text-left text-metadata tabular-nums sm:text-ui">
          <thead><tr><th scope="col">Window</th><th scope="col" className="text-right">NEAR acquired</th><th scope="col" className="text-right">Est. USD</th></tr></thead>
          <tbody>
            {windows.map((window) => (
              <tr key={window.label} className="border-t border-border">
                <th scope="row" className="py-2 font-normal">{window.label}</th>
                <td className="text-right">{window.near}</td>
                <td className="text-right">{"$"}{window.usd}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-text-secondary">
          NEAR quantities are rounded as recorded. The USD estimates use daily start-of-day prices.
          Using end-of-day prices gives a {closingDecline}% decline from the second window to the third.
        </p>
      </details>
      <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-metadata">
        {["CL-002", "CL-004"].map((id) => (
          <a key={id} href={`#${id}-heading`} className="text-accent underline underline-offset-4">Recorded claim {id}</a>
        ))}
      </p>
    </figure>
  );
}
