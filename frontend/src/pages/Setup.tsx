import { type FormEvent, useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { Steps, Button, Input, Select, Card, Typography } from "antd"
import {
  getAthleteInfo,
  getStoredAthleteId,
  requireAthleteId,
  saveOnboardingProfile,
} from "../api/client"
import { SkeletonBlock, SkeletonLine } from "../components/Skeleton"
import type { LanguageCode, OnboardingProfilePayload, UnitSystem } from "../types"

const steps = ["Threshold HR", "Threshold pace", "Body metrics", "Preferences"] as const

interface SetupForm {
  lthr: string
  maxHr: string
  thresholdPaceSecKm: string
  weightKg: string
  vo2maxEstimate: string
  units: UnitSystem
  language: LanguageCode
}

const initialForm: SetupForm = {
  lthr: "",
  maxHr: "",
  thresholdPaceSecKm: "",
  weightKg: "",
  vo2maxEstimate: "",
  units: "metric",
  language: "en",
}

export default function Setup() {
  const athleteId = getStoredAthleteId()
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [form, setForm] = useState(initialForm)
  const [error, setError] = useState<string | null>(null)

  const athleteQuery = useQuery({
    queryKey: ["athlete", athleteId],
    queryFn: () => getAthleteInfo(requireAthleteId(athleteId)),
    enabled: athleteId !== null,
  })

  useEffect(() => {
    if (athleteId === null) return
    if (!athleteQuery.isSuccess) return
    if (athleteQuery.data.profile?.onboarding_complete) {
      navigate(`/dashboard?athlete_id=${athleteId}`, { replace: true })
    }
  }, [athleteId, athleteQuery.isSuccess, athleteQuery.data, navigate])

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const id = requireAthleteId(athleteId)
    await saveOnboardingProfile(toPayload(form, id))
    navigate(`/dashboard?athlete_id=${id}`)
  }

  if (athleteId === null) return <SetupStatus message="Add athlete_id in the URL before setup." />
  if (athleteQuery.isPending) {
    return <SetupSkeleton />
  }
  if (athleteQuery.isError) {
    return <SetupStatus message={athleteQuery.error.message} />
  }

  return (
    <main className="min-h-screen bg-trail-surface px-4 py-8 text-trail-ink">
      <Card bordered={false} className="mx-auto max-w-xl rounded-lg border border-slate-200 bg-white p-2 shadow-panel">
        <form onSubmit={save}>
          <StepProgress step={step} />
          <Typography.Title level={2} className="!mt-8 !mb-0 font-bold text-slate-950">{steps[step]}</Typography.Title>
          <StepFields form={form} setForm={setForm} step={step} />
          {error ? <p className="mt-4 text-sm font-semibold text-red-600">{error}</p> : null}
          <SetupActions setError={setError} setStep={setStep} step={step} />
        </form>
      </Card>
    </main>
  )
}

function StepProgress({ step }: { step: number }) {
  return (
    <Steps 
      current={step} 
      size="small"
      items={steps.map(label => ({ title: label }))} 
    />
  )
}

function StepFields(props: {
  form: SetupForm
  setForm: (value: SetupForm) => void
  step: number
}) {
  if (props.step === 0) return <ThresholdFields {...props} />
  if (props.step === 1) return <PaceFields {...props} />
  if (props.step === 2) return <BodyFields {...props} />
  return <PreferenceFields {...props} />
}

function ThresholdFields(props: FormProps) {
  return (
    <div className="mt-6 space-y-4">
      <NumberField label="Lactate threshold HR" value={props.form.lthr} onChange={(value) => update(props, "lthr", value)} placeholder="162" />
      <NumberField label="Max HR" value={props.form.maxHr} onChange={(value) => update(props, "maxHr", value)} placeholder="192" />
    </div>
  )
}

function PaceFields(props: FormProps) {
  return (
    <div className="mt-6 space-y-4">
      <NumberField label="Threshold pace seconds per km" value={props.form.thresholdPaceSecKm} onChange={(value) => update(props, "thresholdPaceSecKm", value)} placeholder="270" />
      <p className="text-sm text-slate-500">270 seconds equals 4:30/km.</p>
    </div>
  )
}

function BodyFields(props: FormProps) {
  return (
    <div className="mt-6 space-y-4">
      <NumberField label="Weight kg" value={props.form.weightKg} onChange={(value) => update(props, "weightKg", value)} placeholder="68" />
      <NumberField label="VO2max estimate" value={props.form.vo2maxEstimate} onChange={(value) => update(props, "vo2maxEstimate", value)} placeholder="52" />
    </div>
  )
}

