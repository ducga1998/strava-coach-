import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { Typography, Alert, Button } from "antd"
import { WarningFilled } from "@ant-design/icons"
import DarkAppShell from "../components/layout/DarkAppShell"
import {
  getAthleteInfo,
  getDashboardLoad,
  getPlanRange,
  getStoredAthleteId,
  listActivities,
  requireAthleteId,
} from "../api/client"
import AcwrGauge from "../components/AcwrGauge"
import LoadChart from "../components/LoadChart"
import MetricBadge from "../components/MetricBadge"
import PhaseIndicator from "../components/PhaseIndicator"
import { SkeletonBlock, SkeletonLine } from "../components/Skeleton"
import type {
  AcwrZone,
  ActivityListItem,
  AthleteInfo,
  DashboardLoadResponse,
  LoadSnapshot,
  PlanEntry,
} from "../types"

const emptyLoad: DashboardLoadResponse = {
  training_phase: "Base",
  latest: { ctl: 0, atl: 0, tsb: 0, acwr: 1 },
  history: [],
}

export default function Dashboard() {
  const athleteId = getStoredAthleteId()
  const loadQuery = useLoadQuery(athleteId)
  const activitiesQuery = useActivitiesQuery(athleteId)
  const athleteQuery = useAthleteQuery(athleteId)
  if (athleteId === null)
    return (
      <DarkAppShell>
        <MissingAthleteState />
      </DarkAppShell>
    )
  if (loadQuery.isPending)
    return (
      <DarkAppShell>
        <DashboardSkeleton />
      </DarkAppShell>
    )
  if (loadQuery.isError)
    return (
      <DarkAppShell>
        <StatusPage message={loadQuery.error.message} />
      </DarkAppShell>
    )

  const load = loadQuery.data ?? emptyLoad
  const activities = activitiesQuery.data ?? []
  const athlete = athleteQuery.data ?? null
  return (
    <DarkAppShell>
      <DashboardView activities={activities} athlete={athlete} athleteId={athleteId} load={load} />
    </DarkAppShell>
  )
}

function useLoadQuery(athleteId: number | null) {
  return useQuery({
    queryKey: ["dashboard-load", athleteId],
    queryFn: () => getDashboardLoad(requireAthleteId(athleteId)),
    enabled: athleteId !== null,
  })
}

function useActivitiesQuery(athleteId: number | null) {
  return useQuery({
    queryKey: ["activities", athleteId],
    queryFn: () => listActivities(requireAthleteId(athleteId)),
    enabled: athleteId !== null,
  })
}

function useAthleteQuery(athleteId: number | null) {
  return useQuery({
    queryKey: ["athlete", athleteId],
    queryFn: () => getAthleteInfo(requireAthleteId(athleteId)),
    enabled: athleteId !== null,
  })
}

function DashboardView(props: {
  activities: ActivityListItem[]
  athlete: AthleteInfo | null
  athleteId: number
  load: DashboardLoadResponse
}) {
  const latest = props.load.latest
  const acwrZone = resolveAcwrZone(latest)
  return (
    <main className="px-4 py-6 text-neutral-50">
      <div className="mx-auto max-w-6xl space-y-6">
        <DashboardHeader athlete={props.athlete} load={props.load} />
        {props.load.history.length < 14 ? <BaseliningBanner count={props.load.history.length} /> : null}
        {props.athlete ? <AthleteCard athlete={props.athlete} /> : null}
        <MetricGrid load={props.load} />
        <AcwrBanner zone={acwrZone} latest={latest} warning={props.load.warning ?? null} />
        <ThisWeekStrip athleteId={props.athleteId} />
        <section className="grid gap-6 xl:grid-cols-[1fr_320px]">
          <LoadChart data={props.load.history} variant="dark" />
          <AcwrGauge acwr={latest.acwr} variant="dark" />
        </section>
        <RecentActivities activities={props.activities} athleteId={props.athleteId} />
      </div>
    </main>
  )
}

