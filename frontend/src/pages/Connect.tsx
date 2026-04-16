import { type FormEvent, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { Button, Input } from "antd"
import { getApiBaseUrl, getStoredAthleteId, persistAthleteId } from "../api/client"

export default function Connect() {
  const navigate = useNavigate()
  const [athleteId, setAthleteId] = useState(getInitialAthleteId)
  const [error, setError] = useState<string | null>(null)

  function connectStrava() {
    window.location.assign(`${getApiBaseUrl()}/auth/strava`)
  }

  function continueWithId(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const parsed = Number(athleteId)
    if (!Number.isInteger(parsed) || parsed <= 0) return setError("Enter a valid athlete id.")
    persistAthleteId(parsed)
    navigate(`/dashboard?athlete_id=${parsed}`)
  }

  return (
    <main className="min-h-screen bg-trail-surface px-4 py-8 text-trail-ink">
      <section className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[1.05fr_0.95fr]">
        <ConnectPanel onConnect={connectStrava} />
        <AccessPanel
          athleteId={athleteId}
          error={error}
          onChange={setAthleteId}
          onSubmit={continueWithId}
        />
      </section>
    </main>
  )
}

function ConnectPanel(props: { onConnect: () => void }) {
  return (
    <div className="rounded-lg bg-slate-950 p-8 text-white shadow-panel">
      <p className="text-sm font-semibold uppercase text-orange-300">Strava AI Coach</p>
      <h1 className="mt-6 max-w-2xl text-4xl font-bold leading-tight md:text-6xl">
        Numeric coaching after every trail run.
      </h1>
      <p className="mt-5 max-w-xl text-base leading-7 text-slate-300">
        Connect Strava, set your thresholds, and review load, ACWR, and debriefs
        built around your current race target.
      </p>
      <Button
        type="primary"
        size="large"
        onClick={props.onConnect}
        className="mt-8 bg-trail-strava border-none font-bold text-white transition hover:bg-orange-600"
        style={{ height: "auto", padding: "0.75rem 1.25rem", borderRadius: "0.5rem" }}
      >
        Connect Strava
      </Button>
    </div>
  )
}

function AccessPanel(props: {
  athleteId: string
  error: string | null
  onChange: (value: string) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-panel">
      <h2 className="text-xl font-bold text-slate-950">Open your dashboard</h2>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        OAuth redirects back with an athlete id. During local backend work, enter
        that id here to load the app shell and API-backed screens.
      </p>
      <form className="mt-6 space-y-4" onSubmit={props.onSubmit}>
        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-slate-700">Athlete id</span>
          <Input
            className="w-full rounded-lg px-3 py-3 text-slate-950"
            inputMode="numeric"
            onChange={(event) => props.onChange(event.target.value)}
            placeholder="1"
            value={props.athleteId}
          />
        </label>
        {props.error ? <p className="text-sm font-semibold text-red-600">{props.error}</p> : null}
        <Button 
          type="primary" 
          htmlType="submit" 
          className="w-full bg-slate-950 font-bold text-white hover:!bg-slate-800"
          style={{ height: "auto", padding: "0.75rem 1rem", borderRadius: "0.5rem" }}
        >
          Continue
        </Button>
      </form>
      <div className="mt-6 flex flex-wrap gap-3 text-sm">
        <Link className="font-semibold text-blue-700 hover:underline" to="/setup">
          Setup profile
        </Link>
        <Link className="font-semibold text-blue-700 hover:underline" to="/targets">
          Manage targets
        </Link>
      </div>
    </div>
  )
}

function getInitialAthleteId(): string {
  return getStoredAthleteId()?.toString() ?? ""
}
