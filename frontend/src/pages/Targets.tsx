import { type FormEvent, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { Card, Typography, Button, Input, Select } from "antd"
import {
  createRaceTarget,
  deleteRaceTarget,
  getStoredAthleteId,
  listRaceTargets,
  requireAthleteId,
} from "../api/client"
import type { RacePriority, RaceTarget, RaceTargetPayload } from "../types"

interface TargetForm {
  raceName: string
  raceDate: string
  distanceKm: string
  elevationGainM: string
  goalTimeSec: string
  priority: RacePriority
}

const initialForm: TargetForm = {
  raceName: "",
  raceDate: "",
  distanceKm: "",
  elevationGainM: "",
  goalTimeSec: "",
  priority: "A",
}

export default function Targets() {
  const athleteId = getStoredAthleteId()
  if (athleteId === null) return <TargetsStatus message="Add athlete_id before managing targets." />
  return <TargetsView athleteId={athleteId} />
}

function TargetsView({ athleteId }: { athleteId: number }) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState(initialForm)
  const targets = useTargetsQuery(athleteId)
  const create = useCreateTarget(athleteId, queryClient, () => setForm(initialForm))
  const remove = useDeleteTarget(athleteId, queryClient)

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    create.mutate(toPayload(form, requireAthleteId(athleteId)))
  }

  return (
    <main className="min-h-screen bg-trail-surface px-4 py-8 text-trail-ink">
      <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[380px_1fr]">
        <TargetFormCard form={form} onChange={setForm} onSubmit={submit} />
        <TargetList isLoading={targets.isPending} onDelete={remove.mutate} targets={targets.data ?? []} />
      </div>
    </main>
  )
}

function useTargetsQuery(athleteId: number) {
  return useQuery({
    queryKey: ["targets", athleteId],
    queryFn: () => listRaceTargets(athleteId),
  })
}

function useCreateTarget(
  athleteId: number,
  queryClient: ReturnType<typeof useQueryClient>,
  onSuccess: () => void,
) {
  return useMutation({
    mutationFn: createRaceTarget,
    onSuccess: async () => {
      onSuccess()
      await queryClient.invalidateQueries({ queryKey: ["targets", athleteId] })
    },
  })
}

function useDeleteTarget(
  athleteId: number,
  queryClient: ReturnType<typeof useQueryClient>,
) {
  return useMutation({
    mutationFn: (id: number) => deleteRaceTarget({ id, athleteId }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["targets", athleteId] })
    },
  })
}

function TargetFormCard(props: {
  form: TargetForm
  onChange: (form: TargetForm) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}) {
  return (
    <Card className="rounded-lg shadow-panel border-slate-200" bordered={false}>
      <Link className="font-semibold text-blue-700 hover:underline" to="/dashboard">Dashboard</Link>
      <Typography.Title level={2} className="!mt-4 !mb-0 font-bold text-slate-950">Race targets</Typography.Title>
      <form className="mt-6 space-y-4" onSubmit={props.onSubmit}>
        <TextField label="Race name" value={props.form.raceName} onChange={(value) => change(props, "raceName", value)} placeholder="VMM 100" />
        <TextField label="Race date" value={props.form.raceDate} onChange={(value) => change(props, "raceDate", value)} placeholder="2026-11-15" type="date" />
        <TextField label="Distance km" value={props.form.distanceKm} onChange={(value) => change(props, "distanceKm", value)} placeholder="100" />
        <TextField label="Elevation gain m" value={props.form.elevationGainM} onChange={(value) => change(props, "elevationGainM", value)} placeholder="8000" />
        <PriorityField form={props.form} onChange={props.onChange} />
        <Button size="large" type="primary" htmlType="submit" className="w-full bg-trail-strava font-bold">Add target</Button>
      </form>
    </Card>
  )
}

function PriorityField(props: {
  form: TargetForm
  onChange: (form: TargetForm) => void
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-semibold text-slate-700">Priority</span>
      <Select 
        className="w-full" 
        size="large"
        onChange={(value) => change(props, "priority", value as RacePriority)} 
        value={props.form.priority}
      >
        {(["A", "B", "C"] as const).map((priority) => <Select.Option key={priority} value={priority}>{priority}</Select.Option>)}
      </Select>
    </label>
  )
}

function TargetList(props: {
  isLoading: boolean
  onDelete: (id: number) => void
  targets: RaceTarget[]
}) {
  if (props.isLoading) return <TargetsStatus message="Loading targets..." />
  return (
    <Card className="rounded-lg shadow-panel border-slate-200" bordered={false}>
      <Typography.Title level={3} className="!mt-0 !mb-4 font-bold text-slate-950">Upcoming races</Typography.Title>
      <div className="divide-y divide-slate-100">
        {props.targets.map((target) => <TargetRow key={target.id} onDelete={props.onDelete} target={target} />)}
        {props.targets.length === 0 ? <p className="py-8 text-sm text-slate-500">No race targets yet.</p> : null}
      </div>
    </Card>
  )
}

function TargetRow(props: {
  onDelete: (id: number) => void
  target: RaceTarget
}) {
  return (
    <article className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p className="font-bold text-slate-950">{props.target.race_name}</p>
        <p className="text-sm text-slate-500">{props.target.race_date} · {props.target.distance_km.toFixed(1)} km · {props.target.priority} race</p>
      </div>
      <Button danger size="middle" onClick={() => props.onDelete(props.target.id)} className="font-bold border-red-200">
        Delete
      </Button>
    </article>
  )
}

function TextField(props: {
  label: string
  onChange: (value: string) => void
  placeholder: string
  type?: string
  value: string
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-semibold text-slate-700">{props.label}</span>
      <Input
        size="large"
        className="w-full text-slate-950" 
        onChange={(event) => props.onChange(event.target.value)} 
        placeholder={props.placeholder} 
        type={props.type ?? "text"} 
        value={props.value} 
      />
    </label>
  )
}

function change<K extends keyof TargetForm>(
  props: { form: TargetForm; onChange: (form: TargetForm) => void },
  key: K,
  value: TargetForm[K],
) {
  props.onChange({ ...props.form, [key]: value })
}

function toPayload(form: TargetForm, athleteId: number): RaceTargetPayload {
  return {
    athlete_id: athleteId,
    race_name: form.raceName,
    race_date: form.raceDate,
    distance_km: Number(form.distanceKm),
    elevation_gain_m: optionalNumber(form.elevationGainM),
    goal_time_sec: optionalNumber(form.goalTimeSec),
    priority: form.priority,
  }
}

function optionalNumber(value: string): number | undefined {
  if (value.trim() === "") return undefined
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : undefined
}

function TargetsStatus({ message }: { message: string }) {
  return <main className="min-h-screen bg-trail-surface p-8 text-slate-800">{message}</main>
}
