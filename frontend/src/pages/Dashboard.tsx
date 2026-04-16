import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { Typography, Alert, Button } from "antd"
import {
  getDashboardLoad,
  getStoredAthleteId,
  listActivities,
  requireAthleteId,
} from "../api/client"
import AcwrGauge from "../components/AcwrGauge"
import LoadChart from "../components/LoadChart"
import MetricBadge from "../components/MetricBadge"
import PhaseIndicator from "../components/PhaseIndicator"
import type { ActivityListItem, DashboardLoadResponse, LoadSnapshot } from "../types"

const emptyLoad: DashboardLoadResponse = {
  training_phase: "Base",
  latest: { ctl: 0, atl: 0, tsb: 0, acwr: 1 },
  history: [],
}

export default function Dashboard() {
  const athleteId = getStoredAthleteId()
  const loadQuery = useLoadQuery(athleteId)
  const activitiesQuery = useActivitiesQuery(athleteId)
  if (athleteId === null) return <MissingAthleteState />
  if (loadQuery.isPending) return <StatusPage message="Loading training load..." />
  if (loadQuery.isError) return <StatusPage message={loadQuery.error.message} />

  const load = loadQuery.data ?? emptyLoad
  const activities = activitiesQuery.data ?? []
  return <DashboardView activities={activities} athleteId={athleteId} load={load} />
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

function DashboardView(props: {
  activities: ActivityListItem[]
  athleteId: number
  load: DashboardLoadResponse
}) {
  const latest = props.load.latest
  return (
    <main className="min-h-screen bg-trail-surface px-4 py-6 text-trail-ink">
      <div className="mx-auto max-w-6xl space-y-6">
        <DashboardHeader load={props.load} />
        {isRiskZone(latest) ? <RiskBanner latest={latest} /> : null}
        {props.load.history.length < 14 ? <BaseliningBanner count={props.load.history.length} /> : null}
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

function DashboardHeader({ load }: { load: DashboardLoadResponse }) {
  return (
    <header className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div>
        <Typography.Text className="font-semibold uppercase text-trail-strava">Dashboard</Typography.Text>
        <Typography.Title level={1} className="!mt-1 !mb-0 !text-3xl font-bold text-slate-950">Training load</Typography.Title>
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

function MetricGrid({ load }: { load: DashboardLoadResponse }) {
  const volume = load.weekly_volume
  return (
    <section className="grid gap-4 md:grid-cols-4">
      <MetricBadge label="CTL" value={load.latest.ctl.toFixed(1)} caption="Fitness" tone="blue" />
      <MetricBadge label="ATL" value={load.latest.atl.toFixed(1)} caption="Fatigue" tone="amber" />
      <MetricBadge label="TSB" value={load.latest.tsb.toFixed(1)} caption="Form" tone={load.latest.tsb < -30 ? "red" : "emerald"} />
      <MetricBadge label="Weekly volume" value={formatVolume(volume)} caption={formatElevation(volume)} tone="violet" />
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
