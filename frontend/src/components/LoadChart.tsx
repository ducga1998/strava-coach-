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
}

export default function LoadChart({ data }: LoadChartProps) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-1.5 text-lg font-bold text-slate-950">
            Training load
            <AntTooltip title={CHART_HELP} trigger={["hover", "click"]}>
              <InfoCircleOutlined className="cursor-help text-base font-normal text-slate-400" />
            </AntTooltip>
          </h2>
          <p className="text-sm text-slate-500">CTL, ATL, and TSB over 90 days</p>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data.map(withDateLabel)}>
          <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
          <XAxis dataKey="dateLabel" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} width={36} />
          <Tooltip content={<LoadChartTooltip />} />
          <Legend />
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

function LoadChartTooltip(props: {
  active?: boolean
  label?: string
  payload?: ReadonlyArray<{ dataKey?: string; name?: string; value?: number; color?: string }>
}) {
  if (!props.active || !props.payload?.length) return null
  return (
    <div className="max-w-xs rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-md">
      <p className="font-semibold text-slate-950">{props.label}</p>
      <ul className="mt-2 space-y-2">
        {props.payload.map((row) => {
          const name = row.name ?? row.dataKey ?? "—"
          const hint = typeof name === "string" ? SERIES_HINT[name] : undefined
          return (
            <li key={String(row.dataKey)} className="flex gap-2">
              <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: row.color }} />
              <span>
                <span className="font-semibold text-slate-900">
                  {name}: {typeof row.value === "number" ? row.value.toFixed(1) : "—"}
                </span>
                {hint ? <span className="mt-0.5 block text-xs font-normal text-slate-500">{hint}</span> : null}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