function DashboardHeader({ athlete, load }: { athlete: AthleteInfo | null; load: DashboardLoadResponse }) {
  const name = athlete ? [athlete.firstname, athlete.lastname].filter(Boolean).join(" ") : null
  return (
    <header className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div className="flex items-center gap-4">
        {athlete?.avatar_url ? (
          <img
            alt={name ?? "Athlete"}
            className="h-14 w-14 rounded-full border-2 border-white/20 object-cover shadow-sm"
            src={athlete.avatar_url}
          />
        ) : (
          <div className="flex h-14 w-14 items-center justify-center rounded-full border border-white/15 bg-white/5 text-xl font-bold text-brand-muted shadow-sm">
            {name ? name[0].toUpperCase() : "?"}
          </div>
        )}
        <div>
          {name ? (
            <Typography.Title className="!mt-0 !mb-0 !text-2xl font-bold !text-neutral-50" level={1}>
              {name}
            </Typography.Title>
          ) : null}
          {athlete?.city || athlete?.country ? (
            <Typography.Text className="text-sm text-brand-muted">
              {[athlete.city, athlete.country].filter(Boolean).join(", ")}
            </Typography.Text>
          ) : null}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <PhaseIndicator phase={load.training_phase} targetDate={load.target?.race_date} variant="dark" />
        <Link to="/targets">
          <Button
            className="rounded-lg !border-white/20 !bg-transparent !font-semibold !text-neutral-50 hover:!border-brand-teal/50 hover:!text-brand-teal"
            size="large"
          >
            Targets
          </Button>
        </Link>
      </div>
    </header>
  )
}

function AthleteCard({ athlete }: { athlete: AthleteInfo }) {
  const p = athlete.profile
  if (!p || (!p.lthr && !p.threshold_pace_sec_km && !p.vo2max_estimate && !p.weight_kg)) return null
  return (
    <section className="grid grid-cols-2 gap-3 rounded-xl border border-white/[0.14] bg-brand-charcoal/70 p-5 shadow-[0_20px_60px_rgba(0,0,0,0.35)] md:grid-cols-4">
      <ProfileStat label="LTHR" value={p.lthr ? `${p.lthr} bpm` : null} hint="Lactate threshold HR" />
      <ProfileStat label="Threshold pace" value={p.threshold_pace_sec_km ? formatPace(p.threshold_pace_sec_km) : null} hint="min/km at LT" />
      <ProfileStat label="VO₂max" value={p.vo2max_estimate ? `${p.vo2max_estimate.toFixed(1)} ml/kg/min` : null} hint="Aerobic capacity estimate" />
      <ProfileStat label="Weight" value={p.weight_kg ? `${p.weight_kg.toFixed(1)} kg` : null} hint="Body mass" />
    </section>
  )
}

function ProfileStat({ label, value, hint }: { label: string; value: string | null; hint: string }) {
  if (!value) return null
  return (
    <div>
      <p className="text-xs font-semibold uppercase text-brand-muted">{label}</p>
      <p className="mt-1 text-lg font-bold text-neutral-50">{value}</p>
      <p className="text-xs text-brand-muted">{hint}</p>
    </div>
  )
}

function formatPace(secPerKm: number): string {
  const min = Math.floor(secPerKm / 60)
  const sec = secPerKm % 60
  return `${min}:${String(sec).padStart(2, "0")} /km`
}

const METRIC_HELP = {
  ctl: "Chronic Training Load — your rolling fitness from the last several weeks. It rises when you train consistently and falls after long breaks.",
  atl: "Acute Training Load — fatigue from about the last week. It jumps after hard blocks and should ease after easier days.",
  tsb: "Training Stress Balance (form) — CTL minus ATL. Negative means tired; very positive means fresh. Many athletes aim near +5 to +15 on race day.",
  weeklyVolume: "Rolling 7-day distance and climb from synced activities. Use it to see if your week matches the plan, not to compare to other runners.",
} as const

function MetricGrid({ load }: { load: DashboardLoadResponse }) {
  const volume = load.weekly_volume
  return (
    <section className="grid gap-4 md:grid-cols-4">
      <MetricBadge label="CTL" value={load.latest.ctl.toFixed(1)} caption="Fitness" help={METRIC_HELP.ctl} tone="blue" variant="dark" />
      <MetricBadge label="ATL" value={load.latest.atl.toFixed(1)} caption="Fatigue" help={METRIC_HELP.atl} tone="amber" variant="dark" />
      <MetricBadge
        label="TSB"
        value={load.latest.tsb.toFixed(1)}
        caption="Form"
        help={METRIC_HELP.tsb}
        tone={load.latest.tsb < -30 ? "red" : "emerald"}
        variant="dark"
      />
      <MetricBadge
        label="Weekly volume"
        value={formatVolume(volume)}
        caption={formatElevation(volume)}
        help={METRIC_HELP.weeklyVolume}
        tone="violet"
        variant="dark"
      />
    </section>
  )
}

function RecentActivities(props: { activities: ActivityListItem[]; athleteId: number }) {
  return (
    <section className="rounded-xl border border-white/[0.14] bg-brand-charcoal/70 p-5 shadow-[0_20px_60px_rgba(0,0,0,0.35)]">
      <h2 className="text-lg font-bold text-neutral-50">Recent activities</h2>
      <div className="mt-4 divide-y divide-white/10">
        {props.activities.map((activity) => (
          <ActivityRow activity={activity} athleteId={props.athleteId} key={activity.id} />
        ))}
        {props.activities.length === 0 ? <EmptyActivities /> : null}
      </div>
    </section>
  )
}

