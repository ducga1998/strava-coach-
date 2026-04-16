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

interface LoadChartProps {
  data: LoadPoint[]
}

export default function LoadChart({ data }: LoadChartProps) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-slate-950">Training load</h2>
          <p className="text-sm text-slate-500">CTL, ATL, and TSB over 90 days</p>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data.map(withDateLabel)}>
          <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
          <XAxis dataKey="dateLabel" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} width={36} />
          <Tooltip />
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
