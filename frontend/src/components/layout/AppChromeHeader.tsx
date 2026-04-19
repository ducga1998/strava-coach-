import { Link } from "react-router-dom"
import { getStoredAthleteId } from "../../api/client"

export default function AppChromeHeader() {
  const athleteId = getStoredAthleteId()
  return (
    <header className="fixed left-0 right-0 top-0 z-50 border-b border-white/12 bg-brand-void/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link className="font-mono text-xs font-bold tracking-[0.2em] text-white md:text-sm" to="/">
          STRAVA AI COACH
        </Link>
        <nav className="flex items-center gap-3 md:gap-5">
          {athleteId !== null ? (
            <Link
              className="font-mono text-[11px] text-brand-muted transition hover:text-white md:text-xs"
              to={`/dashboard?athlete_id=${athleteId}`}
            >
              Dashboard
            </Link>
          ) : null}
          <Link
            className="rounded-full border border-brand-teal/35 bg-brand-teal/10 px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-wider text-brand-teal transition hover:border-brand-teal/60 hover:bg-brand-teal/20 md:px-4 md:text-xs"
            to="/connect"
          >
            Connect
          </Link>
        </nav>
      </div>
    </header>
  )
}
