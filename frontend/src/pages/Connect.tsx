import { type FormEvent, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { Alert, Button, Input } from "antd"
import DarkAppShell from "../components/layout/DarkAppShell"
import {
  clearAthleteId,
  getApiBaseUrl,
  getStoredAthleteId,
  persistAthleteId,
} from "../api/client"
import ConnectSeo from "../seo/ConnectSeo"

const OAUTH_ERROR_MESSAGES: Record<string, string> = {
  strava_token:
    "Strava could not finish login. Check STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET in backend .env, and that your Strava app’s Authorization Callback Domain matches this site (e.g. localhost). Then click Connect Strava again.",
  strava_payload: "Strava returned an unexpected response. Try Connect Strava again.",
  encryption_config:
    "Server misconfiguration: ENCRYPTION_KEY must be a base64 string that decodes to exactly 32 bytes. Generate one and restart the API.",
  server_error: "Something went wrong on the server while saving your login. Check the API terminal logs and try again.",
  invalid_state: "Your login session expired (e.g. API restarted). Click Connect Strava again.",
}

export default function Connect() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [athleteId, setAthleteId] = useState(getInitialAthleteId)
  const [error, setError] = useState<string | null>(null)
  const oauthErrorCode = searchParams.get("oauth_error")
  const oauthMessage =
    oauthErrorCode !== null
      ? (OAUTH_ERROR_MESSAGES[oauthErrorCode] ?? OAUTH_ERROR_MESSAGES.server_error)
      : null
  const sessionAthleteId = getStoredAthleteId()

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

  function dismissOauthError() {
    const next = new URLSearchParams(searchParams)
    next.delete("oauth_error")
    setSearchParams(next, { replace: true })
  }

  return (
    <DarkAppShell>
      <ConnectSeo />
      <main className="px-4 py-8 text-neutral-50">
        <div className="mx-auto mb-6 max-w-6xl">
          <Link className="font-mono text-xs font-semibold text-brand-muted transition hover:text-white" to="/">
            ← Back to home
          </Link>
        </div>
        {oauthMessage ? (
          <div className="mx-auto mb-6 max-w-6xl">
            <Alert closable message={oauthMessage} onClose={dismissOauthError} showIcon type="error" />
          </div>
        ) : null}
        {sessionAthleteId !== null ? (
          <div className="mx-auto mb-6 max-w-6xl">
            <Alert
              message="You’re signed in on this browser."
              description={
                <span className="flex flex-wrap items-center gap-3">
                  <span>
                    Athlete id <strong>{sessionAthleteId}</strong> is saved locally. Open the dashboard to continue, or
                    sign out to use another account.
                  </span>
                  <Button type="primary" onClick={() => navigate(`/dashboard?athlete_id=${sessionAthleteId}`)}>
                    Open dashboard
                  </Button>
                  <Button
                    className="p-0"
                    type="link"
                    onClick={() => {
                      clearAthleteId()
                      setAthleteId("")
                      navigate("/", { replace: true })
                    }}
                  >
                    Sign out (clear this browser)
                  </Button>
                </span>
              }
              showIcon
              type="success"
            />
          </div>
        ) : null}
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
    </DarkAppShell>
  )
}

function ConnectPanel(props: { onConnect: () => void }) {
  return (
    <div className="rounded-2xl border border-white/[0.14] bg-brand-charcoal/90 p-8 shadow-[0_20px_60px_rgba(0,0,0,0.45)]">
      <p className="text-sm font-semibold uppercase tracking-wide text-brand-teal">Strava AI Coach</p>
      <h1 className="mt-6 max-w-2xl text-4xl font-bold leading-tight text-neutral-50 md:text-6xl">
        Numeric coaching after every trail run.
      </h1>
      <p className="mt-5 max-w-xl text-base leading-7 text-brand-muted">
        Connect Strava, set your thresholds, and review load, ACWR, and debriefs built around your current race target.
      </p>
      <Button
        className="mt-8 border-none font-bold !bg-trail-strava !text-white hover:!bg-orange-600"
        size="large"
        type="primary"
        onClick={props.onConnect}
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
    <div className="rounded-2xl border border-white/[0.14] bg-brand-charcoal/60 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.35)]">
      <h2 className="text-xl font-bold text-neutral-50">Open your dashboard</h2>
      <p className="mt-2 text-sm leading-6 text-brand-muted">
        OAuth redirects back with an athlete id. During local backend work, enter that id here to load the app shell and
        API-backed screens.
      </p>
      <form className="mt-6 space-y-4" onSubmit={props.onSubmit}>
        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-neutral-200">Athlete id</span>
          <Input
            className="!border-white/15 !bg-black/30 !text-neutral-50 placeholder:!text-brand-muted"
            inputMode="numeric"
            onChange={(event) => props.onChange(event.target.value)}
            placeholder="1"
            value={props.athleteId}
          />
        </label>
        {props.error ? <p className="text-sm font-semibold text-red-400">{props.error}</p> : null}
        <Button
          className="w-full !border-brand-teal/40 !bg-brand-teal/15 !font-bold !text-brand-teal hover:!bg-brand-teal/25"
          htmlType="submit"
          size="large"
          type="default"
          style={{ height: "auto", padding: "0.75rem 1rem", borderRadius: "0.5rem" }}
        >
          Continue
        </Button>
      </form>
      <div className="mt-6 flex flex-wrap gap-3 text-sm">
        <Link className="font-semibold text-brand-teal hover:underline" to="/setup">
          Setup profile
        </Link>
        <Link className="font-semibold text-brand-teal hover:underline" to="/targets">
          Manage targets
        </Link>
      </div>
    </div>
  )
}

function getInitialAthleteId(): string {
  return getStoredAthleteId()?.toString() ?? ""
}
