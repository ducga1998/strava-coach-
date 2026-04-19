import { InfoCircleOutlined } from "@ant-design/icons"
import { Card, Statistic, Tooltip } from "antd"

export type MetricTone = "blue" | "emerald" | "amber" | "red" | "violet"

interface MetricBadgeProps {
  label: string
  value: string
  caption?: string
  /** Short explanation shown on hover / tap (mobile). */
  help?: string
  tone?: MetricTone
  selected?: boolean
  onSelect?: () => void
  /** Default `light` (ActivityDetail, etc.). Use `dark` on dashboard. */
  variant?: "light" | "dark"
}

const toneClassesLight: Record<MetricTone, string> = {
  blue: "border-blue-200 bg-blue-50 text-blue-900",
  emerald: "border-emerald-200 bg-emerald-50 text-emerald-900",
  amber: "border-amber-200 bg-amber-50 text-amber-900",
  red: "border-red-200 bg-red-50 text-red-900",
  violet: "border-violet-200 bg-violet-50 text-violet-900",
}

const toneClassesDark: Record<MetricTone, string> = {
  blue: "border-blue-500/35 bg-blue-950/40 text-blue-100",
  emerald: "border-emerald-500/35 bg-emerald-950/35 text-emerald-100",
  amber: "border-amber-500/35 bg-amber-950/35 text-amber-100",
  red: "border-red-500/35 bg-red-950/40 text-red-100",
  violet: "border-violet-500/35 bg-violet-950/40 text-violet-100",
}

export default function MetricBadge(props: MetricBadgeProps) {
  const variant = props.variant ?? "light"
  const selectedClass =
    props.selected && variant === "dark"
      ? "ring-2 ring-brand-teal/70"
      : props.selected
        ? "ring-2 ring-slate-900"
        : ""
  const toneClass = (variant === "dark" ? toneClassesDark : toneClassesLight)[props.tone ?? "blue"]

  const className = [
    "min-h-28 rounded-lg border text-left transition",
    "hover:-translate-y-0.5 hover:shadow-sm",
    toneClass,
    selectedClass,
    props.onSelect ? "cursor-pointer" : "",
  ].join(" ")

  const titleMuted = variant === "dark" ? "text-brand-muted" : "text-slate-500"
  const iconMuted = variant === "dark" ? "text-brand-muted" : "text-slate-400"

  return (
    <Card onClick={props.onSelect} className={className} bodyStyle={{ padding: "16px" }} bordered={false}>
      <Statistic
        title={
          <span className={`flex items-center gap-1 text-xs font-semibold uppercase ${titleMuted}`}>
            <span>{props.label}</span>
            {props.help ? (
              <Tooltip title={props.help} trigger={["hover", "click"]}>
                <InfoCircleOutlined
                  className={`cursor-help align-middle text-[0.65rem] normal-case ${iconMuted}`}
                  onClick={(e) => e.stopPropagation()}
                  onPointerDown={(e) => e.stopPropagation()}
                />
              </Tooltip>
            ) : null}
          </span>
        }
        value={props.value}
        valueStyle={{ fontSize: "1.5rem", fontWeight: 700, color: "inherit" }}
        formatter={(val) => <span className="text-2xl font-bold">{val}</span>}
      />
      {props.caption ? <span className="mt-1 block text-xs opacity-80">{props.caption}</span> : null}
    </Card>
  )
}
