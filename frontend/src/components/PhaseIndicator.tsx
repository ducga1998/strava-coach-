import { InfoCircleOutlined } from "@ant-design/icons"
import { Tooltip } from "antd"
import type { TrainingPhase } from "../types"

const PHASE_HELP =
  "Phase is inferred from your race date: Base builds volume, Build adds intensity, Peak sharpens fitness, Taper cuts load before race day."

interface PhaseIndicatorProps {
  phase: TrainingPhase
  targetDate?: string
  variant?: "light" | "dark"
}

const phaseClassesLight: Record<TrainingPhase, string> = {
  Base: "border-blue-200 bg-blue-50 text-blue-800",
  Build: "border-violet-200 bg-violet-50 text-violet-800",
  Peak: "border-amber-200 bg-amber-50 text-amber-800",
  Taper: "border-emerald-200 bg-emerald-50 text-emerald-800",
}

const phaseClassesDark: Record<TrainingPhase, string> = {
  Base: "border-blue-500/40 bg-blue-950/50 text-blue-100",
  Build: "border-violet-500/40 bg-violet-950/50 text-violet-100",
  Peak: "border-amber-500/40 bg-amber-950/50 text-amber-100",
  Taper: "border-emerald-500/40 bg-emerald-950/50 text-emerald-100",
}

export default function PhaseIndicator(props: PhaseIndicatorProps) {
  const variant = props.variant ?? "light"
  const weeks = getWeeksToTarget(props.targetDate)
  const table = variant === "dark" ? phaseClassesDark : phaseClassesLight
  return (
    <span className={`inline-flex flex-col rounded-lg border px-3 py-2 ${table[props.phase]}`}>
      <span className="flex items-center gap-1 text-xs font-semibold uppercase">
        Training phase
        <Tooltip title={PHASE_HELP} trigger={["hover", "click"]}>
          <InfoCircleOutlined className="cursor-help text-[0.65rem] normal-case opacity-70" />
        </Tooltip>
      </span>
      <span className="text-sm font-bold">{props.phase}</span>
      {weeks !== null ? <span className="text-xs opacity-90">{weeks} weeks out</span> : null}
    </span>
  )
}

function getWeeksToTarget(targetDate?: string): number | null {
  if (!targetDate) return null
  const millis = new Date(targetDate).getTime() - Date.now()
  return Math.max(0, Math.ceil(millis / 604_800_000))
}
