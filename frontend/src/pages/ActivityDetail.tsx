import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { Link, useParams } from "react-router-dom"
import { getActivityDetail, getStoredAthleteId } from "../api/client"
import DebriefCard from "../components/DebriefCard"
import MetricBadge, { type MetricTone } from "../components/MetricBadge"
import type { ActivityDetailResponse, ActivityMetrics } from "../types"

interface MetricDisplay {
  key: string
  label: string
  value: string
  caption: string
  tone: MetricTone
}

export default function ActivityDetail() {
  const activityId = useActivityId()
  const query = useActivityQuery(activityId)
  const [selectedMetric, setSelectedMetric] = useState("hr_tss")
  if (activityId === null) return <ActivityStatus message="Invalid activity id." />
  if (query.isPending) return <ActivityStatus message="Loading activity debrief..." />
  if (query.isError) return <ActivityStatus message={query.error.message} />
  return <ActivityDetailView data={query.data} selectedMetric={selectedMetric} onSelectMetric={setSelectedMetric} />
}

function useActivityId(): number | null {
  const params = useParams<{ id: string }>()
  const parsed = Number(params.id)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function useActivityQuery(activityId: number | null) {
  return useQuery({
    queryKey: ["activity-detail", activityId],
    queryFn: () => getActivityDetail(requireActivityId(activityId)),
    enabled: activityId !== null,
  })
}

function ActivityDetailView(props: {
  data: ActivityDetailResponse
  selectedMetric: string
  onSelectMetric: (metric: string) => void
}) {
  const metrics = buildMetrics(props.data.metrics)
  const selected = metrics.find((metric) => metric.key === props.selectedMetric)
  return (
    <main className="min-h-screen bg-trail-surface px-4 py-6 text-trail-ink">
      <div className="mx-auto max-w-4xl space-y-6">
        <BackLink />
        <ActivityHeader data={props.data} />
        <MetricPanel metrics={metrics} selected={props.selectedMetric} onSelect={props.onSelectMetric} />
        {selected ? <MetricSource metric={selected} /> : null}
        {props.data.debrief ? <DebriefCard debrief={props.data.debrief} /> : <DebriefPending />}
      </div>
    </main>
  )
}

function BackLink() {
  const athleteId = getStoredAthleteId()
  const path = athleteId ? `/dashboard?athlete_id=${athleteId}` : "/dashboard"
  return <Link className="font-semibold text-blue-700 hover:underline" to={path}>Back to dashboard</Link>
}

function ActivityHeader({ data }: { data: ActivityDetailResponse }) {
  return (
    <header className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
      <p className="text-sm font-semibold uppercase text-trail-strava">{data.activity.sport_type}</p>
      <h1 className="mt-2 text-3xl font-bold text-slate-950">{data.activity.name}</h1>
      <p className="mt-2 text-sm text-slate-500">
        {formatDate(data.activity.start_date)} · {formatKm(data.activity.distance_m)} · {formatDuration(data.activity.elapsed_time_sec)}
      </p>
    </header>
  )
}

function MetricPanel(props: {
  metrics: MetricDisplay[]
  selected: string
  onSelect: (metric: string) => void
}) {
  if (props.metrics.length === 0) return <NoMetrics />
  return (
    <section className="grid gap-4 md:grid-cols-4">
      {props.metrics.map((metric) => (
        <MetricBadge
          caption={metric.caption}
          key={metric.key}
          label={metric.label}
          onSelect={() => props.onSelect(metric.key)}
          selected={props.selected === metric.key}
          tone={metric.tone}
          value={metric.value}
        />
      ))}
    </section>
  )
}

function MetricSource({ metric }: { metric: MetricDisplay }) {
  return (
    <section className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
      Source metric selected: <strong>{metric.label}</strong> at <strong>{metric.value}</strong>.
    </section>
  )
}

function buildMetrics(metrics: ActivityMetrics | null): MetricDisplay[] {
  if (!metrics) return []
  return [
    display("hr_tss", "hrTSS", formatNumber(metrics.hr_tss), "Load score", "blue"),
    display("hr_drift", "HR drift", formatPercent(metrics.hr_drift_pct), "Late-run cardiac drift", "amber"),
    display("decoupling", "Decoupling", formatPercent(metrics.aerobic_decoupling_pct), "Pace to HR efficiency", "emerald"),
    display("ngp", "NGP", formatPace(metrics.ngp_sec_km), "Normalized graded pace", "violet"),
  ]
}

function display(key: string, label: string, value: string, caption: string, tone: MetricTone): MetricDisplay {
  return { key, label, value, caption, tone }
}

function DebriefPending() {
  return (
    <section className="rounded-lg border border-amber-200 bg-amber-50 p-5 text-sm font-semibold text-amber-800">
      Debrief is still being generated. Refresh after processing completes.
    </section>
  )
}

function NoMetrics() {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-500">
      Metrics are not available for this activity yet.
    </section>
  )
}

function ActivityStatus({ message }: { message: string }) {
  return <main className="min-h-screen bg-trail-surface p-8 text-slate-800">{message}</main>
}

function requireActivityId(activityId: number | null): number {
  if (activityId === null) throw new Error("Activity id is required")
  return activityId
}

function formatNumber(value: number | null): string {
  return value === null ? "-" : value.toFixed(1)
}

function formatPercent(value: number | null): string {
  return value === null ? "-" : `${value.toFixed(1)}%`
}

function formatPace(secondsPerKm: number | null): string {
  if (secondsPerKm === null) return "-"
  return `${Math.floor(secondsPerKm / 60)}:${String(Math.round(secondsPerKm % 60)).padStart(2, "0")}/km`
}

function formatKm(meters: number): string {
  return `${(meters / 1000).toFixed(2)} km`
}

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.round((seconds % 3600) / 60)
  return hours > 0 ? `${hours}h ${minutes}m` : `${minutes} min`
}

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString("en", { dateStyle: "medium" })
}