function ActivityRow(props: { activity: ActivityListItem; athleteId: number }) {
  const activity = props.activity
  return (
    <Link
      className="flex flex-col gap-2 py-4 transition hover:bg-white/5 md:flex-row md:items-center md:justify-between"
      to={`/activities/${activity.id}?athlete_id=${props.athleteId}`}
    >
      <span>
        <span className="block font-semibold text-neutral-50">{activity.name}</span>
        <span className="text-sm text-brand-muted">
          {activity.sport_type} · {formatKm(activity.distance_m)} · {formatMinutes(activity.elapsed_time_sec)}
        </span>
      </span>
      <span className={statusClass(activity.processing_status)}>{activity.processing_status}</span>
    </Link>
  )
}

function AcwrBanner(props: {
  zone: AcwrZone | "low"
  latest: LoadSnapshot
  warning: string | null
}) {
  if (props.zone === "green" || props.zone === "low") return null
  const acwr = props.latest.acwr.toFixed(2)
  if (props.zone === "red") {
    const message =
      props.warning ??
      `Injury risk zone — ACWR ${acwr}. Consider a deload before adding more load.`
    return (
      <div
        className="flex items-start gap-3 rounded-lg border-l-4 border-red-500 bg-red-50 p-4 text-red-900 shadow-[0_12px_40px_rgba(220,38,38,0.18)]"
        role="alert"
      >
        <WarningFilled className="mt-0.5 shrink-0 text-lg text-red-500" aria-hidden="true" />
        <p className="text-base font-semibold leading-relaxed">{message}</p>
      </div>
    )
  }
  // yellow
  const message = props.warning ?? `ACWR ${acwr} — monitor load.`
  return (
    <div
      className="flex items-start gap-3 rounded-lg border-l-4 border-yellow-400 bg-yellow-50 p-4 text-amber-900 shadow-[0_12px_40px_rgba(202,138,4,0.18)]"
      role="alert"
    >
      <WarningFilled className="mt-0.5 shrink-0 text-lg text-yellow-500" aria-hidden="true" />
      <p className="text-base font-semibold leading-relaxed">{message}</p>
    </div>
  )
}

function resolveAcwrZone(latest: LoadSnapshot): AcwrZone | "low" {
  // Prefer server-provided zone (per LEADER.md contract). Fall back to numeric mapping
  // using the thresholds documented in FRONTEND.md when backend omits the field.
  if (latest.acwr_zone) return latest.acwr_zone
  return zoneFromAcwr(latest.acwr)
}

function zoneFromAcwr(acwr: number): AcwrZone | "low" {
  if (acwr < 0.8) return "low"
  if (acwr <= 1.3) return "green"
  if (acwr <= 1.5) return "yellow"
  return "red"
}

function BaseliningBanner({ count }: { count: number }) {
  return (
    <Alert
      className="font-semibold"
      message={`Baselining: ${Math.max(0, 14 - count)} more days needed for full load accuracy.`}
      showIcon
      type="warning"
    />
  )
}

function MissingAthleteState() {
  return <StatusPage message="Connect Strava or enter an athlete id before opening the dashboard." />
}

