import type { TrainingPhase } from "../types"

interface PhaseIndicatorProps {
  phase: TrainingPhase
  targetDate?: string
}

const phaseClasses: Record<TrainingPhase, string> = {
  Base: "border-blue-200 bg-blue-50 text-blue-800",
  Build: "border-violet-200 bg-violet-50 text-violet-800",
  Peak: "border-amber-200 bg-amber-50 text-amber-800",
  Taper: "border-emerald-200 bg-emerald-50 text-emerald-800",
}

export default function PhaseIndicator(props: PhaseIndicatorProps) {
  const weeks = getWeeksToTarget(props.targetDate)
  return (
    <span className={`inline-flex flex-col rounded-lg border px-3 py-2 ${phaseClasses[props.phase]}`}>
      <span className="text-xs font-semibold uppercase">Training phase</span>
      <span className="text-sm font-bold">{props.phase}</span>
      {weeks !== null ? <span className="text-xs">{weeks} weeks out</span> : null}
    </span>
  )
}

function getWeeksToTarget(targetDate?: string): number | null {
  if (!targetDate) return null
  const millis = new Date(targetDate).getTime() - Date.now()
  return Math.max(0, Math.ceil(millis / 604_800_000))
}
