import { InfoCircleOutlined } from "@ant-design/icons"
import { Tooltip } from "antd"

interface AcwrGaugeProps {
  acwr: number
  variant?: "light" | "dark"
}

const ACWR_HELP =
  "Acute:Chronic Workload Ratio — this week’s load vs your usual baseline. About 0.8–1.3 is often sustainable; above 1.5 suggests injury risk if it stays there."

const radius = 52
const stroke = 12
const circumference = 2 * Math.PI * radius

export default function AcwrGauge({ acwr, variant = "light" }: AcwrGaugeProps) {
  const dark = variant === "dark"
  const zone = getAcwrZone(acwr, dark)
  const offset = circumference * (1 - getGaugePercent(acwr))
  const shell = dark
    ? "rounded-lg border border-white/[0.14] bg-brand-charcoal/80 p-5 shadow-[0_20px_60px_rgba(0,0,0,0.35)]"
    : "rounded-lg border border-slate-200 bg-white p-5 shadow-panel"
  const labelCls = dark
    ? "flex items-center gap-1 text-sm font-semibold uppercase text-brand-muted"
    : "flex items-center gap-1 text-sm font-semibold uppercase text-slate-500"
  const iconCls = dark ? "cursor-help text-[0.7rem] normal-case text-brand-muted" : "cursor-help text-[0.7rem] normal-case text-slate-400"
  const valueCls = dark ? "mt-1 text-4xl font-bold text-neutral-50" : "mt-1 text-4xl font-bold text-slate-950"
  const guideCls = dark ? "mt-4 text-sm text-brand-muted" : "mt-4 text-sm text-slate-600"
  const trackStroke = dark ? "#334155" : "#e2e8f0"

  return (
    <section className={shell}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className={labelCls}>
            ACWR
            <Tooltip title={ACWR_HELP} trigger={["hover", "click"]}>
              <InfoCircleOutlined className={iconCls} />
            </Tooltip>
          </h2>
          <p className={valueCls}>{acwr.toFixed(2)}</p>
          <p className={`mt-2 text-sm font-semibold ${zone.textClass}`}>{zone.label}</p>
        </div>
        <GaugeCircle offset={offset} strokeClass={zone.strokeClass} trackStroke={trackStroke} />
      </div>
      <p className={guideCls}>{zone.guidance}</p>
    </section>
  )
}

function GaugeCircle(props: { offset: number; strokeClass: string; trackStroke: string }) {
  return (
    <svg viewBox="0 0 140 140" className="h-32 w-32 shrink-0" aria-hidden="true">
      <circle cx="70" cy="70" r={radius} fill="none" stroke={props.trackStroke} strokeWidth={stroke} />
      <circle
        cx="70"
        cy="70"
        r={radius}
        fill="none"
        stroke="currentColor"
        strokeDasharray={circumference}
        strokeDashoffset={props.offset}
        strokeLinecap="round"
        strokeWidth={stroke}
        className={`origin-center -rotate-90 ${props.strokeClass}`}
      />
    </svg>
  )
}

function getGaugePercent(acwr: number): number {
  return clamp((acwr - 0.5) / 1.3, 0.05, 1)
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function getAcwrZone(acwr: number, dark: boolean) {
  if (acwr < 0.8)
    return zone(
      "Undertraining",
      dark ? "text-blue-300" : "text-blue-700",
      dark ? "text-blue-400" : "text-blue-500",
      "Load is below chronic baseline.",
    )
  if (acwr <= 1.3)
    return zone(
      "Green zone",
      dark ? "text-emerald-300" : "text-emerald-700",
      dark ? "text-emerald-400" : "text-emerald-500",
      "Current load is inside the sustainable range.",
    )
  if (acwr <= 1.5)
    return zone(
      "Caution",
      dark ? "text-amber-300" : "text-amber-700",
      dark ? "text-amber-400" : "text-amber-500",
      "One hard week is acceptable; avoid stacking another.",
    )
  return zone(
    "Injury risk",
    dark ? "text-red-300" : "text-red-700",
    dark ? "text-red-400" : "text-red-500",
    "Consider deloading before adding more intensity.",
  )
}

function zone(label: string, textClass: string, strokeClass: string, guidance: string) {
  return { label, textClass, strokeClass, guidance }
}