function PreferenceFields(props: FormProps) {
  return (
    <div className="mt-6 grid gap-4 sm:grid-cols-2">
      <SelectField label="Units" value={props.form.units} onChange={(value) => update(props, "units", value as UnitSystem)} options={["metric", "imperial"]} />
      <SelectField label="Language" value={props.form.language} onChange={(value) => update(props, "language", value as LanguageCode)} options={["en", "vi"]} />
    </div>
  )
}

interface FormProps {
  form: SetupForm
  setForm: (value: SetupForm) => void
}

function update<K extends keyof SetupForm>(props: FormProps, key: K, value: SetupForm[K]) {
  props.setForm({ ...props.form, [key]: value })
}

function NumberField(props: {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder: string
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-semibold text-slate-700">{props.label}</span>
      <Input 
        size="large"
        className="w-full text-slate-950" 
        inputMode="numeric" 
        onChange={(event) => props.onChange(event.target.value)} 
        placeholder={props.placeholder} 
        value={props.value} 
      />
    </label>
  )
}

function SelectField(props: {
  label: string
  options: string[]
  value: string
  onChange: (value: string) => void
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-semibold text-slate-700">{props.label}</span>
      <Select 
        size="large"
        className="w-full" 
        onChange={(value) => props.onChange(value)} 
        value={props.value}
      >
        {props.options.map((option) => <Select.Option key={option} value={option}>{option}</Select.Option>)}
      </Select>
    </label>
  )
}

function SetupActions(props: {
  setError: (value: string | null) => void
  setStep: (value: (step: number) => number) => void
  step: number
}) {
  return (
    <div className="mt-8 flex items-center justify-between">
      <Button 
        type="default"
        size="large"
        className="font-semibold text-slate-500 disabled:opacity-40" 
        disabled={props.step === 0} 
        onClick={() => props.setStep((step) => Math.max(0, step - 1))}
      >
        Back
      </Button>
      {props.step < steps.length - 1 ? <NextButton {...props} /> : <FinishButton />}
    </div>
  )
}

function NextButton(props: {
  setError: (value: string | null) => void
  setStep: (value: (step: number) => number) => void
}) {
  return (
    <Button 
      type="primary"
      size="large"
      className="bg-slate-950 font-bold" 
      onClick={() => advance(props)}
    >
      Next
    </Button>
  )
}

function FinishButton() {
  return <Button type="primary" size="large" className="bg-trail-strava font-bold border-none" htmlType="submit">Finish</Button>
}

function advance(props: {
  setError: (value: string | null) => void
  setStep: (value: (step: number) => number) => void
}) {
  props.setError(null)
  props.setStep((step) => Math.min(steps.length - 1, step + 1))
}

function toPayload(form: SetupForm, athleteId: number): OnboardingProfilePayload {
  return {
    athlete_id: athleteId,
    lthr: optionalNumber(form.lthr),
    max_hr: optionalNumber(form.maxHr),
    threshold_pace_sec_km: optionalNumber(form.thresholdPaceSecKm),
    weight_kg: optionalNumber(form.weightKg),
    vo2max_estimate: optionalNumber(form.vo2maxEstimate),
    units: form.units,
    language: form.language,
  }
}

function optionalNumber(value: string): number | undefined {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined
}

function SetupStatus({ message }: { message: string }) {
  return <main className="min-h-screen bg-trail-surface p-8 text-slate-800">{message}</main>
}

function SetupSkeleton() {
  return (
    <main
      aria-busy="true"
      aria-label="Loading profile"
      className="min-h-screen bg-trail-surface px-4 py-8 text-trail-ink"
    >
      <div className="mx-auto max-w-xl rounded-lg border border-slate-200 bg-white p-6 shadow-panel">
        <div className="flex items-center gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div className="flex flex-1 items-center gap-2" key={i}>
              <SkeletonBlock className="h-6 w-6" rounded="full" />
              <SkeletonLine height="0.625rem" width="60%" />
            </div>
          ))}
        </div>
        <SkeletonLine className="mt-8" height="1.5rem" width="55%" />
        <div className="mt-6 space-y-5">
          {Array.from({ length: 2 }).map((_, i) => (
            <div className="space-y-2" key={i}>
              <SkeletonLine height="0.75rem" width="160px" />
              <SkeletonBlock className="h-10 w-full" rounded="md" />
            </div>
          ))}
        </div>
        <div className="mt-8 flex items-center justify-between">
          <SkeletonBlock className="h-10 w-20" rounded="md" />
          <SkeletonBlock className="h-10 w-24" rounded="md" />
        </div>
      </div>
    </main>
  )
}