function DashboardSkeleton() {
  const panel =
    "rounded-xl border border-white/[0.14] bg-brand-charcoal/70 p-5 shadow-[0_20px_60px_rgba(0,0,0,0.35)]"
  return (
    <main className="px-4 py-6 text-neutral-50" aria-busy="true" aria-label="Loading dashboard">
      <div className="mx-auto max-w-6xl space-y-6">
        <header className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-4">
            <SkeletonBlock className="h-14 w-14" rounded="full" variant="dark" />
            <div className="space-y-2">
              <SkeletonLine height="1.25rem" variant="dark" width="180px" />
              <SkeletonLine height="0.75rem" variant="dark" width="120px" />
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <SkeletonBlock className="h-9 w-28" rounded="lg" variant="dark" />
            <SkeletonBlock className="h-10 w-24" rounded="lg" variant="dark" />
          </div>
        </header>
        <section className={`grid grid-cols-2 gap-3 md:grid-cols-4 ${panel}`}>
          {Array.from({ length: 4 }).map((_, i) => (
            <div className="space-y-2" key={i}>
              <SkeletonLine height="0.625rem" variant="dark" width="60%" />
              <SkeletonLine height="1.25rem" variant="dark" width="80%" />
              <SkeletonLine height="0.625rem" variant="dark" width="40%" />
            </div>
          ))}
        </section>
        <section className="grid gap-4 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div className="min-h-28 rounded-lg border border-white/10 bg-white/[0.03] p-4" key={i}>
              <SkeletonLine height="0.625rem" variant="dark" width="40%" />
              <SkeletonLine className="mt-3" height="1.5rem" variant="dark" width="70%" />
              <SkeletonLine className="mt-2" height="0.625rem" variant="dark" width="55%" />
            </div>
          ))}
        </section>
        <section className="grid gap-6 xl:grid-cols-[1fr_320px]">
          <SkeletonBlock className="h-72" rounded="xl" variant="dark" />
          <SkeletonBlock className="h-72" rounded="xl" variant="dark" />
        </section>
        <section className={panel}>
          <SkeletonLine height="1rem" variant="dark" width="160px" />
          <div className="mt-4 divide-y divide-white/10">
            {Array.from({ length: 4 }).map((_, i) => (
              <div className="flex items-center justify-between py-4" key={i}>
                <div className="space-y-2">
                  <SkeletonLine height="0.875rem" variant="dark" width="220px" />
                  <SkeletonLine height="0.625rem" variant="dark" width="160px" />
                </div>
                <SkeletonBlock className="h-6 w-16" rounded="full" variant="dark" />
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  )
}

function StatusPage({ message }: { message: string }) {
  return (
    <main className="min-h-[50vh] px-4 py-12 text-neutral-50">
      <p className="text-brand-muted">{message}</p>
      <Link className="mt-4 inline-block font-semibold text-brand-teal hover:underline" to="/connect">
        Go to connect
      </Link>
    </main>
  )
}

function EmptyActivities() {
  return <p className="py-6 text-sm text-brand-muted">No processed activities yet.</p>
}

function statusClass(status: ActivityListItem["processing_status"]): string {
  if (status === "done") return "rounded-full bg-emerald-500/20 px-3 py-1 text-xs font-bold text-emerald-300"
  if (status === "failed") return "rounded-full bg-red-500/20 px-3 py-1 text-xs font-bold text-red-300"
  return "rounded-full bg-white/10 px-3 py-1 text-xs font-bold text-brand-muted"
}

function formatVolume(volume?: DashboardLoadResponse["weekly_volume"]): string {
  return volume ? `${volume.distance_km.toFixed(1)} km` : "0.0 km"
}

function formatElevation(volume?: DashboardLoadResponse["weekly_volume"]): string {
  return volume ? `${Math.round(volume.elevation_gain_m)} m D+` : "0 m D+"
}

function formatKm(meters: number): string {
  return `${(meters / 1000).toFixed(1)} km`
}

function formatMinutes(seconds: number): string {
  return `${Math.round(seconds / 60)} min`
}

function toIso(d: Date): string {
  return d.toISOString().slice(0, 10)
}

function usePlannedThisWeek(athleteId: number) {
  const today = new Date()
  const end = new Date()
  end.setDate(today.getDate() + 6)
  return useQuery({
    queryKey: ["plan-range", athleteId, toIso(today), toIso(end)],
    queryFn: () =>
      getPlanRange({
        athleteId,
        from: toIso(today),
        to: toIso(end),
      }),
  })
}

function ThisWeekStrip({ athleteId }: { athleteId: number }) {
  const query = usePlannedThisWeek(athleteId)
  const entries = query.data ?? []
  if (entries.length === 0) return null
  const byDate = new Map<string, PlanEntry>()
  for (const entry of entries) byDate.set(entry.date, entry)

  const today = new Date()
  const days: { label: string; iso: string; isToday: boolean }[] = []
  for (let i = 0; i < 7; i++) {
    const d = new Date()
    d.setDate(today.getDate() + i)
    const iso = toIso(d)
    days.push({
      label: i === 0 ? "Today" : d.toLocaleDateString("en-US", { weekday: "short" }),
      iso,
      isToday: i === 0,
    })
  }

  return (
    <section className="mb-4 rounded-lg border border-slate-200 bg-white p-4 shadow-panel">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
        This week (planned)
      </h2>
      <div className="grid grid-cols-7 gap-2 text-center">
        {days.map((day) => {
          const entry = byDate.get(day.iso) ?? null
          return (
            <div
              className={
                "rounded border p-2 text-xs " +
                (day.isToday
                  ? "border-trail-strava bg-orange-50"
                  : "border-slate-200")
              }
              key={day.iso}
            >
              <p className="font-bold text-slate-800">{day.label}</p>
              <p className="mt-1 text-slate-700">
                {entry ? entry.workout_type : "—"}
              </p>
              <p className="mt-1 font-mono text-[11px] text-slate-500">
                {entry && entry.planned_tss !== null
                  ? `TSS ${entry.planned_tss.toFixed(0)}`
                  : ""}
              </p>
            </div>
          )
        })}
      </div>
    </section>
  )
}
