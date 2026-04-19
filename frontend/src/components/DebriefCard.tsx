import type { Debrief } from "../types"

interface DebriefCardProps {
  debrief: Debrief
}

const CORE_SECTIONS = [
  { key: "load_verdict", label: "Load verdict", border: "border-blue-500", icon: "⚡" },
  { key: "technical_insight", label: "Technical insight", border: "border-amber-500", icon: "🔬" },
  { key: "next_session_action", label: "Next session", border: "border-emerald-500", icon: "🎯" },
] as const

const EXTRA_SECTIONS = [
  { key: "nutrition_protocol", label: "Recovery nutrition", border: "border-orange-400", icon: "🍜" },
  { key: "vmm_projection", label: "VMM 160km projection", border: "border-violet-500", icon: "🏔️" },
] as const

export default function DebriefCard({ debrief }: DebriefCardProps) {
  const hasExtras =
    (debrief.nutrition_protocol && debrief.nutrition_protocol.length > 0) ||
    (debrief.vmm_projection && debrief.vmm_projection.length > 0)

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
      <h2 className="text-lg font-bold text-slate-950">Post-run debrief</h2>
      <div className="mt-5 space-y-4">
        {CORE_SECTIONS.map(({ key, label, border, icon }) => (
          <DebriefSection key={key} border={border} label={label} icon={icon} text={debrief[key]} />
        ))}

        {hasExtras && (
          <div className="border-t border-slate-100 pt-4">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Elite coaching insights
            </p>
            <div className="space-y-4">
              {EXTRA_SECTIONS.map(({ key, label, border, icon }) => {
                const text = debrief[key]
                if (!text) return null
                return <DebriefSection key={key} border={border} label={label} icon={icon} text={text} />
              })}
            </div>
          </div>
        )}
      </div>
    </section>
  )
}

function DebriefSection(props: { border: string; icon: string; label: string; text: string }) {
  return (
    <article className={`border-l-4 pl-4 ${props.border}`}>
      <h3 className="text-xs font-semibold uppercase text-slate-500">
        {props.icon} {props.label}
      </h3>
      <p className="mt-1 text-sm leading-6 text-slate-800">{props.text}</p>
    </article>
  )
}
