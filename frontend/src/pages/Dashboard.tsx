import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { Typography, Alert, Button } from "antd"
import {
  getAthleteInfo,
  getDashboardLoad,
  getStoredAthleteId,
  listActivities,
  requireAthleteId,
} from "../api/client"
import AcwrGauge from "../components/AcwrGauge"
import LoadChart from "../components/LoadChart"
import MetricBadge from "../components/MetricBadge"
import PhaseIndicator from "../components/PhaseIndicator"
import type { ActivityListItem, AthleteInfo, DashboardLoadResponse, LoadSnapshot } from "../types"

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
  if (athleteId === null) return <MissingAthleteState />
  if (loadQuery.isPending) return <StatusPage message="Loading training load..." />
  if (loadQuery.isError) return <StatusPage message={loadQuery.error.message} />

  const load = loadQuery.data ?? emptyLoad
  const activities = activitiesQuery.data ?? []
  const athlete = athleteQuery.data ?? null
  return <DashboardView activities={activities} athlete={athlete} athleteId={athleteId} load={load} />
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
  return (
    <main className="min-h-screen bg-trail-surface px-4 py-6 text-trail-ink">
      <div className="mx-auto max-w-6xl space-y-6">
        <DashboardHeader athlete={props.athlete} load={props.load} />
        {isRiskZone(latest) ? <RiskBanner latest={latest} /> : null}
        {props.load.history.length < 14 ? <BaseliningBanner count={props.load.history.length} /> : null}
        {props.athlete ? <AthleteCard athlete={props.athlete} /> : null}
        <MetricGrid load={props.load} />
        <section className="grid gap-6 xl:grid-cols-[1fr_320px]">
          <LoadChart data={props.load.history} />
          <AcwrGauge acwr={latest.acwr} />
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
            src={athlete.avatar_url}
            alt={name ?? "Athlete"}
            className="h-14 w-14 rounded-full border-2 border-white object-cover shadow-sm"
          />
        ) : (
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-slate-200 text-xl font-bold text-slate-500 shadow-sm">
            {name ? name[0].toUpperCase() : "?"}
          </div>
        )}
        <div>
          {name ? (
            <Typography.Title level={1} className="!mt-0 !mb-0 !text-2xl font-bold text-slate-950">
              {name}
            </Typography.Title>
          ) : null}
          {athlete?.city || athlete?.country ? (
            <Typography.Text className="text-sm text-slate-500">
              {[athlete.city, athlete.country].filter(Boolean).join(", ")}
            </Typography.Text>
          ) : null}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <PhaseIndicator phase={load.training_phase} targetDate={load.target?.race_date} />
        <Link to="/targets">
          <Button className="rounded-lg border-slate-300 font-semibold text-slate-800" size="large">
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
    <section className="grid grid-cols-2 gap-3 rounded-lg border border-slate-200 bg-white p-5 shadow-panel md:grid-cols-4">
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
      <p className="text-xs font-semibold uppercase text-slate-400">{label}</p>
      <p className="mt-1 text-lg font-bold text-slate-950">{value}</p>
      <p className="text-xs text-slate-400">{hint}</p>
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
      <MetricBadge label="CTL" value={load.latest.ctl.toFixed(1)} caption="Fitness" help={METRIC_HELP.ctl} tone="blue" />
      <MetricBadge label="ATL" value={load.latest.atl.toFixed(1)} caption="Fatigue" help={METRIC_HELP.atl} tone="amber" />
      <MetricBadge
        label="TSB"
        value={load.latest.tsb.toFixed(1)}
        caption="Form"
        help={METRIC_HELP.tsb}
        tone={load.latest.tsb < -30 ? "red" : "emerald"}
      />
      <MetricBadge
        label="Weekly volume"
        value={formatVolume(volume)}
        caption={formatElevation(volume)}
        help={METRIC_HELP.weeklyVolume}
        tone="violet"
      />
    </section>
  )
}

function RecentActivities(props: { activities: ActivityListItem[]; athleteId: number }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
      <h2 className="text-lg font-bold text-slate-950">Recent activities</h2>
      <div className="mt-4 divide-y divide-slate-100">
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
    <Link className="flex flex-col gap-2 py-4 hover:bg-slate-50 md:flex-row md:items-center md:justify-between" to={`/activities/${activity.id}?athlete_id=${props.athleteId}`}>
      <span>
        <span className="block font-semibold text-slate-950">{activity.name}</span>
        <span className="text-sm text-slate-500">{activity.sport_type} · {formatKm(activity.distance_m)} · {formatMinutes(activity.elapsed_time_sec)}</span>
      </span>
      <span className={statusClass(activity.processing_status)}>{activity.processing_status}</span>
    </Link>
  )
}

function RiskBanner({ latest }: { latest: LoadSnapshot }) {
  return (
    <Alert 
      type="error"
      showIcon
      message={`Injury risk zone: ACWR ${latest.acwr.toFixed(2)} and TSB ${latest.tsb.toFixed(1)}. Consider deloading before adding more load.`}
      className="font-semibold"
    />
  )
}

function BaseliningBanner({ count }: { count: number }) {
  return (
    <Alert 
      type="warning"
      showIcon
      message={`Baselining: ${Math.max(0, 14 - count)} more days needed for full load accuracy.`}
      className="font-semibold"
    />
  )
}

function MissingAthleteState() {
  return <StatusPage message="Connect Strava or enter an athlete id before opening the dashboard." />
}

function StatusPage({ message }: { message: string }) {
  return (
    <main className="min-h-screen bg-trail-surface p-8 text-slate-800">
      <p>{message}</p>
      <Link className="mt-4 inline-block font-semibold text-blue-700" to="/">Go to connect</Link>
    </main>
  )
}

function EmptyActivities() {
  return <p className="py-6 text-sm text-slate-500">No processed activities yet.</p>
}

function isRiskZone(latest: LoadSnapshot): boolean {
  return latest.acwr > 1.5 || latest.tsb < -30
}

function statusClass(status: ActivityListItem["processing_status"]): string {
  if (status === "done") return "rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-700"
  if (status === "failed") return "rounded-full bg-red-100 px-3 py-1 text-xs font-bold text-red-700"
  return "rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600"
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
