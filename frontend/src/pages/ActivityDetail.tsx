import { useMutation, useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { Link, useParams } from "react-router-dom"
import { getActivityDetail, getPlanRange, getStoredAthleteId, pushActivityDescription } from "../api/client"
import DebriefCard from "../components/DebriefCard"
import MetricBadge, { type MetricTone } from "../components/MetricBadge"
import { SkeletonBlock, SkeletonLine } from "../components/Skeleton"
import type {
  ActivityDetail as ActivityDetailData,
  ActivityDetailResponse,
  ActivityMetrics,
  Debrief,
  PlanEntry,
} from "../types"

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
  if (query.isPending) return <ActivityDetailSkeleton />
  if (query.isError) return <ActivityStatus message={query.error.message} />
  return (
    <ActivityDetailView
      activityId={activityId}
      data={query.data}
      selectedMetric={selectedMetric}
      onSelectMetric={setSelectedMetric}
    />
  )
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
  activityId: number
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
        <ActivityHeader data={props.data} activityId={props.activityId} />
        <MetricPanel metrics={metrics} selected={props.selectedMetric} onSelect={props.onSelectMetric} />
        {selected ? <MetricSource metric={selected} /> : null}
        <PlannedVsActualGate
          activity={props.data.activity}
          metrics={props.data.metrics}
          debrief={props.data.debrief}
        />
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

function ActivityHeader({ data, activityId }: { data: ActivityDetailResponse; activityId: number }) {
  return (
    <header className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase text-trail-strava">{data.activity.sport_type}</p>
          <h1 className="mt-2 text-3xl font-bold text-slate-950">{data.activity.name}</h1>
          <p className="mt-2 text-sm text-slate-500">
            {formatDate(data.activity.start_date)} · {formatKm(data.activity.distance_m)} · {formatDuration(data.activity.elapsed_time_sec)}
          </p>
        </div>
        <PushDescriptionButton activityId={activityId} hasDebrief={data.debrief !== null} />
      </div>
    </header>
  )
}

function PushDescriptionButton({ activityId, hasDebrief }: { activityId: number; hasDebrief: boolean }) {
  const mutation = useMutation({
    mutationFn: () => pushActivityDescription(activityId),
  })

  if (mutation.isSuccess) {
    return (
      <div className="flex shrink-0 flex-col items-end gap-1">
        <span className="inline-flex items-center gap-1.5 rounded-md bg-green-100 px-3 py-1.5 text-sm font-medium text-green-800">
          ✓ Pushed to Strava
        </span>
        <button
          className="text-xs text-slate-400 hover:text-slate-600 hover:underline"
          onClick={() => mutation.reset()}
          type="button"
        >
          Push again
        </button>
      </div>
    )
  }

  if (mutation.isError) {
    return (
      <div className="flex shrink-0 flex-col items-end gap-1">
        <span className="inline-flex items-center gap-1.5 rounded-md bg-red-100 px-3 py-1.5 text-sm font-medium text-red-800">
          ✗ {mutation.error.message}
        </span>
        <button
          className="text-xs text-slate-400 hover:text-slate-600 hover:underline"
          onClick={() => mutation.reset()}
          type="button"
        >
          Try again
        </button>
      </div>
    )
  }

  return (
    <button
      className={[
        "shrink-0 rounded-md px-4 py-2 text-sm font-semibold transition-colors",
        mutation.isPending
          ? "cursor-not-allowed bg-slate-100 text-slate-400"
          : hasDebrief
            ? "bg-trail-strava text-white hover:opacity-90"
            : "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
      ].join(" ")}
      disabled={mutation.isPending}
      onClick={() => mutation.mutate()}
      type="button"
      title={hasDebrief ? "Write AI coaching summary to Strava description" : "No debrief yet — metrics needed first"}
    >
      {mutation.isPending ? "Pushing…" : "Push to Strava"}
    </button>
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

function ActivityDetailSkeleton() {
  return (
    <main
      aria-busy="true"
      aria-label="Loading activity debrief"
      className="min-h-screen bg-trail-surface px-4 py-6 text-trail-ink"
    >
      <div className="mx-auto max-w-4xl space-y-6">
        <SkeletonLine height="0.875rem" width="160px" />
        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 space-y-3">
              <SkeletonLine height="0.75rem" width="80px" />
              <SkeletonLine height="1.75rem" width="70%" />
              <SkeletonLine height="0.75rem" width="55%" />
            </div>
            <SkeletonBlock className="h-10 w-32" rounded="md" />
          </div>
        </section>
        <section className="grid gap-4 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div className="min-h-28 rounded-lg border border-slate-200 bg-white p-4" key={i}>
              <SkeletonLine height="0.625rem" width="40%" />
              <SkeletonLine className="mt-3" height="1.5rem" width="70%" />
              <SkeletonLine className="mt-2" height="0.625rem" width="55%" />
            </div>
          ))}
        </section>
        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
          <SkeletonLine height="1rem" width="120px" />
          <div className="mt-4 space-y-3">
            <SkeletonLine />
            <SkeletonLine width="92%" />
            <SkeletonLine width="80%" />
            <SkeletonLine width="70%" />
            <SkeletonLine width="88%" />
          </div>
        </section>
      </div>
    </main>
  )
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

function PlannedVsActualGate(props: {
  activity: ActivityDetailData
  metrics: ActivityMetrics | null
  debrief: Debrief | null
}) {
  const athleteId = getStoredAthleteId()
  if (athleteId === null) return null
  return (
    <PlannedVsActualBlock
      athleteId={athleteId}
      activity={props.activity}
      metrics={props.metrics}
      debrief={props.debrief}
    />
  )
}

function PlannedVsActualBlock(props: {
  athleteId: number
  activity: ActivityDetailData
  metrics: ActivityMetrics | null
  debrief: Debrief | null
}) {
  // Use the athlete's LOCAL calendar date for the plan lookup. Slicing
  // the ISO string gives the UTC date, which is wrong for runs that
  // straddle midnight in the athlete's timezone (e.g. a 06:00 run in
  // Hanoi has a UTC start_date on the previous calendar day).
  // `toLocaleDateString("en-CA")` yields YYYY-MM-DD in local time.
  const iso = new Date(props.activity.start_date).toLocaleDateString("en-CA")
  const query = useQuery({
    queryKey: ["plan-range", props.athleteId, iso, iso],
    queryFn: () =>
      getPlanRange({ athleteId: props.athleteId, from: iso, to: iso }),
  })
  const entries: PlanEntry[] = query.data ?? []
  const planned = entries[0]
  if (!planned) return null

  const complianceText = props.debrief?.plan_compliance ?? ""
  const score = parseComplianceScore(complianceText)
  const sentence = stripComplianceScore(complianceText)

  const actualTss = props.metrics?.hr_tss ?? props.metrics?.tss ?? null
  const actualDurationMin = Math.round(props.activity.elapsed_time_sec / 60)

  return (
    <section className="mb-4 rounded-lg border border-slate-200 bg-white p-4 shadow-panel">
      <header className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-bold text-slate-900">Planned vs actual</h2>
        {score !== null ? (
          <span
            className={
              "rounded-full px-3 py-1 text-sm font-bold " +
              complianceBadgeClasses(score)
            }
          >
            {score}/100
          </span>
        ) : null}
      </header>
      {sentence ? (
        <p className="mb-4 text-sm italic text-slate-700">&ldquo;{sentence}&rdquo;</p>
      ) : null}
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-500">
            <th className="pb-2"></th>
            <th className="pb-2">Planned</th>
            <th className="pb-2">Actual</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          <tr>
            <td className="py-2 font-semibold">Type</td>
            <td className="py-2">{planned.workout_type}</td>
            <td className="py-2">{props.activity.sport_type}</td>
          </tr>
          <tr>
            <td className="py-2 font-semibold">TSS</td>
            <td className="py-2">
              {planned.planned_tss !== null
                ? planned.planned_tss.toFixed(0)
                : "—"}
            </td>
            <td className="py-2">
              {actualTss !== null ? actualTss.toFixed(0) : "—"}
            </td>
          </tr>
          <tr>
            <td className="py-2 font-semibold">Duration</td>
            <td className="py-2">
              {planned.planned_duration_min !== null
                ? `${planned.planned_duration_min} min`
                : "—"}
            </td>
            <td className="py-2">{actualDurationMin} min</td>
          </tr>
          {planned.description ? (
            <tr>
              <td className="py-2 font-semibold">Notes</td>
              <td className="py-2" colSpan={2}>
                {planned.description}
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </section>
  )
}

function parseComplianceScore(text: string): number | null {
  const match = /^(\d{1,3})\/100\s/.exec(text)
  if (!match) return null
  const n = Number(match[1])
  return Number.isFinite(n) && n >= 0 && n <= 100 ? n : null
}

function stripComplianceScore(text: string): string {
  return text.replace(/^\d{1,3}\/100\s/, "").trim()
}

function complianceBadgeClasses(score: number): string {
  if (score >= 90) return "bg-green-100 text-green-800"
  if (score >= 70) return "bg-yellow-100 text-yellow-800"
  return "bg-red-100 text-red-800"
}
