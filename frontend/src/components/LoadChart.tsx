import { InfoCircleOutlined } from "@ant-design/icons"
import { Tooltip as AntTooltip } from "antd"
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import type { TooltipProps } from "recharts"
import type { LoadPoint } from "../types"

const CHART_HELP =
  "CTL (blue) is long-term fitness, ATL (orange) is recent fatigue, TSB (green) is form (fitness minus fatigue). Hover a day for values."

const SERIES_HINT: Record<string, string> = {
  CTL: "Long-term fitness — builds slowly, drops after time off.",
  ATL: "Recent fatigue — rises after hard weeks.",
  TSB: "Form — negative when tired, positive when fresh.",
}

interface LoadChartProps {
  data: LoadPoint[]
  variant?: "light" | "dark"
}

export default function LoadChart({ data, variant = "light" }: LoadChartProps) {
  const dark = variant === "dark"
  const shell = dark
    ? "rounded-lg border border-white/[0.14] bg-brand-charcoal/80 p-5 shadow-[0_20px_60px_rgba(0,0,0,0.35)]"
    : "rounded-lg border border-slate-200 bg-white p-5 shadow-panel"
  const titleClass = dark ? "text-lg font-bold text-neutral-50" : "text-lg font-bold text-slate-950"
  const subClass = dark ? "text-sm text-brand-muted" : "text-sm text-slate-500"
  const iconClass = dark ? "cursor-help text-base font-normal text-brand-muted" : "cursor-help text-base font-normal text-slate-400"
  const gridStroke = dark ? "#334155" : "#e2e8f0"
  const tickFill = dark ? "#94a3b8" : undefined
  const legendStyle = dark ? { color: "#cbd5e1" } : undefined

  return (
    <section className={shell}>
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <h2 className={`flex items-center gap-1.5 ${titleClass}`}>
            Training load
            <AntTooltip title={CHART_HELP} trigger={["hover", "click"]}>
              <InfoCircleOutlined className={iconClass} />
            </AntTooltip>
          </h2>
          <p className={subClass}>CTL, ATL, and TSB over 90 days</p>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data.map(withDateLabel)}>
          <CartesianGrid stroke={gridStroke} strokeDasharray="3 3" />
          <XAxis dataKey="dateLabel" tick={{ fontSize: 12, fill: tickFill }} stroke={dark ? "#475569" : undefined} />
          <YAxis tick={{ fontSize: 12, fill: tickFill }} width={36} stroke={dark ? "#475569" : undefined} />
          <Tooltip
            content={(props: TooltipProps<number, string>) => <LoadChartTooltip {...props} variant={variant} />}
          />
          <Legend wrapperStyle={legendStyle} />
          <Line type="monotone" dataKey="ctl" name="CTL" stroke="#2563eb" dot={false} strokeWidth={2} />
          <Line type="monotone" dataKey="atl" name="ATL" stroke="#fc4c02" dot={false} strokeWidth={2} />
          <Line type="monotone" dataKey="tsb" name="TSB" stroke="#059669" dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </section>
  )
}

function withDateLabel(point: LoadPoint): LoadPoint & { dateLabel: string } {
  return { ...point, dateLabel: formatDate(point.date) }
}

function formatDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString("en", { month: "short", day: "numeric" })
}

function LoadChartTooltip(
  props: TooltipProps<number, string> & {
    variant?: "light" | "dark"
  },
) {
  if (!props.active || !props.payload?.length) return null
  const dark = props.variant === "dark"
  const box = dark
    ? "max-w-xs rounded-lg border border-white/15 bg-brand-void px-3 py-2 text-sm shadow-md"
    : "max-w-xs rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-md"
  const labelCls = dark ? "font-semibold text-neutral-50" : "font-semibold text-slate-950"
  const nameCls = dark ? "font-semibold text-neutral-100" : "font-semibold text-slate-900"
  const hintCls = dark ? "mt-0.5 block text-xs font-normal text-brand-muted" : "mt-0.5 block text-xs font-normal text-slate-500"

  return (
    <div className={box}>
      <p className={labelCls}>{props.label}</p>
      <ul className="mt-2 space-y-2">
        {props.payload.map((row) => {
          const name = row.name ?? row.dataKey ?? "—"
          const hint = typeof name === "string" ? SERIES_HINT[name] : undefined
          return (
            <li key={String(row.dataKey)} className="flex gap-2">
              <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: row.color }} />
              <span>
                <span className={nameCls}>
                  {name}: {typeof row.value === "number" ? row.value.toFixed(1) : "—"}
                </span>
                {hint ? <span className={hintCls}>{hint}</span> : null}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
